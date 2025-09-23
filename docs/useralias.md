# useralias

**File:** `useralias.py`

**Complexity:** Medium

---

## Overview

This module provides functionality for useralias.
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

### setup_genesys_client

Initialize and return the Genesys Cloud API client.

**Parameters:** region, client_id, client_secret

### get_division_users

Retrieve all users from the specified division.

**Parameters:** users_api, division_id

### update_user_names

Update user names to match their first names if different.

**Parameters:** users_api, users

### main



---

*This documentation was automatically generated using GitHub Copilot.*
