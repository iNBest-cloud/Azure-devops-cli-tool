# Scoring Parameters Guide

This guide explains how to adjust developer scoring weights and efficiency parameters to match your team's priorities.

## Table of Contents

1. [Overview](#overview)
2. [Developer Score Weights](#developer-score-weights)
3. [Efficiency Scoring](#efficiency-scoring)
4. [Business Hours](#business-hours)
5. [Example Configurations](#example-configurations)
6. [CLI Overrides](#cli-overrides)

**📚 For detailed calculation examples with real data, see [SCORING_EXAMPLES.md](SCORING_EXAMPLES.md)**

---

## Overview

The Overall Developer Score is calculated as:

```
Score = (Fair Efficiency x W1) + (Delivery Score x W2) + (Completion Rate x W3) + (On-Time Delivery x W4)
```

All parameters are configured in `config/azure_devops_config.json`.

**Configuration Priority:**
1. CLI parameters (highest)
2. Custom config file (`--scoring-config`)
3. Default config (`config/azure_devops_config.json`)
4. Code defaults (lowest)

---

## Developer Score Weights

Located in `developer_scoring.weights`:

### Current Defaults

```json
{
  "developer_scoring": {
    "weights": {
      "fair_efficiency": 0.2,
      "delivery_score": 0.3,
      "completion_rate": 0.3,
      "on_time_delivery": 0.2
    },
    "minimum_items_for_scoring": 3
  }
}
```

### Weight Descriptions

| Weight | Default | Description |
|--------|---------|-------------|
| `fair_efficiency` | 20% | Productive time vs estimated time |
| `delivery_score` | 30% | Points for early/on-time delivery (60-130 scale) |
| `completion_rate` | 30% | Percentage of items completed |
| `on_time_delivery` | 20% | Percentage delivered by target date |

**Weights must sum to 1.0 (100%).**

### How to Modify

Edit `config/azure_devops_config.json`:

```json
{
  "developer_scoring": {
    "weights": {
      "fair_efficiency": 0.25,
      "delivery_score": 0.35,
      "completion_rate": 0.25,
      "on_time_delivery": 0.15
    }
  }
}
```

---

## Efficiency Scoring

Located in `efficiency_scoring`:

### Current Defaults

```json
{
  "efficiency_scoring": {
    "completion_bonus_percentage": 0.20,
    "max_efficiency_cap": 150.0,
    "early_delivery_thresholds": {
      "very_early_days": 5,
      "early_days": 3,
      "slightly_early_days": 1
    },
    "early_delivery_scores": {
      "very_early": 130.0,
      "early": 120.0,
      "slightly_early": 110.0,
      "on_time": 100.0
    },
    "early_delivery_bonuses": {
      "very_early": 1.0,
      "early": 0.5,
      "slightly_early": 0.25
    },
    "late_delivery_scores": {
      "late_1_3": 95.0,
      "late_4_7": 90.0,
      "late_8_14": 85.0,
      "late_15_plus": 70.0
    },
    "late_penalty_mitigation": {
      "late_1_3": 2.0,
      "late_4_7": 4.0,
      "late_8_14": 6.0,
      "late_15_plus": 8.0
    }
  }
}
```

### Parameter Descriptions

#### Core Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `completion_bonus_percentage` | 0.20 | 20% bonus for completed items |
| `max_efficiency_cap` | 150.0 | Maximum efficiency score |

#### Early Delivery Thresholds

Defines days early for each tier:

| Threshold | Default | Meaning |
|-----------|---------|---------|
| `very_early_days` | 5 | 5+ days early |
| `early_days` | 3 | 3-4 days early |
| `slightly_early_days` | 1 | 1-2 days early |

#### Delivery Scores

Fixed scores assigned by delivery timing:

| Tier | Score | Trigger |
|------|-------|---------|
| `very_early` | 130 | 5+ days early |
| `early` | 120 | 3-4 days early |
| `slightly_early` | 110 | 1-2 days early |
| `on_time` | 100 | On target date |
| `late_1_3` | 95 | 1-3 days late |
| `late_4_7` | 90 | 4-7 days late |
| `late_8_14` | 85 | 8-14 days late |
| `late_15_plus` | 70 | 15+ days late |

#### Late Penalty Mitigation

Hours added to denominator to soften late delivery impact:

| Days Late | Mitigation |
|-----------|------------|
| 1-3 days | 2.0 hours |
| 4-7 days | 4.0 hours |
| 8-14 days | 6.0 hours |
| 15+ days | 8.0 hours |

---

## Business Hours

Located in `business_hours`:

### Current Defaults

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

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `office_start_hour` | 9 | Work day starts at 9 AM |
| `office_end_hour` | 18 | Work day ends at 6 PM |
| `max_hours_per_day` | 8 | Maximum hours credited per day |
| `timezone` | America/Mexico_City | Timezone for calculations |
| `working_days` | [1,2,3,4,5] | Monday=1 through Friday=5 |

---

## Example Configurations

### Prioritize On-Time Delivery

For teams where meeting deadlines is critical:

```json
{
  "developer_scoring": {
    "weights": {
      "fair_efficiency": 0.15,
      "delivery_score": 0.40,
      "completion_rate": 0.20,
      "on_time_delivery": 0.25
    }
  },
  "efficiency_scoring": {
    "late_delivery_scores": {
      "late_1_3": 85.0,
      "late_4_7": 75.0,
      "late_8_14": 65.0,
      "late_15_plus": 50.0
    }
  }
}
```

### Focus on Completion Rate

For teams where finishing tasks matters most:

```json
{
  "developer_scoring": {
    "weights": {
      "fair_efficiency": 0.20,
      "delivery_score": 0.20,
      "completion_rate": 0.45,
      "on_time_delivery": 0.15
    }
  }
}
```

### Balanced with Higher Efficiency Weight

For teams focused on estimation accuracy:

```json
{
  "developer_scoring": {
    "weights": {
      "fair_efficiency": 0.35,
      "delivery_score": 0.25,
      "completion_rate": 0.25,
      "on_time_delivery": 0.15
    }
  },
  "efficiency_scoring": {
    "completion_bonus_percentage": 0.25,
    "max_efficiency_cap": 130.0
  }
}
```

### Lenient Late Delivery Scoring

For teams with frequently changing priorities:

```json
{
  "efficiency_scoring": {
    "late_delivery_scores": {
      "late_1_3": 98.0,
      "late_4_7": 95.0,
      "late_8_14": 90.0,
      "late_15_plus": 80.0
    },
    "late_penalty_mitigation": {
      "late_1_3": 1.0,
      "late_4_7": 2.0,
      "late_8_14": 3.0,
      "late_15_plus": 4.0
    }
  }
}
```

### Extended Work Hours

For teams with different schedules:

```json
{
  "business_hours": {
    "office_start_hour": 8,
    "office_end_hour": 20,
    "max_hours_per_day": 10,
    "timezone": "America/New_York",
    "working_days": [1, 2, 3, 4, 5, 6]
  }
}
```

---

## CLI Overrides

Override parameters directly from command line:

### Weight Overrides

```bash
python run.py --query-work-items \
  --assigned-to "Developer" \
  --fair-efficiency-weight 0.3 \
  --delivery-score-weight 0.4 \
  --export-csv "report.csv"
```

### Efficiency Overrides

```bash
python run.py --query-work-items \
  --assigned-to "Developer" \
  --completion-bonus 0.25 \
  --max-efficiency-cap 120.0 \
  --export-csv "report.csv"
```

### Custom Config File

Create a partial config with only your changes:

```json
{
  "developer_scoring": {
    "weights": {
      "fair_efficiency": 0.4,
      "delivery_score": 0.3,
      "completion_rate": 0.2,
      "on_time_delivery": 0.1
    }
  }
}
```

Then use it:

```bash
python run.py --query-work-items \
  --scoring-config "my_config.json" \
  --assigned-to "Developer" \
  --export-csv "report.csv"
```

---

## Best Practices

1. **Start with defaults** - Run reports first to establish a baseline
2. **Make incremental changes** - Adjust one parameter at a time
3. **Document changes** - Keep notes on why parameters were modified
4. **Communicate** - Inform team when scoring criteria change
5. **Review quarterly** - Revisit parameters to ensure alignment with goals
6. **Validate sum** - Weights must always sum to 1.0

---

## Related Documentation

- **[SCORING_EXAMPLES.md](SCORING_EXAMPLES.md)** - Detailed calculation examples with real data showing how each parameter affects the scoring
- [WORK_ITEM_QUERYING_GUIDE.md](WORK_ITEM_QUERYING_GUIDE.md) - Complete guide for querying work items
- [FLOW_DIAGRAM.md](FLOW_DIAGRAM.md) - Process flow diagram
