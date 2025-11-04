# Azure DevOps CLI Tool

A powerful command-line utility for Azure DevOps analytics, featuring advanced developer scoring, work item querying, and performance metrics calculation.

## Features

- **Developer Scoring System**: Calculate comprehensive developer performance metrics
- **Advanced Work Item Querying**: Filter and analyze work items across projects
- **Efficiency Metrics**: Fair efficiency calculations with state transition tracking
- **Performance Optimized**: Batch processing with 70-95% speed improvements
- **CSV Export**: Detailed and summary reports for further analysis
- **Service Hook Management**: Create and manage Azure DevOps webhooks
- **Automated Monthly Reports**: GitHub Actions workflow for scheduled report generation

## Installation

### Prerequisites

- Python 3.7+
- Azure DevOps Personal Access Token (PAT)
- Access to Azure DevOps organization

### Setup

1. **Clone the repository**
   ```bash
   cd /path/to/project
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Create a `.env` file in the project root:
   ```plaintext
   AZURE_DEVOPS_ORG=<Your Organization Name>
   AZURE_DEVOPS_PAT=<Your Personal Access Token>
   ```

   To create a PAT:
   - Go to Azure DevOps → User Settings → Personal Access Tokens
   - Create new token with `Work Items: Read` permission
   - Copy the token to your `.env` file

## Quick Start

### List Projects
```bash
python run.py --list-projects
```

### Query Work Items with Developer Scores
```bash
python run.py --query-work-items \
  --assigned-to "Developer Name" \
  --start-date "2025-09-01" \
  --end-date "2025-09-30" \
  --export-csv "results.csv"
```

## Developer Score System

The tool calculates a comprehensive **Overall Developer Score** based on four key metrics:

### Score Components

| Metric | Weight | Description |
|--------|--------|-------------|
| **Fair Efficiency** | 25% | Productivity relative to estimated time |
| **Delivery Score** | 50% | On-time delivery performance (60-130 points) |
| **Completion Rate** | 15% | Percentage of tasks completed |
| **On-Time Delivery** | 10% | Percentage completed within target date |

### Fair Efficiency Calculation

```
Fair Efficiency = (Active Hours + Completion Bonus) / (Estimated Hours + Late Penalty) × 100%
```

**Key Features:**
- Active time capped at 1.2× estimate (prevents over-efficiency bias)
- 20% completion bonus for finished work items
- Paused/blocked time excluded from calculations
- Stack-based state transition tracking

### Delivery Score

**Early Delivery Bonuses:**
- Very early (≥7 days): 130 points + 1.0h bonus
- Early (≥3 days): 120 points + 0.5h bonus
- Slightly early (≥1 day): 110 points + 0.25h bonus
- On-time: 100 points

**Late Delivery Penalties:**
- 1-3 days late: 90 points, 2h penalty mitigation
- 4-7 days late: 80 points, 4h penalty mitigation
- 8-14 days late: 70 points, 6h penalty mitigation
- 15+ days late: 60 points, 8h penalty mitigation

### Score Interpretation

| Overall Score | Level | Action |
|--------------|-------|--------|
| ≥86% | Excellent | Maintain performance |
| 65-85% | Good | Minor improvements |
| 55-64% | Fair | Attention needed |
| <55% | Low | Urgent action required |

## Common Usage Examples

### Basic Developer Query
```bash
python run.py --query-work-items \
  --assigned-to "John Doe" \
  --start-date "2025-10-01" \
  --end-date "2025-10-31"
```

### Multiple Developers with Export
```bash
python run.py --query-work-items \
  --assigned-to "Developer1,Developer2,Developer3" \
  --start-date "2025-09-01" \
  --end-date "2025-09-30" \
  --export-csv "september_results.csv"
```

### High-Performance Query (Optimized)
```bash
python run.py --query-work-items \
  --assigned-to "Developer Name" \
  --all-projects \
  --optimized \
  --max-workers 15 \
  --batch-size 200 \
  --export-csv "fast_results.csv"
```

### Specific Projects Only
```bash
python run.py --query-work-items \
  --project-names "ProjectA,ProjectB" \
  --assigned-to "Developer Name" \
  --export-csv "specific_projects.csv"
