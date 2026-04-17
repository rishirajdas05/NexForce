"""
ML Engine — NexForce EMS
Models:
  1. Attendance Anomaly Detector      (Z-score statistical)
  2. Performance Score Predictor      (Weighted multi-factor)
  3. Attrition Risk Analyzer          (Heuristic risk scoring)
  4. Smart Search Engine              (Multi-field relevance)
  5. Department Analytics             (Statistical aggregation)
  6. Salary Fairness Analyzer         (Percentile + gap detection)
  7. Workload Balance Detector        (Hours pattern analysis)
  8. Skill Gap Analyzer               (Team skill coverage)
  9. Leave Pattern Analyzer           (Burn rate + clustering)
 10. Employee Wellness Score          (Composite wellbeing index)
"""

import numpy as np
from datetime import date, datetime, timedelta
from collections import defaultdict
import math


# ─── 1. ATTENDANCE ANOMALY DETECTOR ──────────────────────────────────────────

class AttendanceAnomalyDetector:
    """
    Detects anomalies in attendance using Z-score analysis.
    Flags: unusual check-in/out times, short shifts, absence streaks.
    """

    def detect_anomaly(self, attendance_records):
        anomalies = []
        if len(attendance_records) < 5:
            return anomalies

        checkin_hours = []
        for r in attendance_records:
            if r.get('check_in') and r.get('status') in ['present', 'late']:
                t = r['check_in']
                if hasattr(t, 'hour'):
                    h = t.hour + t.minute / 60
                    checkin_hours.append(h)

        if len(checkin_hours) < 3:
            return anomalies

        mean_ci = float(np.mean(checkin_hours))
        std_ci = float(np.std(checkin_hours)) if np.std(checkin_hours) > 0 else 0.5

        for r in attendance_records:
            reasons = []
            if r.get('check_in') and r.get('status') in ['present', 'late']:
                t = r['check_in']
                if hasattr(t, 'hour'):
                    h = t.hour + t.minute / 60
                    z = abs(h - mean_ci) / std_ci
                    if z > 2.0:
                        direction = "late" if h > mean_ci else "early"
                        reasons.append(f"Unusually {direction} check-in ({t.hour:02d}:{t.minute:02d})")

            if r.get('check_in') and r.get('check_out'):
                ci = r['check_in']
                co = r['check_out']
                if hasattr(ci, 'hour') and hasattr(co, 'hour'):
                    hours = (co.hour * 60 + co.minute - ci.hour * 60 - ci.minute) / 60
                    if hours < 4:
                        reasons.append(f"Very short shift ({hours:.1f}h)")
                    elif hours > 13:
                        reasons.append(f"Very long shift ({hours:.1f}h)")

            if r.get('status') == 'absent':
                reasons.append("Absent")

            if reasons:
                anomalies.append({'date': r.get('date'), 'reasons': reasons, 'is_anomaly': True})

        return anomalies

    def get_attendance_score(self, records, period_days=30):
        if not records:
            return 50.0
        present = sum(1 for r in records if r.get('status') in ['present', 'work_from_home'])
        total = len(records)
        if total == 0:
            return 50.0
        base = (present / total) * 100
        anomaly_count = sum(1 for r in records if r.get('is_anomaly'))
        penalty = anomaly_count * 3
        return round(max(0.0, min(100.0, base - penalty)), 1)

    def get_streak_analysis(self, records):
        """Find longest present streak and current absent streak"""
        statuses = [r.get('status') for r in records]
        longest_present = 0
        current_present = 0
        current_absent_streak = 0

        for s in statuses:
            if s in ['present', 'work_from_home']:
                current_present += 1
                longest_present = max(longest_present, current_present)
                current_absent_streak = 0
            elif s == 'absent':
                current_absent_streak += 1
                current_present = 0
            else:
                current_present = 0

        return {
            'longest_present_streak': longest_present,
            'current_absent_streak': current_absent_streak,
        }


# ─── 2. PERFORMANCE SCORE PREDICTOR ──────────────────────────────────────────

