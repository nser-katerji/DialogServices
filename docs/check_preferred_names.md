# check_preferred_names

**File:** `check_preferred_names.py`

**Complexity:** Medium

---

## Overview

This module provides functionality for check preferred names.
## Dependencies

- `os`
- `logging`
- `argparse`
- `PureCloudPlatformClientV2`
- `PureCloudPlatformClientV2.rest.ApiException`

## Functions

### get_env_or_fail

**Parameters:** var_name

### parse_args

### get_all_divisions

Retrieve all divisions from Genesys Cloud.

**Parameters:** api_client

### setup_genesys_client

Initialize and return the Genesys Cloud API client.

**Parameters:** region, client_id, client_secret

### get_division_users

Retrieve all users from the specified division.

**Parameters:** users_api, division_id

### check_user_names

Check for users with empty or mismatched preferred names.

**Parameters:** users

### process_division

Process all users in a specific division.

**Parameters:** users_api, division, results

### write_results_to_file

Write results to a file in a formatted way.

**Parameters:** results, filename

### main



---

*This documentation was automatically generated using GitHub Copilot.*
