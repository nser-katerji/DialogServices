import os
import re
import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import PureCloudPlatformClientV2

# --- Configuration (will be loaded from environment variables in GitHub Actions) ---
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID") # e.g., 'C1234567890'

GENESYS_CLIENT_ID = os.environ.get("GENESYS_CLIENT_ID")
GENESYS_CLIENT_SECRET = os.environ.get("GENESYS_CLIENT_SECRET")
GENESYS_REGION = os.environ.get("GENESYS_REGION", "us_east_1") # e.g., us_east_1, eu_west_1 etc.
GENESYS_DATA_TABLE_ID = os.environ.get("GENESYS_DATA_TABLE_ID")

LAST_RUN_TIMESTAMP_FILE = "last_run_timestamp.txt" # For local testing, in GitHub Actions, you might use artifacts or a different persistence method.

def get_last_run_timestamp():
    if os.path.exists(LAST_RUN_TIMESTAMP_FILE):
        with open(LAST_RUN_TIMESTAMP_FILE, 'r') as f:
            return float(f.read().strip())
    return 0 # Start from beginning if no timestamp found

def save_last_run_timestamp(timestamp):
    with open(LAST_RUN_TIMESTAMP_FILE, 'w') as f:
        f.write(str(timestamp))

def get_slack_emails(client, channel_id, oldest_timestamp):
    emails = set()
    try:
        # Fetch messages since the last run
        response = client.conversations_history(
            channel=channel_id,
            oldest=oldest_timestamp,
            limit=100 # Adjust as needed
        )
        messages = response["messages"]
        newest_timestamp = oldest_timestamp

        for msg in messages:
            if "text" in msg:
                # Regex to find email addresses
                found_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', msg["text"])
                for email in found_emails:
                    emails.add(email.lower()) # Add in lowercase to avoid duplicates

            # Keep track of the newest message timestamp for the next run
            if float(msg["ts"]) > newest_timestamp:
                newest_timestamp = float(msg["ts"])

        return list(emails), newest_timestamp

    except SlackApiError as e:
        print(f"Error fetching Slack messages: {e}")
        return [], oldest_timestamp

def get_genesys_data_table_rows(api_instance, data_table_id):
    existing_emails = set()
    try:
        # Fetch existing rows from the data table
        # Note: Genesys API might require pagination for large tables
        rows = api_instance.get_architect_datatable_rows(data_table_id, page_size=1000)
        for row in rows.entities:
            # Assuming your data table has a column named 'EmailAddress'
            if 'EmailAddress' in row.properties:
                existing_emails.add(row.properties['EmailAddress'].lower())
        return existing_emails
    except PureCloudPlatformClientV2.rest.ApiException as e:
        print(f"Error fetching Genesys Data Table rows: {e}")
        return set()

def add_genesys_data_table_row(api_instance, data_table_id, email_address):
    try:
        # Create a new row object
        new_row = PureCloudPlatformClientV2.ArchitectDatatableRow()
        new_row.properties = {"EmailAddress": email_address} # Match your column name

        api_instance.add_architect_datatable_row(data_table_id, new_row)
        print(f"Added {email_address} to Genesys Data Table.")
        return True
    except PureCloudPlatformClientV2.rest.ApiException as e:
        print(f"Error adding row to Genesys Data Table: {e}")
        return False

def main():
    # 1. Slack Client
    slack_client = WebClient(token=SLACK_BOT_TOKEN)

    # 2. Genesys Cloud CX API Configuration
    PureCloudPlatformClientV2.configuration.client_id = GENESYS_CLIENT_ID
    PureCloudPlatformClientV2.configuration.client_secret = GENESYS_CLIENT_SECRET
    PureCloudPlatformClientV2.configuration.set_base_path_by_region(GENESYS_REGION)
    api_client = PureCloudPlatformClientV2.api_client.ApiClient()
    architect_api = PureCloudPlatformClientV2.ArchitectApi(api_client=api_client)

    # 3. Get last run timestamp
    last_run_ts = get_last_run_timestamp()
    print(f"Last run timestamp: {last_run_ts}")

    # 4. Fetch emails from Slack
    new_emails, current_newest_ts = get_slack_emails(slack_client, SLACK_CHANNEL_ID, last_run_ts)
    print(f"Found {len(new_emails)} new emails from Slack.")

    if not new_emails:
        print("No new emails to process. Exiting.")
        return

    # 5. Get existing emails from Genesys Data Table
    existing_genesys_emails = get_genesys_data_table_rows(architect_api, GENESYS_DATA_TABLE_ID)
    print(f"Found {len(existing_genesys_emails)} existing emails in Genesys Data Table.")

    # 6. Add new emails to Genesys Data Table
    added_count = 0
    for email in new_emails:
        if email not in existing_genesys_emails:
            if add_genesys_data_table_row(architect_api, GENESYS_DATA_TABLE_ID, email):
                added_count += 1
    print(f"Successfully added {added_count} new emails to Genesys Data Table.")

    # 7. Save the new last run timestamp
    save_last_run_timestamp(current_newest_ts)
    print(f"Updated last run timestamp to: {current_newest_ts}")

if __name__ == "__main__":
    main()