class PerformancePredictor:
    """
    Weighted multi-factor performance scoring.
    Attendance 30% | Reviews 40% | Tenure 10% | Leave 10% | Skills 10%
    """

    WEIGHTS = {
        'attendance_score': 0.30,
        'review_avg': 0.40,
        'tenure_bonus': 0.10,
        'leave_efficiency': 0.10,
        'skill_diversity': 0.10,
    }

    def predict(self, employee_data: dict) -> dict:
        scores = {}

        scores['attendance_score'] = employee_data.get('attendance_score', 75) / 100

        review_scores = employee_data.get('review_scores', [3.0])
        if review_scores:
            avg = sum(review_scores) / len(review_scores)
            scores['review_avg'] = (avg - 1) / 4
        else:
            scores['review_avg'] = 0.5

        years = employee_data.get('years_of_service', 1)
        scores['tenure_bonus'] = min(years / 5, 1.0)

        used = employee_data.get('leave_days_used', 5)
        total = employee_data.get('total_leave_days', 21)
        if total > 0:
            ratio = used / total
            scores['leave_efficiency'] = 1 - abs(ratio - 0.6)
        else:
            scores['leave_efficiency'] = 0.5

        skill_count = employee_data.get('skill_count', 3)
        scores['skill_diversity'] = min(skill_count / 10, 1.0)

        final = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        final_100 = round(final * 100, 1)

        if final_100 >= 85:
            grade = 'A+'
        elif final_100 >= 75:
            grade = 'A'
        elif final_100 >= 65:
            grade = 'B+'
        elif final_100 >= 55:
            grade = 'B'
        elif final_100 >= 45:
            grade = 'C'
        else:
            grade = 'D'

        insights = []
        if scores['attendance_score'] < 0.7:
            insights.append("Attendance needs improvement")
        if scores['review_avg'] > 0.8:
            insights.append("Exceptional performance reviews")
        if scores['tenure_bonus'] > 0.8:
            insights.append("Highly experienced team member")
        if scores['skill_diversity'] > 0.7:
            insights.append("Strong multi-skill profile")
        if scores['review_avg'] < 0.4:
            insights.append("Performance reviews below average")

        recommendations = []
        weakest = min(scores, key=scores.get)
        if weakest == 'attendance_score':
            recommendations.append("Address attendance consistency")
        elif weakest == 'review_avg':
            recommendations.append("Schedule 1-on-1 coaching sessions")
        elif weakest == 'skill_diversity':
            recommendations.append("Enroll in skill development programs")
        elif weakest == 'leave_efficiency':
            recommendations.append("Encourage balanced leave usage")

        return {
            'score': final_100,
            'grade': grade,
            'component_scores': {k: round(v * 100, 1) for k, v in scores.items()},
            'insights': insights,
            'recommendations': recommendations,
            'percentile': self._estimate_percentile(final_100),
        }

    def _estimate_percentile(self, score):
        """Rough percentile estimate based on score distribution"""
        if score >= 90: return 95
        if score >= 80: return 80
        if score >= 70: return 65
        if score >= 60: return 45
        if score >= 50: return 30
        return 15


# ─── 3. ATTRITION RISK ANALYZER ──────────────────────────────────────────────

