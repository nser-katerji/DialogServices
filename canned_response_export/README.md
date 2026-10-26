# Genesys Cloud canned response exporter

Exports response-management responses to a timestamped CSV in `exports/`. The CSV includes each response's ID, name, type, library names, text content, and the complete API response as JSON. Both exporters support organization-specific OAuth credentials and regions; the default region is `mypurecloud.de`.

## Requirements

- Python 3.9 or later
- A Genesys Cloud OAuth client using the client-credentials grant
- The OAuth client must have permission to view response libraries and responses. Its roles must also grant access to the divisions containing the responses.

## Configure and run

From the `Dialog` folder, activate the existing virtual environment and set the credentials in your terminal session:

```zsh
source .venv/bin/activate
export GENESYS_CLIENT_ID='your-client-id'
export GENESYS_CLIENT_SECRET='your-client-secret'
export GENESYS_REGION_DOMAIN='mypurecloud.de'
python canned_response_export/export_canned_responses.py
```

The script does not save credentials. Each run creates a new CSV under `canned_response_export/exports/`. Keep exported files private because they may contain internal response content.

To export only libraries for a country, run:

```zsh
python canned_response_export/export_country_canned_responses.py SE
```

## GitHub Actions

The repository root is `Dialog`, so the workflow is located at `.github/workflows/export-canned-responses.yml` relative to that folder. Push the scripts and workflow to a private GitHub repository. The workflow must exist on the default branch for the manual Run workflow button to appear. Do not commit credentials, your `.venv`, or exported CSVs.

For every Genesys organization, create a GitHub Environment under **Settings > Environments**, for example `genesys-production` or `genesys-test`. Configure each environment with:

| Setting | Kind | Value |
| --- | --- | --- |
| `GENESYS_CLIENT_ID` | Environment secret | OAuth client ID for this organization |
| `GENESYS_CLIENT_SECRET` | Environment secret | OAuth client secret for this organization |
| `GENESYS_REGION_DOMAIN` | Environment variable | Region domain, e.g. `mypurecloud.de`, `mypurecloud.com`, or `mypurecloud.com.au` |

Use only the region domain, without `https://`, `api.`, `login.`, paths, or a trailing slash. It is the organization's Genesys region, not its organization name. Each OAuth client needs `responses:library:view` and `responses:response:view`, with access to the relevant divisions. Missing permissions can prevent exports or limit their coverage.

To run an export:

1. Open **Actions > Export Genesys canned responses > Run workflow**.
2. Select the organization environment.
3. Select `all` to run the full exporter, or `country` and supply a country code such as `SE`, `AT`, `AU`, or `NL`.
4. After success, download the CSV from the run's **Artifacts** section. Artifacts expire after seven days and are not committed to the repository.

The workflow uses Python 3.12 and the standard library, so no dependency installation is needed. It fails if credentials or the region variable are missing. A country export also fails if the country code is invalid or no matching libraries are found. Only successful exports are uploaded.

Restrict repository and artifact access because responses can contain internal content. Consider environment approvals and deployment branch restrictions for production organizations. Anyone allowed to edit and run workflow code against an environment can potentially access its secrets; configure the repository and environment permissions accordingly.

If a client secret was previously hard-coded or committed, rotate it in Genesys Cloud before configuring these secrets. Removing it from the current scripts does not remove it from Git history.