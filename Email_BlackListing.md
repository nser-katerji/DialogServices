# Email Blacklist Solution Design

## System Architecture

```mermaid
graph TD
    subgraph "GitHub Actions Workflow"
        A[GitHub Action Trigger] -->|Every 4 hours| B[Python Script]
        M[Manual Trigger] -->|On-demand| B
    end

    subgraph "External Services"
        C[Slack Channel] -->|Read Messages| B
        B -->|Update| D[Genesys Cloud Data Table]
    end

    subgraph "Data Flow"
        B -->|1. Read| E[last_run_timestamp.txt]
        B -->|2. Fetch New Messages| C
        B -->|3. Extract Emails| F[Email Processing]
        F -->|4. Validate & Normalize| G[Email Validation]
        B -->|5. Check Existing| D
        B -->|6. Add New Emails| D
        B -->|7. Save Timestamp| E
    end

    subgraph "Persistence"
        E -->|Store as Artifact| H[GitHub Artifacts]
        H -->|Restore Next Run| E
    end
```

## Component Details

```mermaid
classDiagram
    class GitHubAction {
        +schedule: "0 */4 * * *"
        +workflow_dispatch
        +setup_python()
        +install_dependencies()
        +run_script()
        +handle_artifacts()
    }

    class BlacklistUpdater {
        +SLACK_BOT_TOKEN
        +SLACK_CHANNEL_ID
        +GENESYS_CONFIG
        +main()
        -check_slack_scopes()
        -get_slack_messages()
        -get_slack_emails()
        -get_genesys_data_table_rows()
        -add_genesys_data_table_row()
    }

    class SlackIntegration {
        +required_scopes
        +WebClient
        +conversations_history()
        +auth_test()
        +bots_info()
    }

    class GenesysIntegration {
        +Configuration
        +ApiClient
        +ArchitectApi
        +get_architect_datatable_rows()
        +add_architect_datatable_row()
    }

    class EmailProcessor {
        +validate_email()
        +normalize_email()
        +extract_from_message()
    }

    GitHubAction --> BlacklistUpdater
    BlacklistUpdater --> SlackIntegration
    BlacklistUpdater --> GenesysIntegration
    BlacklistUpdater --> EmailProcessor
```

## Security and Authentication Flow

```mermaid
sequenceDiagram
    participant GH as GitHub Actions
    participant Script as Python Script
    participant Slack as Slack API
    participant Genesys as Genesys Cloud

    GH->>Script: Load Environment Secrets
    
    Script->>Slack: Initialize WebClient with Bot Token
    activate Slack
    Slack-->>Script: Verify Token & Scopes
    deactivate Slack
    
    Script->>Genesys: Initialize with Client ID/Secret
    activate Genesys
    Genesys-->>Script: Authenticate API Client
    deactivate Genesys
    
    loop Every 4 Hours
        Script->>Slack: Fetch Channel Messages
        activate Slack
        Slack-->>Script: Return Messages
        deactivate Slack
        
        Script->>Script: Extract & Validate Emails
        
        Script->>Genesys: Check Existing Blacklist
        activate Genesys
        Genesys-->>Script: Return Current Entries
        deactivate Genesys
        
        Script->>Genesys: Add New Entries
        activate Genesys
        Genesys-->>Script: Confirm Updates
        deactivate Genesys
    end
```

## Error Handling and Retry Logic

```mermaid
stateDiagram-v2
    [*] --> CheckEnvironment
    CheckEnvironment --> InitializeClients: Success
    CheckEnvironment --> FailAndExit: Missing Variables
    
    InitializeClients --> CheckPermissions: Success
    InitializeClients --> RetryInitialization: Error
    RetryInitialization --> InitializeClients: Retry
    RetryInitialization --> FailAndExit: Max Retries
    
    CheckPermissions --> FetchMessages: Success
    CheckPermissions --> UpdatePermissions: Missing Scopes
    UpdatePermissions --> [*]
    
    FetchMessages --> ProcessEmails: Success
    FetchMessages --> RetryFetch: Rate Limited
    RetryFetch --> FetchMessages: Wait
    
    ProcessEmails --> UpdateBlacklist: Valid Emails
    ProcessEmails --> LogInvalid: Invalid Emails
    
    UpdateBlacklist --> SaveProgress: Success
    UpdateBlacklist --> RetryUpdate: API Error
    RetryUpdate --> UpdateBlacklist: Retry
    RetryUpdate --> LogErrors: Max Retries
    
    SaveProgress --> [*]
    LogErrors --> [*]
    LogInvalid --> [*]
    FailAndExit --> [*]
```

## Environment Configuration

Required environment variables and their purposes:

| Variable | Purpose | Service |
|----------|---------|----------|
| SLACK_BOT_TOKEN | Authentication token for Slack API | Slack |
| SLACK_CHANNEL_ID | Channel to monitor for email addresses | Slack |
| GENESYS_CLIENT_ID | Client ID for Genesys Cloud API | Genesys |
| GENESYS_CLIENT_SECRET | Client Secret for Genesys Cloud API | Genesys |
| GENESYS_REGION | Genesys Cloud region (e.g., us_east_1) | Genesys |
| GENESYS_DATA_TABLE_ID | ID of the blacklist data table | Genesys |

## Required Slack Bot Permissions

- channels:history
- channels:read

## Genesys Cloud Requirements

- Data Table Structure:
  - EmailAddress (String, Primary)
  - DateAdded (DateTime)
  
- API Permissions:
  - Architect > dataTables > GET, POST
  - Architect > dataTables > rows > GET, POST