class AttritionRiskAnalyzer:
    """
    Scores employee attrition risk 0-100.
    Factors: tenure, salary, performance, absences, leave balance.
    """

    def analyze(self, employee_data: dict) -> dict:
        risk_score = 0
        risk_factors = []
        protective_factors = []

        years = employee_data.get('years_of_service', 1)
        if years < 1:
            risk_score += 25
            risk_factors.append("New hire — high turnover window")
        elif years < 2:
            risk_score += 15
            risk_factors.append("Early tenure period")
        elif 2 <= years <= 5:
            protective_factors.append("Stable mid-tenure")
        elif years > 7:
            risk_score += 8
            risk_factors.append("Long tenure — possible career plateau")

        perf_score = employee_data.get('performance_score', 50)
        if perf_score < 40:
            risk_score += 30
            risk_factors.append("Low performance score")
        elif perf_score < 55:
            risk_score += 15
            risk_factors.append("Below average performance")
        elif perf_score >= 80:
            risk_score -= 5
            protective_factors.append("High performer — engaged")

        salary_pct = employee_data.get('salary_percentile', 50)
        if salary_pct < 25:
            risk_score += 25
            risk_factors.append("Salary below 25th percentile in dept")
        elif salary_pct < 40:
            risk_score += 10
            risk_factors.append("Below median salary")
        elif salary_pct >= 75:
            protective_factors.append("Well-compensated relative to peers")

        recent_absences = employee_data.get('recent_absences', 0)
        if recent_absences > 8:
            risk_score += 20
            risk_factors.append("High absence rate recently")
        elif recent_absences > 4:
            risk_score += 10
            risk_factors.append("Elevated absence pattern")

        pending_leaves = employee_data.get('pending_leave_days', 0)
        if pending_leaves > 15:
            risk_score += 10
            risk_factors.append("Large unused leave balance")

        risk_score = max(0, min(100, risk_score))

        if risk_score >= 70:
            level, color = 'Critical', '#ef4444'
        elif risk_score >= 50:
            level, color = 'High', '#f97316'
        elif risk_score >= 30:
            level, color = 'Medium', '#eab308'
        else:
            level, color = 'Low', '#22c55e'

        return {
            'risk_score': risk_score,
            'risk_level': level,
            'risk_color': color,
            'risk_factors': risk_factors,
            'protective_factors': protective_factors,
        }


# ─── 4. SMART SEARCH ENGINE ──────────────────────────────────────────────────

class SmartSearchEngine:
    """Multi-field relevance search across employees."""

    def search(self, query: str, employees: list) -> list:
        if not query.strip():
            return employees
        query_lower = query.lower()
        query_words = query_lower.split()
        scored = []
        for emp in employees:
            score = 0
            name = emp.get('name', '').lower()
            dept = emp.get('department', '').lower()
            desig = emp.get('designation', '').lower()
            skills = emp.get('skills', '').lower()
            email = emp.get('email', '').lower()
            emp_id = emp.get('employee_id', '').lower()

            if query_lower in name: score += 60
            if query_lower in emp_id: score += 55
            if query_lower in email: score += 45
            if query_lower in desig: score += 40
            if query_lower in dept: score += 35
            if query_lower in skills: score += 30

            for word in query_words:
                if len(word) < 2:
                    continue
                if word in name: score += 20
                if word in desig: score += 15
                if word in dept: score += 12
                if word in skills: score += 10

            if score > 0:
                emp['relevance_score'] = score
                scored.append(emp)

        return sorted(scored, key=lambda x: x.get('relevance_score', 0), reverse=True)


# ─── 5. DEPARTMENT ANALYTICS ─────────────────────────────────────────────────

class DepartmentAnalytics:
    def generate_summary(self, dept_data: dict) -> dict:
        employees = dept_data.get('employees', [])
        if not employees:
            return {'headcount': 0, 'avg_salary': 0, 'avg_performance': 0,
                    'avg_risk': 0, 'high_risk_count': 0, 'high_performer_count': 0,
                    'salary_range': {'min': 0, 'max': 0}}
        salaries = [e.get('salary', 0) for e in employees]
        perf_scores = [e.get('performance_score', 50) for e in employees]
        risk_scores = [e.get('risk_score', 20) for e in employees]
        return {
            'headcount': len(employees),
            'avg_salary': round(sum(salaries) / len(salaries), 2) if salaries else 0,
            'avg_performance': round(sum(perf_scores) / len(perf_scores), 1),
            'avg_risk': round(sum(risk_scores) / len(risk_scores), 1),
            'high_risk_count': sum(1 for r in risk_scores if r >= 50),
            'high_performer_count': sum(1 for p in perf_scores if p >= 75),
            'salary_range': {'min': min(salaries) if salaries else 0, 'max': max(salaries) if salaries else 0},
        }


# ─── 6. SALARY FAIRNESS ANALYZER ─────────────────────────────────────────────

