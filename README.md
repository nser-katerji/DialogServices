# Genesys Cloud Profile Name Updater - Logic Flow

## Process Flow Diagram
```mermaid
flowchart TD
    Start([Start]) --> Init[Initialize Script]
    Init --> CheckEnv{Check Environment Variables}
    
    CheckEnv -->|Missing| Error1[Show Error: Missing Credentials]
    Error1 --> End([End])
    
    CheckEnv -->|Present| ParseArgs[Parse Command Line Arguments]
    ParseArgs --> ValidateInput{Validate Region & Division}
    
    ValidateInput -->|Invalid| Error2[Show Error: Invalid Input]
    Error2 --> End
    
    ValidateInput -->|Valid| ConnectAPI[Connect to Genesys Cloud API]
    ConnectAPI --> FetchUsers[Fetch Users with Pagination]
    
    FetchUsers --> FilterDivision[Filter Users by Division]
    FilterDivision --> ProcessUsers[Process Each User]
    
    ProcessUsers --> UserLoop{For Each User}
    UserLoop --> CheckName{Check Full Name}
    
    CheckName -->|Invalid/Empty| SkipUser1[Skip User]
    CheckName -->|Valid| ExtractFirst[Extract First Name]
    
    ExtractFirst --> CheckPreferred{Check Preferred Name}
    CheckPreferred -->|Matches First Name| SkipUser2[Skip User]
    CheckPreferred -->|Different/Not Set| UpdateUser[Update User Profile]
    
    UpdateUser --> UpdateResult{Update Result}
    UpdateResult -->|Success| IncrementSuccess[Increment Success Count]
    UpdateResult -->|Failure| IncrementError[Increment Error Count]
    
    IncrementSuccess --> NextUser[Next User]
    IncrementError --> NextUser
    SkipUser1 --> NextUser
    SkipUser2 --> NextUser
    
    NextUser --> UserLoop
    
    UserLoop -->|All Users Processed| ShowSummary[Show Summary]
    ShowSummary --> End

    classDef process fill:#90caf9,stroke:#1565c0,stroke-width:2px;
    classDef decision fill:#ffb74d,stroke:#f57c00,stroke-width:2px;
    classDef error fill:#ef5350,stroke:#c62828,stroke-width:2px;
    classDef success fill:#81c784,stroke:#2e7d32,stroke-width:2px;
    
    class Init,FetchUsers,FilterDivision,ProcessUsers,UpdateUser,ShowSummary process;
    class CheckEnv,ValidateInput,CheckName,CheckPreferred,UpdateResult decision;
    class Error1,Error2,IncrementError error;
    class IncrementSuccess success;
```

## Key Components

1. **Initialization**
   - Load environment variables
   - Parse command-line arguments
   - Validate required inputs

2. **API Connection**
   - Connect to Genesys Cloud
   - Authenticate using client credentials

3. **User Fetching**
   - Fetch users with pagination
   - Filter users by specified division

4. **User Processing**
   For each user:
   - Validate full name
   - Extract first name
   - Check current preferred name
   - Update if necessary

5. **Error Handling**
   - Environment variables missing
   - API connection failures
   - Invalid user data
   - Update failures

6. **Summary**
   - Total users processed
   - Successful updates
   - Skipped users
   - Errors encountered

## Environment Requirements

- `GENESYS_CLIENT_ID`
- `GENESYS_CLIENT_SECRET`
- `GENESYS_DIVISION_ID` (optional if provided via CLI)
- `GENESYS_REGION` (optional if provided via CLI)

## Command Line Arguments

- `--division-id`: Genesys Cloud Division ID
- `--region`: Genesys Cloud region (e.g., mypurecloud.de)
