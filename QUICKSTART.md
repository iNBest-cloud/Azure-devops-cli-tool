# Quick Start Guide

Get up and running in 5 minutes.

## Prerequisites

- Python 3.7+
- Azure DevOps organization access
- Personal Access Token (PAT) with `Work Items: Read` permission

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Create a `.env` file in the project root:

```plaintext
AZURE_DEVOPS_ORG=YourOrganizationName
AZURE_DEVOPS_PAT=your_personal_access_token
```

**To create a PAT:**
1. Go to Azure DevOps > User Settings > Personal Access Tokens
2. Click "New Token"
3. Set scope to `Work Items: Read`
4. Copy token to `.env` file

### 3. Verify Setup

```bash
python run.py --list-projects
```

If you see your projects, you're ready.

---

## Common Commands

### Generate Monthly Developer Report

```bash
python run.py --query-work-items \
  --assigned-to "Developer Name" \
  --start-date "2025-01-01" \
  --end-date "2025-01-31" \
  --export-csv "january_report.csv"
```

Creates two files:
- `january_report.csv` - Detailed work item data
- `january_report_developer_summary.csv` - Developer KPI summary

### Query Multiple Developers

```bash
python run.py --query-work-items \
  --assigned-to "Dev1,Dev2,Dev3" \
  --start-date "2025-01-01" \
  --end-date "2025-01-31" \
  --export-csv "team_report.csv"
```

### List Projects

```bash
python run.py --list-projects
```

---

## Understanding Output

The developer summary CSV includes:

| Metric | Description |
|--------|-------------|
| Overall Developer Score | Weighted combination of all metrics |
| Average Efficiency % | Productivity vs estimated time |
| Average Delivery Score | On-time performance (60-130) |
| Completion Rate % | Tasks completed vs assigned |
| On-Time Delivery % | Completed by target date |

---

## GitHub Actions (Automated Reports)

The tool includes workflows for automated reporting:

- **Daily Snapshot** - Runs at 9:00 AM Mexico City time
- **Monthly Report** - Runs on the 30th of each month

Trigger manually from GitHub Actions tab.

---

## Get Help

```bash
python run.py --explain
```

---

## Next Steps

- **Customize scoring**: See [documentation/SCORING_PARAMETERS.md](documentation/SCORING_PARAMETERS.md)
- **Full documentation**: See [documentation/](documentation/)
