# Logic App Migration Guide

## Overview

The Azure DevOps CLI Tool has been refactored to use Azure Logic App (Fabric Data Warehouse) as the primary source for work item data. This replaces the previous WIQL/Analytics API approach.

## What Changed

### Before (Legacy)
- Used Azure DevOps WIQL queries to fetch work items
- Required project discovery and complex filtering logic
- Multiple API calls for work item details
- Flags: `--optimized`, `--ultra-optimized`, `--all-projects`, `--project-names`, etc.

### After (Current)
- Uses Azure Logic App with Fabric Data Warehouse as single source
- Simplified workflow: date range + emails → work items
- Direct work item data with estimates from warehouse
- Required flags: `--start-date`, `--end-date`
- Optional: `--assigned-to` (names or emails)

## New Workflow

### 1. Setup

**Create `.env` file:**
```bash
cp .env.example .env
```

**Edit `.env` and set:**
```bash
AZURE_LOGIC_APP_URL=https://prod-xx.region.logic.azure.com:443/workflows/YOUR_WORKFLOW_ID/...
```

**Verify `user_email_mapping.json` exists:**
```json
{
    "Carlos Vazquez": "carlos.vazquez@inbest.cloud",
    "Diego Lopez": "diego.lopez@inbest.cloud"
}
```

### 2. Query Work Items

**Basic usage (all users):**
```bash
python run.py --query-work-items \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --export-csv reports/october.csv
```

**Specific users by name:**
```bash
python run.py --query-work-items \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --assigned-to "Carlos Vazquez,Diego Lopez"
```

**Specific users by email:**
```bash
python run.py --query-work-items \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --assigned-to "carlos.vazquez@inbest.cloud"
```

**Without efficiency calculations (faster):**
```bash
python run.py --query-work-items \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --no-efficiency
```

## Architecture

### High-Level Flow

```
1. CLI parses arguments (--start-date, --end-date, --assigned-to)
2. Resolve user names → emails using user_email_mapping.json
3. Call Logic App with POST: {fromDate, toDate, emails[]}
4. Parse ResultSets.Table1 → work items list
5. For each work item: fetch DevOps activity log (revisions)
6. Calculate productivity time using existing efficiency calculator
7. Generate CSVs and terminal summaries
```

### Data Flow

```
Logic App (Fabric) → ResultSets.Table1
    ↓
[{WorkItemId, AssignedToUser, Title, StartDate, TargetDate, OriginalEstimate}]
    ↓
Deduplicate by (WorkItemId, AssignedToUser)
    ↓
For each work item: Fetch Azure DevOps activity log
    ↓
Calculate efficiency metrics (active time, fair efficiency, delivery score)
    ↓
Generate KPIs and export CSVs
```

### Components

#### 1. Logic App Client (`helpers/logic_app_client.py`)
- HTTP POST to Logic App
- Retry logic with exponential backoff (3 attempts)
- 60s timeout
- Request format: `{fromDate, toDate, emails[]}`
- Response format: `{ResultSets: {Table1: [...]}}`

#### 2. Email Resolution (`helpers/email_mapping.py`)
- Load `user_email_mapping.json`
- Resolve names → emails
- Support direct email input
- Warn about unknown names

#### 3. Timezone Utilities (`helpers/timezone_utils.py`)
- Convert dates to America/Mexico_City timezone
- Date range: `from_date 00:00:00` to `to_date 23:59:59` (Mexico City)
- DevOps timestamps (UTC) converted for comparison