```

### Custom Scoring Weights
```bash
python run.py --query-work-items \
  --assigned-to "Developer Name" \
  --fair-efficiency-weight 0.3 \
  --delivery-score-weight 0.4 \
  --completion-rate-weight 0.2 \
  --on-time-delivery-weight 0.1 \
  --export-csv "custom_scoring.csv"
```

### Filter by Work Item Type and State
```bash
python run.py --query-work-items \
  --assigned-to "Developer Name" \
  --work-item-types "Task,Bug" \
  --states "Closed,Done" \
  --date-field "ClosedDate"
```

## Query Options

### Filtering Options

| Option | Description | Example |
|--------|-------------|---------|
| `--assigned-to` | Filter by assigned developers (comma-separated) | `"Dev1,Dev2"` |
| `--project-names` | Specific projects to query | `"ProjectA,ProjectB"` |
| `--all-projects` | Query all projects in organization | Flag only |
| `--work-item-types` | Filter by type | `"Task,Bug,User Story"` |
| `--states` | Filter by work item states | `"Closed,Done,Active"` |
| `--start-date` | Start date for filtering | `"2025-09-01"` |
| `--end-date` | End date for filtering | `"2025-09-30"` |
| `--date-field` | Date field to filter on | `"ClosedDate"` or `"CreatedDate"` |
| `--area-path` | Filter by area path | `"Project\\Area"` |
| `--iteration-path` | Filter by iteration | `"Sprint 1"` |

### Performance Options

| Option | Description | Speed Gain |
|--------|-------------|-----------|
| `--optimized` | Enable batch processing | 70-95% faster |
| `--ultra-optimized` | Bypass project discovery | 80-95% faster |
| `--max-workers` | Parallel worker count (default: 10) | Configurable |
| `--batch-size` | Items per API call (max: 200) | Default: 200 |
| `--no-parallel` | Disable parallel processing | N/A |

### Scoring Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `--completion-bonus` | Completion bonus factor | 0.20 (20%) |
| `--max-efficiency-cap` | Maximum efficiency percentage | 150.0% |
| `--fair-efficiency-weight` | Fair efficiency weight | 0.25 (25%) |
| `--delivery-score-weight` | Delivery score weight | 0.50 (50%) |
| `--completion-rate-weight` | Completion rate weight | 0.15 (15%) |
| `--on-time-delivery-weight` | On-time delivery weight | 0.10 (10%) |

### Export Options

| Option | Description |
|--------|-------------|
| `--export-csv` | Export results to CSV file |
| `--no-efficiency` | Skip efficiency calculations (faster queries) |

## Output Files

The tool generates two types of CSV exports:

### 1. Detailed Results CSV
Contains individual work item details:
- Work item ID, title, type, state
- Assigned developer
- Dates (created, closed, target)
- Time metrics (active hours, estimated hours)
- Efficiency metrics (fair efficiency, delivery score)
- State transition details

### 2. Developer Summary CSV
Contains aggregated metrics per developer:
- Overall Developer Score
- Fair Efficiency percentage
- Average Delivery Score
- Completion Rate
- On-Time Delivery percentage
- Total Active Hours
- Total Estimated Hours
- Work item counts (total, completed, on-time)

### Example Output

```
Developer: Fernando Alcaraz
┌─────────────────────────────────┐
│ Overall Developer Score: 103.78%│
│ Fair Efficiency: 109.43%        │
│ Delivery Score: 108.7           │
│ Completion Rate: 100%           │
│ On-Time Delivery: 74%           │
│ Total Active Hours: 131.19      │
│ Total Estimated Hours: 149      │
│ Work Items: 50 total (50 done)  │
└─────────────────────────────────┘
```

## Configuration

### Configuration Files

The tool uses multiple configuration sources (in order of precedence):

1. **Command-line arguments** (highest priority)
2. **JSON configuration** (`config/azure_devops_config.json`)
3. **Environment variables** (`.env` file)
4. **Code defaults** (lowest priority)

### Key Configuration Sections

Edit `config/azure_devops_config.json` to customize:

- **State Categories**: Define productive, blocked, and completion states
- **Business Hours**: Office hours and timezone settings
- **Scoring Parameters**: Efficiency caps, bonuses, and penalties
- **Work Item Types**: Default types to query
- **Smart Filtering**: Enable/disable intelligent project discovery

## Advanced Features

### Smart Project Discovery

By default, the tool only queries projects where the specified developers have activity:
```bash
# Only queries projects with activity for these users
python run.py --query-work-items --assigned-to "User1,User2"
```

To query all projects:
```bash
python run.py --query-work-items --assigned-to "User1" --all-projects
```

### State Transition Tracking

The tool uses a stack-based algorithm to accurately track:
- Active working time vs. blocked/paused time
- State transitions and their timestamps
- Reopened items with separate tracking
- Business hours enforcement

### Service Hook Management

Create webhooks for Azure DevOps events:
```bash
# Create a work item update webhook
python run.py --create-hook \
  --project-id "<project-id>" \
  --event-type "workitem.updated"

