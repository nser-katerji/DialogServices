# export_country_canned_responses

**File:** `canned_response_export/export_country_canned_responses.py`

**Complexity:** Medium

---

## Overview

Export Genesys Cloud canned responses from libraries belonging to one country.
## Dependencies

- `argparse`
- `base64`
- `csv`
- `json`
- `os`
- `re`
- `sys`
- `datetime.datetime`
- `datetime.timezone`
- `pathlib.Path`

## Functions

### word_pattern

**Parameters:** text

### build_library_matcher

**Parameters:** country_code

### request_json

**Parameters:** url

### get_access_token

**Parameters:** client_id, client_secret

### get_all_pages

**Parameters:** path, token, params

### collect_responses

**Parameters:** token, libraries

### write_csv

**Parameters:** country_code, responses_by_id

### main

### matches

**Parameters:** library_name



---

*This documentation was automatically generated using GitHub Copilot.*