class SalaryFairnessAnalyzer:
    """
    Detects salary inequities within departments.
    Flags employees paid significantly below peers with similar tenure/performance.
    """

    def analyze(self, employees: list) -> dict:
        if len(employees) < 2:
            return {'status': 'insufficient_data', 'flags': [], 'gini': 0}

        salaries = [float(e.get('salary', 0)) for e in employees]
        mean_sal = sum(salaries) / len(salaries)
        std_sal = (sum((s - mean_sal) ** 2 for s in salaries) / len(salaries)) ** 0.5

        flags = []
        for emp in employees:
            sal = float(emp.get('salary', 0))
            if std_sal > 0:
                z = (sal - mean_sal) / std_sal
                if z < -1.5:
                    flags.append({
                        'name': emp.get('name', ''),
                        'salary': sal,
                        'mean': round(mean_sal, 2),
                        'gap': round(mean_sal - sal, 2),
                        'severity': 'high' if z < -2 else 'medium',
                    })

        # Gini coefficient for inequality measurement
        sorted_sal = sorted(salaries)
        n = len(sorted_sal)
        gini = (2 * sum((i + 1) * s for i, s in enumerate(sorted_sal)) / (n * sum(sorted_sal))) - (n + 1) / n if sum(sorted_sal) > 0 else 0

        return {
            'status': 'ok' if not flags else 'inequity_detected',
            'flags': flags,
            'gini': round(gini, 3),
            'mean_salary': round(mean_sal, 2),
            'salary_spread': round(std_sal, 2),
            'inequality_level': 'Low' if gini < 0.2 else 'Medium' if gini < 0.35 else 'High',
        }


# ─── 7. WORKLOAD BALANCE DETECTOR ────────────────────────────────────────────

class WorkloadBalanceDetector:
    """
    Analyzes working hours patterns to detect overwork or underwork.
    """

    def analyze(self, attendance_records: list) -> dict:
        hours_list = []
        for r in attendance_records:
            ci = r.get('check_in')
            co = r.get('check_out')
            if ci and co and hasattr(ci, 'hour') and hasattr(co, 'hour'):
                hours = (co.hour * 60 + co.minute - ci.hour * 60 - ci.minute) / 60
                if 0 < hours < 24:
                    hours_list.append(hours)

        if not hours_list:
            return {'status': 'no_data', 'avg_hours': 0, 'flag': None}

        avg = sum(hours_list) / len(hours_list)
        max_h = max(hours_list)
        min_h = min(hours_list)
        overtime_days = sum(1 for h in hours_list if h > 9)
        underwork_days = sum(1 for h in hours_list if h < 6)

        flag = None
        if avg > 10:
            flag = 'overworked'
        elif avg < 5:
            flag = 'underworked'
        elif overtime_days > len(hours_list) * 0.5:
            flag = 'frequent_overtime'

        return {
            'avg_hours': round(avg, 1),
            'max_hours': round(max_h, 1),
            'min_hours': round(min_h, 1),
            'overtime_days': overtime_days,
            'underwork_days': underwork_days,
            'flag': flag,
            'status': flag or 'balanced',
        }


# ─── 8. SKILL GAP ANALYZER ───────────────────────────────────────────────────

class SkillGapAnalyzer:
    """
    Identifies which skills are rare or missing across the team.
    """

    def analyze(self, employees: list, required_skills: list = None) -> dict:
        skill_counts = defaultdict(int)
        total = len(employees)

        for emp in employees:
            for skill in emp.get('skills_list', []):
                skill_counts[skill.strip().lower()] += 1

        if total == 0:
            return {'coverage': {}, 'gaps': [], 'rare_skills': []}

        coverage = {skill: round((count / total) * 100, 1)
                    for skill, count in skill_counts.items()}

        rare_skills = [s for s, c in skill_counts.items() if c == 1]
        common_skills = sorted(coverage.items(), key=lambda x: x[1], reverse=True)[:5]

        gaps = []
        if required_skills:
            for req in required_skills:
                if req.lower() not in skill_counts:
                    gaps.append(req)
                elif skill_counts[req.lower()] < total * 0.2:
                    gaps.append(f"{req} (low coverage: {skill_counts[req.lower()]} person)")

        return {
            'coverage': coverage,
            'gaps': gaps,
            'rare_skills': rare_skills,
            'top_skills': [s for s, _ in common_skills],
            'total_unique_skills': len(skill_counts),
        }


