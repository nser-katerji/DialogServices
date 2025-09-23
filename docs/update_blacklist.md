# update_blacklist

**File:** `update_blacklist.py`

**Complexity:** Medium

---

## Overview

This module provides functionality for update blacklist.
## Dependencies

- `os`
- `re`
- `time`
- `logging`
- `datetime`
- `typing.Set`
- `typing.List`
- `typing.Tuple`
- `slack_sdk.WebClient`
- `slack_sdk.errors.SlackApiError`

## Functions

### get_required_env_var

**Parameters:** var_name

### get_last_run_timestamp

### save_last_run_timestamp

**Parameters:** timestamp

### validate_and_normalize_email

Validate email and return normalized form.

**Parameters:** email

### check_slack_scopes

Check if the bot has the required scopes.

**Parameters:** client

### get_slack_messages

Fetch messages from Slack with pagination support.

**Parameters:** client, channel_id, oldest_timestamp

### get_slack_emails

Extract validated emails from Slack messages.

**Parameters:** client, channel_id, oldest_timestamp

### get_genesys_data_table_rows

Fetch all existing blacklisted emails from Genesys data table with pagination.

**Parameters:** api_instance, data_table_id

### add_genesys_data_table_row

Add a new email to the Genesys blacklist data table.

**Parameters:** api_instance, data_table_id, email_address

### main

Main execution function.



---

*This documentation was automatically generated using GitHub Copilot.*
