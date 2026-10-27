# export_canned_responses

**File:** `canned_response_export/export_canned_responses.py`

**Complexity:** Medium

---

## Overview

Export Genesys Cloud response-management responses to CSV.
## Dependencies

- `base64`
- `csv`
- `json`
- `os`
- `sys`
- `datetime.datetime`
- `datetime.timezone`
- `pathlib.Path`
- `urllib.error.HTTPError`
- `urllib.error.URLError`

## Functions

### request_json

**Parameters:** url

### get_access_token

**Parameters:** client_id, client_secret

### get_page

**Parameters:** path, token, page_number

### get_all_pages

**Parameters:** path, token

### collect_responses

**Parameters:** token

### write_csv

**Parameters:** responses_by_id

### main



---

*This documentation was automatically generated using GitHub Copilot.*
