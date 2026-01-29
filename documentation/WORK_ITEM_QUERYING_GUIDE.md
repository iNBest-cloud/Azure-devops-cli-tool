# Work Item Querying Guide

Complete reference for querying work items and calculating developer KPIs.

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Query Parameters](#query-parameters)
3. [Configuration File](#configuration-file)
4. [Metrics Explained](#metrics-explained)
5. [CSV Output Columns](#csv-output-columns)
6. [Interpreting Results](#interpreting-results)

---

## Basic Usage

```bash
python run.py --query-work-items \
  --assigned-to "Developer1,Developer2" \
  --start-date "2025-01-01" \
  --end-date "2025-01-31" \
  --export-csv "report.csv"
```

This creates:
- `report.csv` - Detailed work item data
- `report_developer_summary.csv` - Developer KPI summary

---

## Query Parameters

### Required

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--assigned-to` | Developer names (comma-separated) | `"Dev1,Dev2"` |
| `--start-date` | Start date (YYYY-MM-DD) | `"2025-01-01"` |
| `--end-date` | End date (YYYY-MM-DD) | `"2025-01-31"` |

### Optional Filters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--work-item-types` | Types to include | `"Task,Bug,User Story"` |
| `--states` | States to include | `"Closed,Done,Active"` |
| `--project-id` | Single project | `<guid>` |
| `--project-names` | Specific projects | `"ProjectA,ProjectB"` |
| `--all-projects` | Query all projects | (flag) |

### Scoring Overrides

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--scoring-config` | Custom config file | `azure_devops_config.json` |
| `--completion-bonus` | Completion bonus % | `0.20` |
| `--max-efficiency-cap` | Max efficiency | `150.0` |
| `--fair-efficiency-weight` | Weight for efficiency | `0.2` |
| `--delivery-score-weight` | Weight for delivery | `0.3` |

### Output

| Parameter | Description |
|-----------|-------------|
| `--export-csv` | Export to CSV file |
| `--no-efficiency` | Skip calculations (faster) |

---

## Configuration File

The tool uses `config/azure_devops_config.json`. Key sections:

### State Categories

```json
{
  "state_categories": {
    "assigned_states": ["New", "To Do"],
    "productive_states": ["Active", "In Progress", "Code Review", "Testing"],
    "pause_stopper_states": ["Blocked", "On Hold", "Waiting"],
    "completion_states": ["Resolved", "Closed", "Done"],
    "ignored_states": ["Removed", "Cancelled"]
  }
}
```

| Category | Behavior |
|----------|----------|
| **Assigned** | No time counted (assignment state) |
| **Productive** | Time counts toward efficiency (business hours only) |
| **Pause/Stopper** | Pauses tracking, tracked separately |
| **Completion** | Stops tracking, eligible for bonus |
| **Ignored** | Excluded from analysis |

### Business Hours

```json
{
  "business_hours": {
    "office_start_hour": 9,
    "office_end_hour": 18,
    "max_hours_per_day": 8,
    "timezone": "America/Mexico_City",
    "working_days": [1, 2, 3, 4, 5]
  }
}
```

### Scoring Weights

```json
{
  "developer_scoring": {
    "weights": {
      "fair_efficiency": 0.2,
      "delivery_score": 0.3,
      "completion_rate": 0.3,
      "on_time_delivery": 0.2
    }
  }
}
```

See [SCORING_PARAMETERS.md](SCORING_PARAMETERS.md) for detailed customization.

---

## Metrics Explained

### Fair Efficiency Score

```
Numerator = Active Hours + Completion Bonus + Timing Bonus
Denominator = Estimated Hours + Late Penalty Mitigation
Fair Efficiency = (Numerator / Denominator) x 100
```

- **Completion Bonus**: 20% of estimated hours (for completed items)
- **Timing Bonus**: Extra hours credited for early delivery
- **Late Penalty Mitigation**: Hours added to soften late delivery impact

### Delivery Score

Fixed scores by delivery timing:

| Timing | Score |
|--------|-------|
| Very early (5+ days) | 130 |
| Early (3-4 days) | 120 |
| Slightly early (1-2 days) | 110 |
| On time | 100 |
| 1-3 days late | 95 |
| 4-7 days late | 90 |
| 8-14 days late | 85 |
| 15+ days late | 70 |

### Overall Developer Score

```
Score = (Efficiency x 0.2) + (Delivery x 0.3) + (Completion x 0.3) + (OnTime x 0.2)
```

Weights are configurable in the config file.

---

## CSV Output Columns

### Developer Summary (`*_developer_summary.csv`)

| Column | Description |
|--------|-------------|
| Developer | Developer name |
| Total Work Items | Items processed |
| Completed Items | Items in completion states |
| Items With Active Time | Items with tracked time |
| Sample Confidence % | Data quality indicator |
| Completion Rate % | Completion percentage |
| On-Time Delivery % | On-time percentage |
| Average Efficiency % | Average efficiency score |
| Average Delivery Score | Average delivery points |
| Overall Developer Score | Combined weighted score |
| Total Active Hours | Hours in productive states |
| Total Estimated Hours | Sum of estimates |
| Avg Days Ahead/Behind | Average timing |
| Reopened Items Handled | Items reopened and reworked |
| Reopened Rate % | Reopened percentage |
| Work Item Types | Count of different types |
| Projects Count | Projects worked on |
| Early/On-Time/Late Deliveries | Timing breakdown counts |

### Detailed Export (`*_detailed.csv`)

| Column | Description |
|--------|-------------|
| ID | Work item ID |
| Title | Work item title |
| Project Name | Project |
| Assigned To | Developer |
| State | Current state |
| Work Item Type | Type (Task, Bug, etc.) |
| Start/Target/Closed Date | Key dates |
| Estimated Hours | Estimated time |
| Active Time (Hours) | Productive time tracked |
| Blocked Time (Hours) | Time in blocked states |
| Efficiency % | Efficiency score |
| Delivery Score | Delivery points |
| Days Ahead/Behind Target | Delivery timing |
| Completion/Timing Bonus | Bonus hours credited |
| Was Reopened | If item was reopened |
| Active After Reopen | Hours after reopening |

---

## Interpreting Results

### Overall Developer Score Ranges

| Score | Performance |
|-------|-------------|
| 80-100 | Excellent |
| 65-79 | Good |
| 60-64 | Acceptable (minimum) |
| 45-59 | Needs improvement |
| <45 | Requires intervention |

### Key Indicators

| Indicator | Target |
|-----------|--------|
| On-Time Delivery % | > 50% |
| Average Efficiency % | > 40% |
| Overall Score | > 60 |
| Reopened Rate % | < 10% |

### Common Issues

| Issue | Solution |
|-------|----------|
| Zero active hours | Check productive states configuration |
| Efficiency > 100% | Normal (bonuses can exceed 100%, capped at 150%) |
| Missing developers | Verify name spelling matches Azure DevOps |
| Slow queries | Use `--no-efficiency` for faster results |

---

## Example Commands

### Sprint Analysis

```bash
python run.py --query-work-items \
  --assigned-to "Dev1,Dev2,Dev3" \
  --work-item-types "Task,Bug" \
  --states "Closed,Done" \
  --start-date "2025-01-01" \
  --end-date "2025-01-15" \
  --export-csv "sprint_analysis.csv"
```

### Complete Analysis (Active + Closed)

```bash
python run.py --query-work-items \
  --assigned-to "Dev1,Dev2" \
  --states "Closed,Done,Active,In Progress" \
  --start-date "2025-01-01" \
  --end-date "2025-01-31" \
  --export-csv "complete_analysis.csv"
```

### Custom Scoring

```bash
python run.py --query-work-items \
  --assigned-to "Developer" \
  --fair-efficiency-weight 0.3 \
  --delivery-score-weight 0.4 \
  --completion-bonus 0.25 \
  --export-csv "custom_scoring.csv"
```
