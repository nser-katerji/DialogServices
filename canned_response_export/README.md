# Genesys Cloud canned response exporter

Exports response-management responses to a timestamped CSV in `exports/`. The CSV includes each response's ID, name, type, library names, text content, and the complete API response as JSON. Both exporters support organization-specific OAuth credentials and regions; the default region is `mypurecloud.de`.

## Requirements

- Python 3.9 or later
- A Genesys Cloud OAuth client using the client-credentials grant
- The OAuth client must have permission to view response libraries and responses. Its roles must also grant access to the divisions containing the responses.

## Configure and run

From the `Dialog` folder, activate the existing virtual environment and set the credentials in your terminal session. The exporters use the same `CLIENT_ID`, `CLIENT_SECRET`, and `GENESYS_REGION` names as the other Genesys scripts. Existing `GENESYS_CLIENT_ID`, `GENESYS_CLIENT_SECRET`, and `GENESYS_REGION_DOMAIN` variables remain supported for compatibility.

```zsh
source .venv/bin/activate
export CLIENT_ID='your-client-id'
export CLIENT_SECRET='your-client-secret'
export GENESYS_REGION='mypurecloud.de'
python canned_response_export/export_canned_responses.py
```

The script does not save credentials. Each run creates a new CSV under `canned_response_export/exports/`. Keep exported files private because they may contain internal response content.

To export only libraries for a country, run:

```zsh
python canned_response_export/export_country_canned_responses.py SE
```

## GitHub Actions

The repository root is `Dialog`, so the workflow is located at `.github/workflows/export-canned-responses.yml` relative to that folder. Push the scripts and workflow to a private GitHub repository. The workflow must exist on the default branch for the manual Run workflow button to appear. Do not commit credentials, your `.venv`, or exported CSVs.

Configure these repository secrets under **Settings > Secrets and variables > Actions**:

| Setting | Kind | Value |
| --- | --- | --- |
| `CLIENT_ID` | Repository secret | OAuth client ID |
| `CLIENT_SECRET` | Repository secret | OAuth client secret |

The repository-level secrets provide one credential pair for this repository. At dispatch, enter the matching Genesys region domain without `https://`, `api.`, `login.`, paths, or a trailing slash (for example `mypurecloud.de`, `mypurecloud.com`, or `mypurecloud.com.au`). Each OAuth client needs `responses:library:view` and `responses:response:view`, with access to the relevant divisions. Missing permissions can prevent exports or limit their coverage.

To run an export:

1. Open **Actions > Export Genesys canned responses > Run workflow**.
2. Enter the Genesys region domain for the configured credentials.
3. Select `all` to run the full exporter, or `country` and supply a country code such as `SE`, `AT`, `AU`, or `NL`.
4. After success, download the CSV from the run's **Artifacts** section. Artifacts expire after seven days and are not committed to the repository.

The workflow uses Python 3.12 and the standard library, so no dependency installation is needed. It fails if credentials or the region domain are missing. A country export also fails if the country code is invalid or no matching libraries are found. Only successful exports are uploaded.

Restrict repository and artifact access because responses can contain internal content. Anyone allowed to edit and run workflow code in the repository can potentially access its secrets; configure repository permissions accordingly.

If a client secret was previously hard-coded or committed, rotate it in Genesys Cloud before configuring these secrets. Removing it from the current scripts does not remove it from Git history.
