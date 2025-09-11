import os
import re
import time
import logging
import datetime
from typing import Set, List, Tuple
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse
import PureCloudPlatformClientV2
from email_validator import validate_email, EmailNotValidError
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Configuration (will be loaded from environment variables in GitHub Actions) ---
def get_required_env_var(var_name: str) -> str:
    value = os.environ.get(var_name)
    if not value:
        raise ValueError(f"Required environment variable {var_name} is not set")
    return value

SLACK_BOT_TOKEN = get_required_env_var("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = get_required_env_var("SLACK_CHANNEL_ID")
GENESYS_CLIENT_ID = get_required_env_var("CLIENT_ID")
GENESYS_CLIENT_SECRET = get_required_env_var("CLIENT_SECRET")
GENESYS_REGION = os.environ.get("GENESYS_REGION", "eu_central_1")
GENESYS_DATA_TABLE_ID = get_required_env_var("GENESYS_DATA_TABLE_ID")

# Constants
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 1  # seconds
PAGE_SIZE = 100

LAST_RUN_TIMESTAMP_FILE = "last_run_timestamp.txt" # For local testing, in GitHub Actions, you might use artifacts or a different persistence method.

def get_last_run_timestamp():
    if os.path.exists(LAST_RUN_TIMESTAMP_FILE):
        with open(LAST_RUN_TIMESTAMP_FILE, 'r') as f:
            return float(f.read().strip())
    return 0 # Start from beginning if no timestamp found

def save_last_run_timestamp(timestamp):
    with open(LAST_RUN_TIMESTAMP_FILE, 'w') as f:
        f.write(str(timestamp))

def validate_and_normalize_email(email: str) -> str:
    """Validate email and return normalized form."""
    try:
        valid = validate_email(email)
        return valid.email.lower()
    except EmailNotValidError:
        return ""

def check_slack_scopes(client: WebClient):
    """Check if the bot has the required scopes."""
    try:
        # Test auth to verify token and bot identity
        auth_test = client.auth_test()
        if not auth_test['ok']:
            raise ValueError("Failed to authenticate with Slack")
            
        # Get the bot's scopes
        scopes = auth_test.get('bot_scopes', [])
        required_scopes = {'channels:history'}
        
        missing_scopes = required_scopes - set(scopes)
        if missing_scopes:
            raise ValueError(
                f"Bot needs the following scopes: {', '.join(missing_scopes)}. "
                "Please add these scopes in your Slack App settings and reinstall the app."
            )
            
        logger.info(f"Successfully verified Slack authentication as {auth_test['user']}")
            
    except SlackApiError as e:
        error_data = getattr(e.response, 'data', {})
        raise ValueError(f"Error verifying Slack authentication: {error_data.get('error', str(e))}")

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def get_slack_messages(client: WebClient, channel_id: str, oldest_timestamp: float) -> Tuple[List[dict], float]:
    """Fetch messages from Slack with pagination support."""
    all_messages = []
    newest_timestamp = oldest_timestamp
    cursor = None

    while True:
        try:
            response = client.conversations_history(
                channel=channel_id,
                oldest=oldest_timestamp,
                limit=PAGE_SIZE,
                cursor=cursor
            )
            
            if not response['ok']:
                error = response.get('error', 'unknown error')
                raise SlackApiError(f"Slack API error: {error}", response)
            
            messages = response.get("messages", [])
            all_messages.extend(messages)
            
            # Update newest timestamp
            for msg in messages:
                if float(msg["ts"]) > newest_timestamp:
                    newest_timestamp = float(msg["ts"])

            # Check if there are more messages
            if not response.get("has_more", False):
                break
                
            cursor = response["response_metadata"].get("next_cursor")
            if not cursor:  # If no cursor, we're done
                break
                
            time.sleep(RATE_LIMIT_DELAY)  # Respect rate limits
            
        except SlackApiError as e:
            if e.response.get("error") == "ratelimited":
                delay = int(e.response.headers.get("Retry-After", RATE_LIMIT_DELAY))
                time.sleep(delay)
                continue
            raise

    return all_messages, newest_timestamp

def get_slack_emails(client: WebClient, channel_id: str, oldest_timestamp: float) -> Tuple[List[str], float]:
    """Extract validated emails from Slack messages."""
    emails = set()
    try:
        messages, newest_timestamp = get_slack_messages(client, channel_id, oldest_timestamp)
        
        for msg in messages:
            if "text" in msg:
                # Regex to find email addresses
                found_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', msg["text"])
                for email in found_emails:
                    valid_email = validate_and_normalize_email(email)
                    if valid_email:
                        emails.add(valid_email)

        logger.info(f"Found {len(emails)} valid unique emails in Slack messages")
        return list(emails), newest_timestamp

    except Exception as e:
        logger.error(f"Error fetching Slack messages: {str(e)}")
        raise

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def get_genesys_data_table_rows(api_instance: PureCloudPlatformClientV2.ArchitectApi, data_table_id: str) -> Set[str]:
    """Fetch all existing blacklisted emails from Genesys data table with pagination."""
    existing_emails = set()
    page_number = 1
    
    try:
        while True:
            rows = api_instance.get_architect_datatable_rows(
                data_table_id,
                page_size=PAGE_SIZE,
                page_number=page_number
            )
            
            if not rows.entities:
                break
                
            for row in rows.entities:
                if 'EmailAddress' in row.properties:
                    email = validate_and_normalize_email(row.properties['EmailAddress'])
                    if email:
                        existing_emails.add(email)
            
            if page_number >= rows.page_count:
                break
                
            page_number += 1
            time.sleep(RATE_LIMIT_DELAY)  # Respect rate limits
            
        logger.info(f"Found {len(existing_emails)} existing blacklisted emails in Genesys")
        return existing_emails
        
    except PureCloudPlatformClientV2.rest.ApiException as e:
        logger.error(f"Error fetching Genesys Data Table rows: {str(e)}")
        raise

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def add_genesys_data_table_row(
    api_instance: PureCloudPlatformClientV2.ArchitectApi,
    data_table_id: str,
    email_address: str
) -> bool:
    """Add a new email to the Genesys blacklist data table."""
    try:
        # Validate email before adding
        email_address = validate_and_normalize_email(email_address)
        if not email_address:
            logger.warning(f"Invalid email address, skipping")
            return False

        # Create a new row object
        new_row = PureCloudPlatformClientV2.ArchitectDatatableRow()
        new_row.properties = {
            "EmailAddress": email_address,
            "DateAdded": datetime.datetime.utcnow().isoformat()
        }

        api_instance.add_architect_datatable_row(data_table_id, new_row)
        logger.info(f"Added {email_address} to Genesys Data Table")
        return True
        
    except PureCloudPlatformClientV2.rest.ApiException as e:
        logger.error(f"Error adding {email_address} to Genesys Data Table: {str(e)}")
        raise

def main():
    """Main execution function."""
    try:
        logger.info("Starting blacklist update process")
        
        # 1. Initialize and verify Slack Client
        logger.info("Initializing Slack client...")
        slack_client = WebClient(token=SLACK_BOT_TOKEN)
        
        try:
            check_slack_scopes(slack_client)
            logger.info("Slack authentication and scopes verified successfully")
        except ValueError as e:
            logger.error(f"Slack configuration error: {str(e)}")
            raise
        
        # 2. Initialize Genesys Cloud CX API
        # Set region
        region_host = {
            'us_east_1': 'https://api.mypurecloud.com',
            'us_west_2': 'https://api.usw2.pure.cloud',
            'eu_west_1': 'https://api.mypurecloud.ie',
            'eu_west_2': 'https://api.euw2.pure.cloud',
            'ap_southeast_2': 'https://api.mypurecloud.com.au',
            'ap_northeast_1': 'https://api.mypurecloud.jp',
            'eu_central_1': 'https://api.mypurecloud.de',
            'ap_northeast_2': 'https://api.apne2.pure.cloud',
            'ca_central_1': 'https://api.cac1.pure.cloud',
            'ap_south_1': 'https://api.aps1.pure.cloud',
            'sa_east_1': 'https://api.sae1.pure.cloud'
        }
        
        if GENESYS_REGION not in region_host:
            raise ValueError(f"Invalid region: {GENESYS_REGION}. Must be one of {', '.join(region_host.keys())}")
            
        # Create configuration
        configuration = PureCloudPlatformClientV2.Configuration()
        configuration.host = region_host[GENESYS_REGION]
        configuration.client_id = GENESYS_CLIENT_ID
        configuration.client_secret = GENESYS_CLIENT_SECRET
        
        # Create API client with configuration
        api_client = PureCloudPlatformClientV2.ApiClient(configuration)
        
        # Create API instance
        architect_api = PureCloudPlatformClientV2.ArchitectApi(api_client)
        
        # 3. Get last run timestamp
        last_run_ts = get_last_run_timestamp()
        logger.info(f"Last run timestamp: {last_run_ts}")
        
        # 4. Fetch emails from Slack
        new_emails, current_newest_ts = get_slack_emails(slack_client, SLACK_CHANNEL_ID, last_run_ts)
        
        if not new_emails:
            logger.info("No new emails to process. Exiting.")
            return
            
        # 5. Get existing emails from Genesys Data Table
        existing_genesys_emails = get_genesys_data_table_rows(architect_api, GENESYS_DATA_TABLE_ID)
        
        # 6. Add new emails to Genesys Data Table
        added_count = 0
        skipped_count = 0
        
        for email in new_emails:
            if email in existing_genesys_emails:
                logger.debug(f"Skipping already blacklisted email: {email}")
                skipped_count += 1
                continue
                
            try:
                if add_genesys_data_table_row(architect_api, GENESYS_DATA_TABLE_ID, email):
                    added_count += 1
                    time.sleep(RATE_LIMIT_DELAY)  # Respect rate limits
            except Exception as e:
                logger.error(f"Failed to add email {email}: {str(e)}")
                
        logger.info(f"Successfully added {added_count} new emails to blacklist")
        logger.info(f"Skipped {skipped_count} already blacklisted emails")
        
        # 7. Save the new last run timestamp
        if current_newest_ts > last_run_ts:
            save_last_run_timestamp(current_newest_ts)
            logger.info(f"Updated last run timestamp to: {current_newest_ts}")
            
    except Exception as e:
        logger.error(f"Fatal error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main()