# List all subscriptions
python run.py --list-subscriptions --project-id "<project-id>"

# Create standard hooks (work items, builds, releases)
python run.py --create-standard-hooks --project-id "<project-id>"
```

## Troubleshooting

### Authentication Issues
- Verify your PAT has `Work Items: Read` permission
- Ensure `.env` file is in the project root
- Check organization name is correct (no URL, just the name)

### Performance Issues
- Use `--optimized` flag for large datasets
- Reduce `--max-workers` if hitting API rate limits
- Use `--ultra-optimized` for maximum speed (bypasses smart filtering)

### No Results Returned
- Verify date ranges match work item activity
- Check work item states match your query
- Ensure developers are assigned to work items in the date range
- Try `--all-projects` if smart filtering is too restrictive

## Automated Monthly Reports (GitHub Actions)

### Quick Setup

The repository includes a GitHub Actions workflow that automatically generates developer reports on the 30th of each month.

1. **Configure GitHub Secrets:**
   - Go to **Settings** → **Environments** → **main**
   - Add secrets:
     - `AZURE_DEVOPS_ORG`: Your organization name
     - `AZURE_DEVOPS_PAT`: Your Personal Access Token

2. **Automatic Execution:**
   - Runs on the 30th of each month at 23:00 UTC
   - Generates reports for the 1st-30th of the current month
   - Reports stored as artifacts for 90 days

3. **Manual Execution:**
   - Go to **Actions** → **Monthly Developer Report**
   - Click **Run workflow**
   - Specify custom date range and developers

### Example Manual Run

**Generate September 2025 report:**
```yaml
start_date: 2025-09-01
end_date: 2025-09-30
assigned_to: Developer1,Developer2  # Optional
```

**Output files:**
- `developer_report_2025-09-01_to_2025-09-30.csv`
- `developer_report_2025-09-01_to_2025-09-30_developer_summary.csv`

For complete workflow documentation, see [`.github/workflows/README.md`](.github/workflows/README.md)

## Documentation

For more detailed information, see:

- `.github/workflows/README.md` - GitHub Actions workflow setup and usage
- `documentation/README.md` - Comprehensive setup guide
- `documentation/WORK_ITEM_QUERYING_GUIDE.md` - Query system details
- `documentation/CONFIGURATION_USAGE.md` - Configuration system
- `GUIA_INTERPRETACION_METRICAS.md` - Metrics interpretation guide (Spanish)
- `OPTIMIZED_USAGE_EXAMPLES.md` - Performance optimization guide

## Project Structure

```
Azure-devops-cli-tool/
├── entry_points/
│   └── main.py              # CLI entry point
├── classes/
│   ├── efficiency_calculator.py    # Developer scoring logic
│   ├── WorkItemOperations.py       # Query and analytics
│   ├── state_transition_stack.py   # State tracking
│   └── ...
├── config/
│   ├── azure_devops_config.json    # Main configuration
│   └── config.py                    # Environment loader
├── documentation/           # Detailed documentation
├── run.py                   # CLI wrapper script
├── requirements.txt         # Python dependencies
└── .env                     # Environment variables (create this)
```

## Support

For issues or questions:
1. Check the documentation in the `documentation/` folder
2. Review example outputs in `Output files/`
3. Verify your configuration in `config/azure_devops_config.json`

## License

Internal tool for Inbest SF Automations