#### 4. Work Item Processing (`classes/WorkItemOperations.py`)
- `get_work_items_from_logic_app()`: Main entry point
- `_process_logic_app_work_items()`: Deduplicate and standardize
- `_fetch_activity_logs_and_calculate_efficiency()`: Get revisions and calculate metrics
- Reuses existing efficiency calculator logic

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_DEVOPS_ORG` | Yes | Azure DevOps organization name |
| `AZURE_DEVOPS_PAT` | Yes | Personal access token |
| `AZURE_LOGIC_APP_URL` | **Yes** | Logic App HTTP trigger URL |

### Configuration Files

| File | Required | Description |
|------|----------|-------------|
| `user_email_mapping.json` | **Yes** | Name-to-email mapping for user resolution |
| `config/azure_devops_config.json` | Yes | Efficiency scoring configuration |

## Logic App Contract

### Request Format

```json
{
  "fromDate": "YYYY-MM-DD",
  "toDate": "YYYY-MM-DD",
  "emails": ["user1@domain.com", "user2@domain.com"]
}
```

### Response Format

```json
{
  "ResultSets": {
    "Table1": [
      {
        "WorkItemId": 42964,
        "AssignedToUser": "Carlos Vazquez",
        "Title": "Implement feature X",
        "StartDate": "2025-10-01T00:00:00Z",
        "TargetDate": "2025-10-15T00:00:00Z",
        "OriginalEstimate": 8.0
      }
    ]
  }
}
```

**Alternative format (body-wrapped):**
```json
{
  "body": {
    "ResultSets": {
      "Table1": [...]
    }
  }
}
```

## Error Handling

### Missing Logic App URL
```
❌ Missing AZURE_LOGIC_APP_URL environment variable.
Please add your Logic App URL to the .env file:
AZURE_LOGIC_APP_URL=https://prod-xx.region.logic.azure.com:443/...
```

### Missing Date Arguments
```
❌ Error: --start-date and --end-date are required for Logic App flow
   Example: --start-date 2025-10-01 --end-date 2025-10-31
```

### Unknown User Names
```
⚠️  Could not resolve 2 name(s): John Doe, Jane Smith
   Available names in user_email_mapping.json: Carlos Vazquez, Diego Lopez, ...
```

### Logic App Timeout
```
❌ Failed to fetch work items from Logic App: Request timeout after 60s
Retrying in 2 seconds...
```

## Migration Checklist

- [ ] Set `AZURE_LOGIC_APP_URL` in `.env` file
- [ ] Verify `user_email_mapping.json` contains all required users
- [ ] Update scripts/workflows to use new required flags: `--start-date`, `--end-date`
- [ ] Remove usage of legacy flags: `--optimized`, `--ultra-optimized`, `--project-names`, `--all-projects`
- [ ] Test with sample date range
- [ ] Compare output CSVs with previous runs for sanity check

## Outputs

Same as before:
- **Detailed CSV**: `{filename}_detailed.csv` - All work items with efficiency metrics
- **Developer Summary CSV**: `{filename}_developer_summary.csv` - Per-developer aggregated metrics
- **Terminal output**: KPIs, bottlenecks, work item summaries

## Performance

- **Logic App fetch**: ~2-5s for 100 work items
- **Email resolution**: <0.1s
- **Activity log fetching**: Parallel processing (default: 10 workers)
- **Efficiency calculation**: ~0.1s per work item
- **Total**: ~10-30s for typical monthly query (50-200 work items)

## Troubleshooting

### Issue: "Logic App client not initialized"
**Solution**: Set `AZURE_LOGIC_APP_URL` in `.env` file

### Issue: "No valid emails resolved"
**Solution**: Check `user_email_mapping.json` exists and contains valid mappings

### Issue: "Failed to fetch from Logic App"
**Solution**:
1. Verify Logic App URL is correct
2. Test Logic App with Postman/curl
3. Check network connectivity
4. Review Azure Logic App logs

### Issue: "No work items found"
**Solution**:
1. Verify date range is correct
2. Check user emails are correct
3. Confirm Logic App query returns data for this period

## Legacy Code Removal

The following have been removed:
- `build_wiql_query()` - No longer used
- `execute_wiql_query()` - Replaced by Logic App
- `execute_optimized_wiql_query()` - Replaced by Logic App
- `_execute_organization_wiql_optimized()` - Replaced by Logic App
- Project discovery logic for work item queries
- Analytics API integration
- `--optimized` flag
- `--ultra-optimized` flag
- `--all-projects` flag
- `--project-names` flag
- `--max-projects` flag

These methods and flags are now marked as legacy or removed entirely.

## Support

For issues or questions:
1. Check this migration guide
2. Review error messages and troubleshooting section
3. Verify Logic App response format matches contract
4. Check Azure Logic App run history for failures
