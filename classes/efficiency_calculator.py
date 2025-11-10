"""
Efficiency calculation module for Azure DevOps work items.
Handles fair efficiency metrics, delivery scoring, and business hours calculations.
Uses stack-based state transition tracking for accurate time measurement.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from classes.state_transition_stack import WorkItemStateStack, create_stack_from_work_item


class EfficiencyCalculator:
    """Calculator for work item efficiency metrics and developer scoring."""
    
    def __init__(self, scoring_config: Optional[Dict] = None):
        """
        Initialize with configurable scoring parameters.
        
        Args:
            scoring_config: Dictionary with scoring configuration parameters
        """
        # Default scoring configuration
        self.config = {
            'completion_bonus_percentage': 0.20,  # 20% of estimated time
            'max_efficiency_cap': 150.0,  # Cap efficiency at 150%
            'max_hours_per_day': 8.0,   # Maximum business hours per day (changed from 10)
            'early_delivery_thresholds': {
                'very_early_days': 7,
                'early_days': 3,
                'slightly_early_days': 1
            },
            'early_delivery_scores': {
                'very_early': 130.0,
                'early': 120.0,
                'slightly_early': 110.0,
                'on_time': 100.0
            },
            'early_delivery_bonuses': {
                'very_early': 1.0,  # hours per day early
                'early': 0.5,
                'slightly_early': 0.25
            },
            'late_delivery_scores': {
                'late_1_3': 90.0,
                'late_4_7': 80.0,
                'late_8_14': 70.0,
                'late_15_plus': 60.0
            },
            'late_penalty_mitigation': {
                'late_1_3': 2.0,
                'late_4_7': 4.0,
                'late_8_14': 6.0,
                'late_15_plus': 8.0
            },
            'developer_score_weights': {
                'fair_efficiency': 0.25,   # 25% (reduced from 40%, adjusted by confidence)
                'delivery_score': 0.50,    # 50% (increased from 30%, most stable metric)
                'completion_rate': 0.15,   # 15% (reduced from 20%)
                'on_time_delivery': 0.10   # 10% (unchanged)
            },
            'default_work_item_hours': {
                'user story': 8.0,   # 1 day (reduced from 16)
                'task': 4.0,         # 0.5 day (reduced from 8) 
                'bug': 2.0,          # 0.25 day (reduced from 4)
                'default': 4.0       # 0.5 day (reduced from 8)
            }
        }
        
        # Update with user-provided configuration
        if scoring_config:
            self._update_config(scoring_config)
    
    def _update_config(self, user_config: Dict):
        """Recursively update configuration with user values."""
        def merge_dicts(base_dict, update_dict):
            for key, value in update_dict.items():
                if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                    merge_dicts(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        merge_dicts(self.config, user_config)
    
    def calculate_fair_efficiency_metrics(self, 
                                        work_item: Dict,
                                        state_history: List[Dict], 
                                        state_config: Optional[Dict] = None,
                                        timeframe_start: Optional[str] = None,
                                        timeframe_end: Optional[str] = None) -> Dict:
        """
        Calculate fair efficiency metrics using stack-based state transition tracking with state categories.
        
        Args:
            work_item: Work item details with dates and metadata
            state_history: List of state changes with timestamps
            state_config: Configuration for state categories and behaviors
            timeframe_start: Start date of the query timeframe (YYYY-MM-DD format)
            timeframe_end: End date of the query timeframe (YYYY-MM-DD format)
        Returns:
            Dictionary with enhanced efficiency metrics
        """
        estimated_hours = self._calculate_estimated_time_from_work_item(
            work_item, timeframe_start, timeframe_end
        )

        if len(state_history) < 2:
            return self._empty_efficiency_metrics(estimated_hours)
        
        # Use provided state config or defaults
        if state_config is None:
            state_config = {
                'productive_states': ['Active', 'In Progress', 'Development', 'Code Review', 'Testing'],
                'pause_stopper_states': ['Stopper', 'Blocked', 'On Hold', 'Waiting'],
                'completion_states': ['Resolved', 'Closed', 'Done'],
                'ignored_states': ['Removed', 'Discarded', 'Cancelled']
            }
        
        # Create stack-based state tracker with office hours configuration
        office_hours_config = {
            'office_start_hour': self.config.get('office_start_hour', 9),
            'office_end_hour': self.config.get('office_end_hour', 17),
            'max_hours_per_day': self.config.get('max_hours_per_day', 8),
            'timezone_str': self.config.get('timezone', 'America/Mexico_City')
        }
        
        state_stack = create_stack_from_work_item(
            work_item, state_history, state_config, office_hours_config, timeframe_start, timeframe_end
        )
        
        # Check if work item should be ignored
        if state_stack.should_ignore_work_item():
            return self._ignored_work_item_metrics(estimated_hours)
        
        # Get time metrics from stack
        raw_productive_hours = state_stack.get_total_productive_hours()
        paused_hours = state_stack.get_total_paused_hours()
        total_hours = state_stack.get_total_time_all_states()
        state_durations = state_stack.get_state_durations()
        pattern_summary = state_stack.get_pattern_summary()
        
        # Apply active hours capping logic: 1.2x estimate cap, exclude if no estimate
        # Now uses exact Logic App estimates (no transformations)
        if estimated_hours <= 0:
            # If no estimate hours, don't count active time
            productive_hours = 0
            pattern_summary['capping_applied'] = 'no_estimate_exclusion'
        else:
            # Cap active hours at 1.2x the estimated hours (using exact Logic App values)
            max_allowed_hours = estimated_hours * 1.2
            if raw_productive_hours > max_allowed_hours:
                productive_hours = max_allowed_hours
                pattern_summary['capping_applied'] = f'capped_at_1.2x_estimate_{raw_productive_hours:.2f}_to_{max_allowed_hours:.2f}'
            else:
                productive_hours = raw_productive_hours
                pattern_summary['capping_applied'] = 'no_capping_needed'
        
        # Calculate delivery timing
        delivery_metrics = self._calculate_delivery_timing(work_item)
        
        # Calculate completion bonus
        is_completed = work_item.get('state', '').lower() in ['closed', 'done', 'resolved']
        completion_bonus = (estimated_hours * self.config['completion_bonus_percentage']) if is_completed else 0

        # Calculate traditional efficiency (estimated time vs active time)
        # INVERTED: Higher percentage = better efficiency
        # 100% = used exactly estimated time
        # >100% = completed faster than estimated (efficient)
        # <100% = took longer than estimated (inefficient)
        if productive_hours > 0 and estimated_hours > 0:
            traditional_efficiency = (estimated_hours / productive_hours) * 100
            traditional_efficiency = min(traditional_efficiency, self.config['max_efficiency_cap'])
        else:
            traditional_efficiency = 0

        # Calculate fair efficiency score with completion bonus only
        # Timing bonuses are reflected in delivery_score, not efficiency
        numerator = productive_hours + completion_bonus
        denominator = estimated_hours + delivery_metrics['late_penalty_mitigation']

        if denominator > 0:
            fair_efficiency = (numerator / denominator) * 100
            fair_efficiency = min(fair_efficiency, self.config['max_efficiency_cap'])
        else:
            fair_efficiency = 0
        
        return {
            "active_time_hours": round(productive_hours, 2),
            "raw_active_time_hours": round(raw_productive_hours, 2),
            "paused_time_hours": round(paused_hours, 2),
            "total_time_hours": round(total_hours, 2),
            "estimated_time_hours": round(estimated_hours, 2),
            "efficiency_percentage": round(traditional_efficiency, 2),
            "fair_efficiency_score": round(fair_efficiency, 2),
            "delivery_score": round(delivery_metrics['delivery_score'], 2),
            "completion_bonus": round(completion_bonus, 2),
            "delivery_timing_bonus": round(delivery_metrics['timing_bonus_hours'], 2),
            "days_ahead_behind": delivery_metrics['days_difference'],
            "state_breakdown": state_durations,
            "paused_state_breakdown": state_stack.paused_time_accumulator,
            "was_reopened": pattern_summary.get('was_reopened', False),
            "active_after_reopen": round(pattern_summary.get('active_after_reopen_hours', 0), 2),
            "is_completed": pattern_summary.get('is_completed', False),
            "should_ignore": pattern_summary.get('should_ignore', False),
            "capping_applied": pattern_summary.get('capping_applied', 'unknown'),
            "stack_summary": pattern_summary
        }
    
    
    def _calculate_estimated_time_from_work_item(self, work_item: Dict, 
                                               timeframe_start: Optional[str] = None, 
                                               timeframe_end: Optional[str] = None) -> float:
        """
        Calculate estimated time using OriginalEstimate field from Fabric Logic App only.
        No fallback to DevOps API or date-based calculation - Fabric is the single source.
        When timeframe is provided, only count office days that fall within the timeframe.

        Args:
            work_item: Work item with original_estimate set by Fabric Logic App
            timeframe_start: Start date of the query timeframe (YYYY-MM-DD format)
            timeframe_end: End date of the query timeframe (YYYY-MM-DD format)
        Returns:
            Estimated hours as float (0 if no estimate from Fabric)
        """
        # Use OriginalEstimate field from Fabric Logic App only
        original_estimate = work_item.get('original_estimate')
        if original_estimate is not None and original_estimate > 0:
            base_estimate = float(original_estimate)

            # DISABLED: Timeframe scaling is intentionally off because Fabric is the source of truth.
            # Exact Logic App estimates must remain unaltered - no proportional adjustments.
            # if timeframe_start or timeframe_end:
            #     return self._adjust_estimate_for_timeframe(work_item, base_estimate, timeframe_start, timeframe_end)

            return base_estimate

        # If Fabric Logic App doesn't provide an estimate, return 0
        # Note: No fallback to DevOps API or revision history - Fabric is the only source
        return 0.0
    
    def _adjust_dates_for_timeframe(self, start_date: datetime, target_date: datetime, 
                                   timeframe_start: Optional[str], timeframe_end: Optional[str]) -> tuple:
        """
        Adjust start and target dates to only include the portion that falls within the specified timeframe.
        For proportional calculation, we count the days that overlap with the timeframe.
        
        Args:
            start_date: Work item start date
            target_date: Work item target date
            timeframe_start: Query timeframe start date (YYYY-MM-DD format)
            timeframe_end: Query timeframe end date (YYYY-MM-DD format)
            
        Returns:
            Tuple of (adjusted_start, adjusted_target) datetime objects
        """
        adjusted_start = start_date
        adjusted_target = target_date
        
        # Parse timeframe dates
        try:
            if timeframe_start:
                timeframe_start_dt = datetime.fromisoformat(f"{timeframe_start}T00:00:00+00:00")
                # If work item starts before timeframe, adjust to timeframe start
                if start_date < timeframe_start_dt:
                    adjusted_start = timeframe_start_dt
                    
            if timeframe_end:
                timeframe_end_dt = datetime.fromisoformat(f"{timeframe_end}T23:59:59+00:00")
                # If work item ends after timeframe, adjust to timeframe end
                if target_date > timeframe_end_dt:
                    adjusted_target = timeframe_end_dt
            
            # Special case: if target date is within the timeframe start day but before office hours,
            # extend it to at least include the office start time of that day for proportional calculation
            if timeframe_start:
                timeframe_start_dt = datetime.fromisoformat(f"{timeframe_start}T00:00:00+00:00")
                if (start_date < timeframe_start_dt and 
                    target_date.date() >= timeframe_start_dt.date() and 
                    adjusted_target < datetime.fromisoformat(f"{timeframe_start}T09:00:00+00:00")):
                    # Extend target to at least the start of office hours on the timeframe start date
                    adjusted_target = max(adjusted_target, datetime.fromisoformat(f"{timeframe_start}T09:00:00+00:00"))
                    
        except (ValueError, TypeError):
            # If timeframe parsing fails, return original dates
            pass
            
        return adjusted_start, adjusted_target
    
    def _adjust_estimate_for_timeframe(self, work_item: Dict, base_estimate: float,
                                      timeframe_start: Optional[str], timeframe_end: Optional[str]) -> float:
        """
        INTENTIONALLY DISABLED: This method is parked to preserve exact Logic App estimates.

        Previously: Adjusted the estimated hours proportionally based on the timeframe.

        Current Status: DISABLED because Fabric Logic App is the source of truth.
        Exact estimates from Logic App must remain unaltered. No proportional adjustments,
        minimum hour guarantees, or timeframe-based scaling should be applied.

        If future timeframe-based adjustments are desired, this method would need a new,
        non-transforming design aligned with the Fabric source-of-truth policy.

        Args:
            work_item: Work item details
            base_estimate: Original estimated hours
            timeframe_start: Query timeframe start date (YYYY-MM-DD format)
            timeframe_end: Query timeframe end date (YYYY-MM-DD format)

        Returns:
            Always returns the base_estimate unchanged (exact Logic App value)
        """
        # DISABLED: Return original estimate unchanged to preserve Fabric Logic App values
        return base_estimate
    
    def _calculate_office_days_between_dates(self, start_date: datetime, end_date: datetime) -> float:
        """
        Calculate the number of office days between two dates.
        For proportional calculation, we count full business days if any part of the period falls on that day.
        
        Args:
            start_date: Start datetime
            end_date: End datetime
            
        Returns:
            Number of office days as float
        """
        if start_date >= end_date:
            return 0.0
            
        total_days = 0.0
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday=0, Friday=4
                # For proportional calculation, if any part of the date range falls on this office day,
                # count it as a full day (simplified approach for proportional estimates)
                total_days += 1.0
                    
            current_date += timedelta(days=1)
            
        return total_days
    
    def _get_estimate_from_revisions(self, revisions: List[Dict]) -> float:
        """
        Search through revision history to find the last valid OriginalEstimate value.
        
        Args:
            revisions: List of revision dictionaries from work item history
            
        Returns:
            Last valid original estimate as float, or 0 if not found
        """
        if not revisions:
            return 0.0
        
        # Sort revisions by revision number in descending order to get the most recent first
        sorted_revisions = sorted(revisions, key=lambda x: x.get('revision', 0), reverse=True)
        
        for revision in sorted_revisions:
            # Check if this revision has fields data (some revision formats may differ)
            if isinstance(revision, dict):
                # Look for OriginalEstimate in various possible field formats
                fields = revision.get('fields', {})
                
                # Check different possible field names for original estimate
                estimate_fields = [
                    'Microsoft.VSTS.Scheduling.OriginalEstimate',
                    'OriginalEstimate',
                    'original_estimate'
                ]
                
                for field_name in estimate_fields:
                    estimate_value = fields.get(field_name)
                    if estimate_value is not None and estimate_value > 0:
                        try:
                            return float(estimate_value)
                        except (ValueError, TypeError):
                            continue
                
                # Also check at the top level of revision data
                for field_name in estimate_fields:
                    estimate_value = revision.get(field_name)
                    if estimate_value is not None and estimate_value > 0:
                        try:
                            return float(estimate_value)
                        except (ValueError, TypeError):
                            continue
        
        return 0.0
    
    def _calculate_business_hours_between_dates(self, start_date: datetime, end_date: datetime) -> float:
        """
        Calculate business hours between start and target dates considering office hours.
        """
        if start_date >= end_date:
            return 0.0
        
        total_hours = 0.0
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Calculate hours for this day
            if current_date == start_date.date() and current_date == end_date.date():
                # Same day - use actual start and end times within office hours
                day_start = max(start_date.time(), datetime.strptime('09:00', '%H:%M').time())
                day_end = min(end_date.time(), datetime.strptime('17:00', '%H:%M').time())
                if day_start < day_end:
                    day_hours = (datetime.combine(current_date, day_end) - 
                               datetime.combine(current_date, day_start)).total_seconds() / 3600
                    total_hours += min(day_hours, self.config['max_hours_per_day'])
            elif current_date == start_date.date():
                # First day - from start time to end of office hours
                day_start = max(start_date.time(), datetime.strptime('09:00', '%H:%M').time())
                day_end = datetime.strptime('17:00', '%H:%M').time()
                if day_start < day_end:
                    day_hours = (datetime.combine(current_date, day_end) - 
                               datetime.combine(current_date, day_start)).total_seconds() / 3600
                    total_hours += min(day_hours, self.config['max_hours_per_day'])
            elif current_date == end_date.date():
                # Last day - from start of office hours to end time
                day_start = datetime.strptime('09:00', '%H:%M').time()
                day_end = min(end_date.time(), datetime.strptime('17:00', '%H:%M').time())
                if day_start < day_end:
                    day_hours = (datetime.combine(current_date, day_end) - 
                               datetime.combine(current_date, day_start)).total_seconds() / 3600
                    total_hours += min(day_hours, self.config['max_hours_per_day'])
            else:
                # Full office day - 8 hours max
                total_hours += self.config['max_hours_per_day']
            
            current_date += timedelta(days=1)
        
        return round(total_hours, 2)
    
    def _calculate_delivery_timing(self, work_item: Dict) -> Dict:
        """Calculate delivery timing metrics and bonuses/penalties."""
        target_date = work_item.get('target_date')
        closed_date = work_item.get('closed_date')
        
        if not target_date or not closed_date:
            return {
                'delivery_score': 100.0,
                'timing_bonus_hours': 0.0,
                'late_penalty_mitigation': 0.0,
                'days_difference': 0
            }
        
        try:
            target = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
            closed = datetime.fromisoformat(closed_date.replace('Z', '+00:00'))
            
            days_difference = (closed - target).total_seconds() / 86400
            
            if days_difference <= 0:
                # Early or on-time delivery
                return self._calculate_early_delivery_bonus(days_difference)
            else:
                # Late delivery with graduated penalties
                return self._calculate_late_delivery_penalty(days_difference)
                
        except (ValueError, TypeError):
            return {
                'delivery_score': 100.0,
                'timing_bonus_hours': 0.0,
                'late_penalty_mitigation': 0.0,
                'days_difference': 0
            }
    
    def _calculate_early_delivery_bonus(self, days_difference: float) -> Dict:
        """Calculate bonus for early delivery."""
        thresholds = self.config['early_delivery_thresholds']
        scores = self.config['early_delivery_scores']
        bonuses = self.config['early_delivery_bonuses']
        
        if days_difference <= -thresholds['very_early_days']:
            delivery_score = scores['very_early']
            timing_bonus_hours = abs(days_difference) * bonuses['very_early']
        elif days_difference <= -thresholds['early_days']:
            delivery_score = scores['early']
            timing_bonus_hours = abs(days_difference) * bonuses['early']
        elif days_difference <= -thresholds['slightly_early_days']:
            delivery_score = scores['slightly_early']
            timing_bonus_hours = abs(days_difference) * bonuses['slightly_early']
        else:
            delivery_score = scores['on_time']
            timing_bonus_hours = 0.0
        
        return {
            'delivery_score': delivery_score,
            'timing_bonus_hours': timing_bonus_hours,
            'late_penalty_mitigation': 0.0,
            'days_difference': round(days_difference, 1)
        }
    
    def _calculate_late_delivery_penalty(self, days_difference: float) -> Dict:
        """Calculate penalty for late delivery."""
        scores = self.config['late_delivery_scores']
        mitigation = self.config['late_penalty_mitigation']
        
        if days_difference <= 3:
            delivery_score = scores['late_1_3']
            late_penalty_mitigation = mitigation['late_1_3']
        elif days_difference <= 7:
            delivery_score = scores['late_4_7']
            late_penalty_mitigation = mitigation['late_4_7']
        elif days_difference <= 14:
            delivery_score = scores['late_8_14']
            late_penalty_mitigation = mitigation['late_8_14']
        else:
            delivery_score = scores['late_15_plus']
            late_penalty_mitigation = mitigation['late_15_plus']
        
        return {
            'delivery_score': delivery_score,
            'timing_bonus_hours': 0.0,
            'late_penalty_mitigation': late_penalty_mitigation,
            'days_difference': round(days_difference, 1)
        }
    
    
    def calculate_developer_score(self, completion_rate: float, avg_fair_efficiency: float, 
                                avg_delivery_score: float, on_time_delivery: float) -> float:
        """Calculate overall developer score using configurable weights."""
        weights = self.config['developer_score_weights']
        
        overall_score = (
            (avg_fair_efficiency * weights['fair_efficiency']) +
            (avg_delivery_score * weights['delivery_score']) +
            (completion_rate * weights['completion_rate']) +
            (min(100, on_time_delivery) * weights['on_time_delivery'])
        )
        
        return round(overall_score, 2)
    
    def _empty_efficiency_metrics(self, estimated_hours: float = 0.0) -> Dict:
        """Return empty efficiency metrics structure."""
        return {
            "active_time_hours": 0,
            "raw_active_time_hours": 0,
            "paused_time_hours": 0,
            "total_time_hours": 0,
            "estimated_time_hours": round(estimated_hours, 2),
            "efficiency_percentage": 0,
            "fair_efficiency_score": 0,
            "delivery_score": 0,
            "completion_bonus": 0,
            "delivery_timing_bonus": 0,
            "days_ahead_behind": 0,
            "state_breakdown": {},
            "paused_state_breakdown": {},
            "was_reopened": False,
            "active_after_reopen": 0,
            "is_completed": False,
            "should_ignore": False,
            "capping_applied": "no_data",
            "stack_summary": {}
        }
    
    def _ignored_work_item_metrics(self, estimated_hours: float = 0.0) -> Dict:
        """Return metrics structure for ignored work items."""
        return {
            "active_time_hours": 0,
            "raw_active_time_hours": 0,
            "paused_time_hours": 0,
            "total_time_hours": 0,
            "estimated_time_hours": round(estimated_hours, 2),
            "efficiency_percentage": 0,
            "fair_efficiency_score": 0,
            "delivery_score": 0,
            "completion_bonus": 0,
            "delivery_timing_bonus": 0,
            "days_ahead_behind": 0,
            "state_breakdown": {},
            "paused_state_breakdown": {},
            "was_reopened": False,
            "active_after_reopen": 0,
            "is_completed": False,
            "should_ignore": True,
            "capping_applied": "ignored_item",
            "stack_summary": {"should_ignore": True}
        }
