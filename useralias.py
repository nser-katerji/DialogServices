import os
import logging
import argparse
import PureCloudPlatformClientV2
from PureCloudPlatformClientV2.rest import ApiException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_env_or_fail(var_name):
    value = os.environ.get(var_name)
    if not value:
        logger.error(f"Environment variable {var_name} is required but not set.")
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value

def parse_args():
    parser = argparse.ArgumentParser(description="Update Genesys Cloud agent profile names to first name only.")
    parser.add_argument('--division-id', type=str, help='Genesys Cloud Division ID')
    parser.add_argument('--region', type=str, help='Genesys Cloud region (e.g. mypurecloud.de)')
    return parser.parse_args()

def setup_genesys_client(region, client_id, client_secret):
    """Initialize and return the Genesys Cloud API client."""
    try:
        PureCloudPlatformClientV2.configuration.host = f'https://api.{region}'
        api_client = PureCloudPlatformClientV2.api_client.ApiClient().get_client_credentials_token(
            client_id, client_secret)
        return PureCloudPlatformClientV2.UsersApi(api_client)
    except Exception as e:
        logger.error(f"Failed to initialize Genesys Cloud client: {e}")
        raise

def get_division_users(users_api, division_id):
    """Retrieve all users from the specified division."""
    users = []
    page_number = 1
    page_size = 100

    try:
        while True:
            response = users_api.get_users(
                page_size=page_size,
                page_number=page_number
            )
            users.extend(response.entities)
            if len(response.entities) < page_size:
                break
            page_number += 1

        # Filter users by division in Python
        filtered_users = [user for user in users if getattr(user, 'division', None) and getattr(user.division, 'id', None) == division_id]
        logger.info(f"Found {len(filtered_users)} users in division {division_id}")
        return filtered_users
    except ApiException as e:
        logger.error(f"Failed to retrieve users: {e}")
        raise

def update_user_names(users_api, users):
    """Update user names to match their first names if different."""
    updated_count = 0
    error_count = 0

    for user in users:
        # Extract first name from the full name (first word)
        if not user.name or not isinstance(user.name, str) or user.name.strip() == "":
            logger.warning(f"Skipping user {getattr(user, 'id', 'unknown')}: No name available")
            continue

        first_name = user.name.strip().split()[0]

        if user.name == first_name:
            logger.debug(f"Skipping user {user.id}: Name already matches first name")
            continue

        try:
            update = PureCloudPlatformClientV2.User()
            update.preferred_name = first_name  # Only update the agent profile name
            update.version = user.version  # Required by Genesys API
            users_api.patch_user(user.id, update)
            logger.info(f"Updated user {user.id}: preferred_name set to '{first_name}'")
            updated_count += 1
        except ApiException as e:
            logger.error(f"Failed to update user {user.id}: {e}")
            error_count += 1

    return updated_count, error_count


def main():
    args = parse_args()
    # Read secrets from environment variables (set as GitHub Actions secrets)
    client_id = get_env_or_fail('GENESYS_CLIENT_ID')
    client_secret = get_env_or_fail('GENESYS_CLIENT_SECRET')
    # Division and region from args or env
    division_id = args.division_id or os.environ.get('GENESYS_DIVISION_ID')
    region = args.region or os.environ.get('GENESYS_REGION')
    if not division_id:
        logger.error('Division ID must be provided as --division-id or GENESYS_DIVISION_ID env variable.')
        raise RuntimeError('Missing Division ID')
    if not region:
        logger.error('Region must be provided as --region or GENESYS_REGION env variable.')
        raise RuntimeError('Missing Region')

    try:
        users_api = setup_genesys_client(region, client_id, client_secret)
        users = get_division_users(users_api, division_id)
        updated_count, error_count = update_user_names(users_api, users)
        logger.info(f"Process completed. Updated {updated_count} users. Errors: {error_count}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    main()