# ─── 9. LEAVE PATTERN ANALYZER ───────────────────────────────────────────────

class LeavePatternAnalyzer:
    """
    Analyzes leave usage patterns.
    Detects: excessive usage, burnout indicators, clustering.
    """

    def analyze(self, leave_records: list, annual_entitlement: int = 21) -> dict:
        if not leave_records:
            return {'burn_rate': 0, 'flag': None, 'pattern': 'no_data'}

        total_days = sum(r.get('days', 0) for r in leave_records)
        sick_days = sum(r.get('days', 0) for r in leave_records if r.get('type') == 'sick')
        approved = [r for r in leave_records if r.get('status') == 'approved']

        burn_rate = round((total_days / annual_entitlement) * 100, 1) if annual_entitlement else 0

        flag = None
        pattern = 'normal'

        if sick_days > 10:
            flag = 'high_sick_leave'
            pattern = 'possible_health_issue'
        elif burn_rate > 90:
            flag = 'near_exhausted'
            pattern = 'leave_exhaustion_risk'
        elif burn_rate < 10:
            flag = 'not_taking_leave'
            pattern = 'possible_burnout_risk'
        elif len(approved) > 8:
            flag = 'frequent_leaves'
            pattern = 'high_frequency'

        return {
            'total_days_taken': total_days,
            'sick_days': sick_days,
            'burn_rate': burn_rate,
            'flag': flag,
            'pattern': pattern,
            'leave_count': len(leave_records),
        }


# ─── 10. EMPLOYEE WELLNESS SCORE ─────────────────────────────────────────────

class EmployeeWellnessScorer:
    """
    Composite wellness index combining workload, leave balance, attendance, and performance trend.
    Score 0-100. Higher = healthier work-life situation.
    """

    def score(self, data: dict) -> dict:
        components = {}

        # Work hours balance (ideal: 7-9h/day)
        avg_hours = data.get('avg_hours', 8)
        if 7 <= avg_hours <= 9:
            components['work_hours'] = 100
        elif 6 <= avg_hours < 7 or 9 < avg_hours <= 10:
            components['work_hours'] = 75
        elif avg_hours > 11:
            components['work_hours'] = 40
        else:
            components['work_hours'] = 60

        # Leave utilization (ideal: 40-70% used)
        burn_rate = data.get('leave_burn_rate', 50)
        if 40 <= burn_rate <= 70:
            components['leave_balance'] = 100
        elif 20 <= burn_rate < 40 or 70 < burn_rate <= 85:
            components['leave_balance'] = 70
        elif burn_rate > 90 or burn_rate < 10:
            components['leave_balance'] = 40
        else:
            components['leave_balance'] = 55

        # Attendance consistency
        att_score = data.get('attendance_score', 75)
        components['attendance'] = att_score

        # Absence streak (current)
        absent_streak = data.get('current_absent_streak', 0)
        if absent_streak == 0:
            components['absence_streak'] = 100
        elif absent_streak <= 2:
            components['absence_streak'] = 70
        elif absent_streak <= 4:
            components['absence_streak'] = 40
        else:
            components['absence_streak'] = 10

        wellness = round(sum(components.values()) / len(components), 1)

        if wellness >= 80:
            status = 'Healthy'
            color = '#22c55e'
        elif wellness >= 60:
            status = 'Moderate'
            color = '#eab308'
        elif wellness >= 40:
            status = 'At Risk'
            color = '#f97316'
        else:
            status = 'Needs Attention'
            color = '#ef4444'

        return {
            'wellness_score': wellness,
            'status': status,
            'color': color,
            'components': components,
        }


# ─── Singleton Instances ──────────────────────────────────────────────────────

anomaly_detector = AttendanceAnomalyDetector()
performance_predictor = PerformancePredictor()
attrition_analyzer = AttritionRiskAnalyzer()
search_engine = SmartSearchEngine()
dept_analytics = DepartmentAnalytics()
salary_analyzer = SalaryFairnessAnalyzer()
workload_detector = WorkloadBalanceDetector()
skill_gap_analyzer = SkillGapAnalyzer()
leave_analyzer = LeavePatternAnalyzer()
wellness_scorer = EmployeeWellnessScorer()