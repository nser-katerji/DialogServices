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
    parser = argparse.ArgumentParser(description="List Genesys Cloud users with empty or mismatched preferred names.")
    parser.add_argument('--region', type=str, help='Genesys Cloud region (e.g. mypurecloud.de)')
    parser.add_argument('--specific-division', type=str, help='Optional: Process only a specific division ID')
    parser.add_argument('--output-file', type=str, help='Optional: Output results to a file')
    return parser.parse_args()

def get_all_divisions(api_client):
    """Retrieve all divisions from Genesys Cloud."""
    try:
        auth_api = PureCloudPlatformClientV2.AuthorizationApi(api_client)
        divisions = []
        page_size = 100
        page_number = 1

        while True:
            response = auth_api.get_authorization_divisions(
                page_size=page_size,
                page_number=page_number
            )
            divisions.extend(response.entities)
            
            if len(response.entities) < page_size:
                break
            page_number += 1

        logger.info(f"Found {len(divisions)} divisions")
        return divisions
    except ApiException as e:
        logger.error(f"Failed to retrieve divisions: {e}")
        raise

def setup_genesys_client(region, client_id, client_secret):
    """Initialize and return the Genesys Cloud API client."""
    try:
        # Set the environment first
        PureCloudPlatformClientV2.configuration.host = f"https://api.{region}"
        
        # Create API client and authenticate
        api_client = PureCloudPlatformClientV2.api_client.ApiClient().get_client_credentials_token(client_id, client_secret)
        
        # Return the Users API instance
        return PureCloudPlatformClientV2.UsersApi(api_client)
    except ApiException as e:
        logger.error(f"Failed to initialize Genesys Cloud client: {str(e.body)}")
        raise
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

def check_user_names(users):
    """Check for users with empty or mismatched preferred names."""
    mismatched_users = []

    for user in users:
        if not user.name or not isinstance(user.name, str) or user.name.strip() == '':
            logger.warning(f"Skipping user {getattr(user, 'id', 'unknown')}: No full name available")
            continue

        first_name = user.name.strip().split()[0]
        preferred_name = getattr(user, 'preferred_name', None)

        # Check if preferred_name is empty or doesn't match first name
        if not preferred_name or preferred_name.strip() != first_name:
            user_info = {
                'id': user.id,
                'full_name': user.name,
                'first_name': first_name,
                'preferred_name': preferred_name if preferred_name else 'Empty',
                'email': getattr(user, 'email', 'No email'),
                'division': getattr(user.division, 'name', 'Unknown Division')
            }
            mismatched_users.append(user_info)

    return mismatched_users

def process_division(users_api, division, results):
    """Process all users in a specific division."""
    try:
        logger.info(f"\nProcessing Division: {division.name} (ID: {division.id})")
        users = get_division_users(users_api, division.id)
        
        if not users:
            logger.info(f"No users found in division {division.name}")
            return
        
        mismatched_users = check_user_names(users)
        results.extend(mismatched_users)
        
        logger.info(f"Found {len(mismatched_users)} users with mismatched names in division {division.name}")
        
    except Exception as e:
        logger.error(f"Error processing division {division.name}: {e}")

def write_results_to_file(results, filename):
    """Write results to a file in a formatted way."""
    try:
        with open(filename, 'w') as f:
            f.write("Users with Empty or Mismatched Preferred Names\n")
            f.write("===========================================\n\n")
            for user in results:
                f.write(f"User ID: {user['id']}\n")
                f.write(f"Full Name: {user['full_name']}\n")
                f.write(f"First Name: {user['first_name']}\n")
                f.write(f"Preferred Name: {user['preferred_name']}\n")
                f.write(f"Email: {user['email']}\n")
                f.write(f"Division: {user['division']}\n")
                f.write("-------------------------------------------\n")
        logger.info(f"Results written to {filename}")
    except Exception as e:
        logger.error(f"Failed to write results to file: {e}")

def main():
    args = parse_args()
    # Use hardcoded values for local testing
    client_id = get_env_or_fail('CLIENT_ID')
    client_secret = get_env_or_fail('CLIENT_SECRET')
    region = args.region or os.environ.get('GENESYS_REGION')
    
    if not region:
        logger.error('Region must be provided as --region or GENESYS_REGION env variable.')
        raise RuntimeError('Missing Region')

    try:
        # Initialize results list
        all_results = []

        # Set up API client
        users_api = setup_genesys_client(region, client_id, client_secret)
        logger.info("Successfully authenticated with Genesys Cloud")

        # Get all divisions or process specific division
        if args.specific_division:
            divisions = [type('Division', (), {
                'id': args.specific_division, 
                'name': f"Division {args.specific_division}"
            })]
            logger.info(f"Processing specific division: {args.specific_division}")
        else:
            divisions = get_all_divisions(users_api.api_client)
            logger.info(f"Found {len(divisions)} divisions to process")

        # Process each division
        for i, division in enumerate(divisions, 1):
            logger.info(f"\nProcessing division {i} of {len(divisions)}")
            process_division(users_api, division, all_results)

        # Print summary
        logger.info("\n=== Summary ===")
        logger.info(f"Total divisions processed: {len(divisions)}")
        logger.info(f"Total users with mismatched names: {len(all_results)}")

        # Print or save detailed results
        if args.output_file:
            write_results_to_file(all_results, args.output_file)
        else:
            logger.info("\n=== Detailed Results ===")
            for user in all_results:
                logger.info(f"\nUser ID: {user['id']}")
                logger.info(f"Full Name: {user['full_name']}")
                logger.info(f"First Name: {user['first_name']}")
                logger.info(f"Preferred Name: {user['preferred_name']}")
                logger.info(f"Email: {user['email']}")
                logger.info(f"Division: {user['division']}")

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    main()
