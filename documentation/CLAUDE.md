# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

Azure DevOps CLI tool for managing projects, service hooks, work items, and developer KPI analytics.

## Project Structure

```
Azure-devops-cli-tool/
├── run.py                 # Entry point
├── entry_points/
│   └── main.py           # CLI argument parsing
├── classes/
│   ├── AzureDevOps.py    # Base API client
│   ├── commands.py       # Project/hook operations
│   ├── AzureDevopsProjectOperations.py
│   ├── WorkItemOperations.py      # Work item queries
│   ├── efficiency_calculator.py   # Scoring logic
│   ├── state_transition_stack.py  # Time tracking
│   └── project_discovery.py       # Project filtering
├── config/
│   ├── config.py         # Environment config
│   ├── config_loader.py  # JSON config loader
│   └── azure_devops_config.json   # Main configuration
├── documentation/
│   ├── README.md         # Main docs
│   ├── SCORING_PARAMETERS.md      # Scoring customization
│   ├── WORK_ITEM_QUERYING_GUIDE.md
│   ├── FLOW_DIAGRAM.md   # Architecture
│   └── CLAUDE.md         # This file
├── .github/workflows/
│   ├── daily-snapshot.yml
│   └── monthly-developer-report.yml
└── QUICKSTART.md         # 5-minute setup
```

## Setup

```bash
pip install -r requirements.txt
```

Create `.env`:
```
AZURE_DEVOPS_ORG=<org>
AZURE_DEVOPS_PAT=<token>
```

## Key Commands

```bash
# List projects
python run.py --list-projects

# Query work items
python run.py --query-work-items --assigned-to "Name" --export-csv "report.csv"

# Help
python run.py --explain
```

## Architecture

1. `main.py` parses CLI arguments
2. Creates operation class (Commands, ProjectOperations, WorkItemOperations)
3. Operations inherit from `AzureDevOps` base class for auth
4. `handle_request()` method executes API calls
5. Results processed and exported to CSV

## Configuration

Main config: `config/azure_devops_config.json`

- `state_categories`: Define productive/blocked/completion states
- `business_hours`: Office hours, timezone, working days
- `developer_scoring.weights`: Scoring weight distribution
- `efficiency_scoring`: Delivery score thresholds and bonuses

## Key Files for Development

| Purpose | File |
|---------|------|
| CLI parsing | `entry_points/main.py` |
| Work item queries | `classes/WorkItemOperations.py` |
| Scoring calculations | `classes/efficiency_calculator.py` |
| Time tracking | `classes/state_transition_stack.py` |
| Configuration | `config/azure_devops_config.json` |

## Notes

- No test framework configured
- Uses environment-based config via python-dotenv
- Mexico City timezone for business hours calculations
