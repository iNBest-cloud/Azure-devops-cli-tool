# Azure DevOps CLI Tool

A command-line interface for Azure DevOps to manage projects, service hooks, work items, and developer KPI analytics.

## Prerequisites

- Python 3.7+
- `pip install -r requirements.txt`

## Configuration

Create a `.env` file:

```plaintext
AZURE_DEVOPS_ORG=YourOrganizationName
AZURE_DEVOPS_PAT=YourPersonalAccessToken
```

## Usage

```bash
python run.py <command> [options]
```

For help:
```bash
python run.py --explain
```

---

## Key Commands

### List Projects

```bash
python run.py --list-projects
```

### Query Work Items with KPI Calculations

```bash
python run.py --query-work-items \
  --assigned-to "Developer1,Developer2" \
  --start-date "2025-01-01" \
  --end-date "2025-01-31" \
  --export-csv "report.csv"
```

**Output files:**
- `report.csv` - Detailed work item data
- `report_developer_summary.csv` - Developer metrics summary

### Service Hook Management

```bash
# List hooks for a project
python run.py --list-subscriptions --project-id <id>

# Create a hook
python run.py --create-hook --project-id <id> --event-type workitem.updated

# Create standard hooks for Software Factory projects
python run.py --create-standard-hooks --filter-tag "Software Factory"
```

---

## Configuration File

The tool uses `config/azure_devops_config.json` for:

- State categories (productive, blocked, completion, ignored)
- Business hours (timezone, working days)
- Scoring weights (efficiency, delivery, completion, on-time)
- Export field configurations

See [SCORING_PARAMETERS.md](SCORING_PARAMETERS.md) for customization details.

---

## Developer Metrics

| Metric | Description |
|--------|-------------|
| Completion Rate % | Items completed vs assigned |
| On-Time Delivery % | Items delivered by target date |
| Average Efficiency % | Productive time vs estimated |
| Delivery Score | Points for early/on-time delivery (60-130) |
| Overall Score | Weighted combination of all metrics |

---

## Related Documentation

- [QUICKSTART.md](../QUICKSTART.md) - 5-minute setup guide
- [SCORING_PARAMETERS.md](SCORING_PARAMETERS.md) - Adjust scoring weights and parameters
- [SCORING_EXAMPLES.md](SCORING_EXAMPLES.md) - Detailed calculation examples with real data
- [FLOW_DIAGRAM.md](FLOW_DIAGRAM.md) - System architecture
- [WORK_ITEM_QUERYING_GUIDE.md](WORK_ITEM_QUERYING_GUIDE.md) - Detailed query guide

---

## GitHub Actions

Automated workflows in `.github/workflows/`:

- **daily-snapshot.yml** - Daily work item snapshot (9:00 AM Mexico City)
- **monthly-developer-report.yml** - Monthly report (30th of each month)

Trigger manually from GitHub Actions tab or run on schedule.
