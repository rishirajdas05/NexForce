from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q, Avg, Count, Sum, Max, Min
from django.utils import timezone
from django.contrib.auth.models import User
import json
from datetime import date, timedelta, datetime

from .models import Employee, Department, Attendance, LeaveRequest, PerformanceReview, Payroll
from ml.engine import (anomaly_detector, performance_predictor,
                        attrition_analyzer, search_engine, dept_analytics)


# ─── Auth Views ──────────────────────────────────────────────────────────────

def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'employees/login.html')


def signup_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'employees/signup.html')


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    total_employees = Employee.objects.filter(is_active=True).count()
    active_employees = Employee.objects.filter(employment_status='active').count()
    on_leave = Employee.objects.filter(employment_status='on_leave').count()
    departments = Department.objects.count()

    today = date.today()
    today_attendance = Attendance.objects.filter(date=today)
    present_today = today_attendance.filter(status__in=['present', 'work_from_home']).count()
    absent_today = today_attendance.filter(status='absent').count()

    pending_leaves = LeaveRequest.objects.filter(status='pending').count()
    high_risk_employees = Employee.objects.filter(risk_score__gte=50, is_active=True).count()

    recent_employees = Employee.objects.filter(is_active=True).order_by('-created_at')[:5]
    dept_stats = Department.objects.annotate(
        emp_count=Count('employees', filter=Q(employees__is_active=True))
    ).order_by('-emp_count')[:5]

    # Monthly attendance trend (last 7 days)
    attendance_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        present = Attendance.objects.filter(date=d, status__in=['present', 'work_from_home']).count()
        absent = Attendance.objects.filter(date=d, status='absent').count()
        attendance_trend.append({
            'date': d.strftime('%b %d'),
            'present': present,
            'absent': absent,
        })

    # Employment type breakdown
    type_breakdown = {}
    for emp_type, label in Employee.EMPLOYMENT_TYPE:
        count = Employee.objects.filter(employment_type=emp_type, is_active=True).count()
        if count > 0:
            type_breakdown[label] = count

    # Recent anomalies
    recent_anomalies = Attendance.objects.filter(
        is_anomaly=True
    ).select_related('employee').order_by('-date')[:5]

    # Top performers
    top_performers = Employee.objects.filter(
        is_active=True, performance_score__gt=0
    ).order_by('-performance_score')[:5]

    # High risk employees
    high_risk_list = Employee.objects.filter(
        is_active=True, risk_score__gte=50
    ).order_by('-risk_score')[:5]

    context = {
        'total_employees': total_employees,
        'active_employees': active_employees,
        'on_leave': on_leave,
        'departments': departments,
        'present_today': present_today,
        'absent_today': absent_today,
        'pending_leaves': pending_leaves,
        'high_risk_employees': high_risk_employees,
        'recent_employees': recent_employees,
        'dept_stats': dept_stats,
        'attendance_trend': json.dumps(attendance_trend),
        'type_breakdown': json.dumps(type_breakdown),
        'recent_anomalies': recent_anomalies,
        'top_performers': top_performers,
        'high_risk_list': high_risk_list,
    }
    return render(request, 'employees/dashboard.html', context)


# ─── Employee Views ───────────────────────────────────────────────────────────

@login_required
def employee_list(request):
    employees = Employee.objects.filter(is_active=True).select_related('department')
    departments = Department.objects.all()

    dept_filter = request.GET.get('department', '')
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')

    if dept_filter:
        employees = employees.filter(department__id=dept_filter)
    if status_filter:
        employees = employees.filter(employment_status=status_filter)
    if type_filter:
        employees = employees.filter(employment_type=type_filter)

    context = {
        'employees': employees,
        'departments': departments,
        'dept_filter': dept_filter,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'total_count': employees.count(),
    }
    return render(request, 'employees/employee_list.html', context)


@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    # Fix: evaluate queryset before slicing
    all_attendance = Attendance.objects.filter(employee=employee).order_by('-date')
    attendance_records = all_attendance[:30]
    leave_requests = LeaveRequest.objects.filter(employee=employee).order_by('-applied_on')[:10]
    performance_reviews = PerformanceReview.objects.filter(employee=employee).order_by('-review_date')[:5]
    payroll_records = Payroll.objects.filter(employee=employee).order_by('-year', '-month')[:6]

    # ML Analysis — use the unsliced queryset for filtering
    records_for_ml = list(all_attendance[:30].values('date', 'check_in', 'check_out', 'status', 'is_anomaly'))
    attendance_score = anomaly_detector.get_attendance_score(records_for_ml)
    anomalies = anomaly_detector.detect_anomaly(records_for_ml)

    review_scores = [r.overall_score for r in performance_reviews]
    emp_data_for_ml = {
        'attendance_score': attendance_score,
        'review_scores': review_scores,
        'years_of_service': employee.years_of_service,
        'skill_count': len(employee.skills_list),
    }
    perf_prediction = performance_predictor.predict(emp_data_for_ml)

    # Salary percentile within dept
    salary_list = list(Employee.objects.filter(
        department=employee.department, is_active=True
    ).values_list('salary', flat=True))
    if salary_list:
        below = sum(1 for s in salary_list if s < employee.salary)
        salary_pct = (below / len(salary_list)) * 100
    else:
        salary_pct = 50

    # Fix: count from unsliced queryset
    recent_absences = Attendance.objects.filter(employee=employee, status='absent').count()

    risk_data = {
        'years_of_service': employee.years_of_service,
        'performance_score': employee.performance_score,
        'salary_percentile': salary_pct,
        'recent_absences': recent_absences,
    }
    risk_analysis = attrition_analyzer.analyze(risk_data)

    # Attendance stats
    total_att = Attendance.objects.filter(employee=employee).count()
    present_count = Attendance.objects.filter(employee=employee, status__in=['present', 'work_from_home']).count()
    absent_count = Attendance.objects.filter(employee=employee, status='absent').count()
    late_count = Attendance.objects.filter(employee=employee, status='late').count()
    anomaly_count = Attendance.objects.filter(employee=employee, is_anomaly=True).count()

    # Monthly performance chart data
    perf_chart = []
    for review in reversed(list(performance_reviews)):
        perf_chart.append({
            'period': review.review_period,
            'score': review.overall_score,
        })

    context = {
        'employee': employee,
        'attendance_records': attendance_records,
        'leave_requests': leave_requests,
        'performance_reviews': performance_reviews,
        'payroll_records': payroll_records,
        'attendance_score': attendance_score,
        'perf_prediction': perf_prediction,
        'risk_analysis': risk_analysis,
        'anomalies_detected': len(anomalies),
        'total_att': total_att,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'anomaly_count': anomaly_count,
        'salary_pct': round(salary_pct, 1),
        'perf_chart': json.dumps(perf_chart),
    }
    return render(request, 'employees/employee_detail.html', context)


@login_required
def attendance_view(request):
    employees = Employee.objects.filter(is_active=True).select_related('department')
    today = date.today()
    today_records = {a.employee_id: a for a in Attendance.objects.filter(date=today)}

    # Attendance stats for today
    present_count = sum(1 for a in today_records.values() if a.status in ['present', 'work_from_home'])
    absent_count = sum(1 for a in today_records.values() if a.status == 'absent')
    late_count = sum(1 for a in today_records.values() if a.status == 'late')
    not_marked = employees.count() - len(today_records)

    context = {
        'employees': employees,
        'today_records': today_records,
        'today': today,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'not_marked': not_marked,
    }
    return render(request, 'employees/attendance.html', context)


@login_required
def leave_management(request):
    leaves = LeaveRequest.objects.select_related(
        'employee', 'employee__department', 'approved_by'
    ).order_by('-applied_on')

    pending_count = leaves.filter(status='pending').count()
    approved_count = leaves.filter(status='approved').count()
    rejected_count = leaves.filter(status='rejected').count()

    context = {
        'leaves': leaves,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    return render(request, 'employees/leave_management.html', context)


@login_required
def analytics_view(request):
    departments = Department.objects.annotate(
        emp_count=Count('employees', filter=Q(employees__is_active=True)),
        avg_salary=Avg('employees__salary', filter=Q(employees__is_active=True)),
        avg_perf=Avg('employees__performance_score', filter=Q(employees__is_active=True)),
    )

    risk_low = Employee.objects.filter(risk_score__lt=30, is_active=True).count()
    risk_medium = Employee.objects.filter(risk_score__gte=30, risk_score__lt=50, is_active=True).count()
    risk_high = Employee.objects.filter(risk_score__gte=50, risk_score__lt=70, is_active=True).count()
    risk_critical = Employee.objects.filter(risk_score__gte=70, is_active=True).count()

    # Performance distribution
    perf_excellent = Employee.objects.filter(performance_score__gte=80, is_active=True).count()
    perf_good = Employee.objects.filter(performance_score__gte=60, performance_score__lt=80, is_active=True).count()
    perf_average = Employee.objects.filter(performance_score__gte=40, performance_score__lt=60, is_active=True).count()
    perf_poor = Employee.objects.filter(performance_score__lt=40, is_active=True).count()

    # Salary stats
    salary_stats = Employee.objects.filter(is_active=True).aggregate(
        avg=Avg('salary'),
        max=Max('salary'),
        min=Min('salary'),
    )

    # Attendance last 30 days
    thirty_days_ago = date.today() - timedelta(days=30)
    attendance_rate = 0
    total_records = Attendance.objects.filter(date__gte=thirty_days_ago).count()
    present_records = Attendance.objects.filter(
        date__gte=thirty_days_ago,
        status__in=['present', 'work_from_home']
    ).count()
    if total_records:
        attendance_rate = round((present_records / total_records) * 100, 1)

    # Top skills across all employees
    all_skills = []
    for emp in Employee.objects.filter(is_active=True):
        all_skills.extend(emp.skills_list)
    skill_counts = {}
    for skill in all_skills:
        skill_counts[skill] = skill_counts.get(skill, 0) + 1
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    ml_models = [
        {'name': 'Anomaly Detector', 'desc': 'Z-score attendance pattern analysis'},
        {'name': 'Performance Predictor', 'desc': 'Weighted multi-factor scoring'},
        {'name': 'Attrition Risk Analyzer', 'desc': 'Heuristic flight risk scoring'},
        {'name': 'Salary Fairness', 'desc': 'Gini coefficient + Z-score gap'},
        {'name': 'Wellness Score', 'desc': 'Composite workload + leave index'},
    ]

    context = {
        'departments': departments,
        'risk_distribution': json.dumps({
            'Low': risk_low,
            'Medium': risk_medium,
            'High': risk_high,
            'Critical': risk_critical,
        }),
        'perf_distribution': json.dumps({
            'Excellent (80+)': perf_excellent,
            'Good (60-79)': perf_good,
            'Average (40-59)': perf_average,
            'Poor (<40)': perf_poor,
        }),
        'salary_stats': salary_stats,
        'attendance_rate': attendance_rate,
        'top_skills': top_skills,
        'total_anomalies': Attendance.objects.filter(is_anomaly=True).count(),
        'total_employees': Employee.objects.filter(is_active=True).count(),
        'ml_models': ml_models,
    }
    return render(request, 'employees/analytics.html', context)


@login_required
def settings_view(request):
    user = request.user
    total_employees = Employee.objects.filter(is_active=True).count()
    total_departments = Department.objects.count()
    total_reviews = PerformanceReview.objects.count()
    total_attendance = Attendance.objects.count()
    total_leaves = LeaveRequest.objects.count()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.save()
            return JsonResponse({'success': True, 'message': 'Profile updated'})
        elif action == 'run_ml_all':
            updated = 0
            for emp in Employee.objects.filter(is_active=True):
                att_records = list(Attendance.objects.filter(employee=emp).order_by('-date')[:30].values(
                    'date', 'check_in', 'check_out', 'status', 'is_anomaly'
                ))
                att_score = anomaly_detector.get_attendance_score(att_records)
                reviews = list(PerformanceReview.objects.filter(employee=emp).values_list('quality_score', 'productivity_score', 'teamwork_score', 'communication_score', 'initiative_score'))
                review_scores = [sum(r)/5 for r in reviews] if reviews else [3.0]
                perf = performance_predictor.predict({
                    'attendance_score': att_score,
                    'review_scores': review_scores,
                    'years_of_service': emp.years_of_service,
                    'skill_count': len(emp.skills_list),
                })
                salary_list = list(Employee.objects.filter(department=emp.department, is_active=True).values_list('salary', flat=True))
                salary_pct = 50
                if salary_list:
                    below = sum(1 for s in salary_list if s < emp.salary)
                    salary_pct = (below / len(salary_list)) * 100
                risk = attrition_analyzer.analyze({
                    'years_of_service': emp.years_of_service,
                    'performance_score': perf['score'],
                    'salary_percentile': salary_pct,
                    'recent_absences': Attendance.objects.filter(employee=emp, status='absent').count(),
                })
                emp.performance_score = perf['score']
                emp.risk_score = risk['risk_score']
                emp.last_ml_update = timezone.now()
                emp.save()
                updated += 1
            return JsonResponse({'success': True, 'message': f'ML scores updated for {updated} employees'})

    ml_models = [
        {'name': 'Anomaly Detector', 'desc': 'Z-score attendance pattern analysis'},
        {'name': 'Performance Predictor', 'desc': 'Weighted multi-factor scoring'},
        {'name': 'Attrition Risk Analyzer', 'desc': 'Heuristic flight risk scoring'},
        {'name': 'Smart Search Engine', 'desc': 'Multi-field relevance ranking'},
        {'name': 'Department Analytics', 'desc': 'Statistical aggregation'},
        {'name': 'Salary Fairness Analyzer', 'desc': 'Gini coefficient + Z-score gap detection'},
        {'name': 'Workload Balance Detector', 'desc': 'Overtime and underwork flagging'},
        {'name': 'Skill Gap Analyzer', 'desc': 'Team skill coverage mapping'},
        {'name': 'Leave Pattern Analyzer', 'desc': 'Burn rate and burnout risk detection'},
        {'name': 'Wellness Score', 'desc': 'Composite workload + leave + attendance index'},
    ]

    months = [
        {'val': 1, 'label': 'January'}, {'val': 2, 'label': 'February'},
        {'val': 3, 'label': 'March'}, {'val': 4, 'label': 'April'},
        {'val': 5, 'label': 'May'}, {'val': 6, 'label': 'June'},
        {'val': 7, 'label': 'July'}, {'val': 8, 'label': 'August'},
        {'val': 9, 'label': 'September'}, {'val': 10, 'label': 'October'},
        {'val': 11, 'label': 'November'}, {'val': 12, 'label': 'December'},
    ]

    context = {
        'user': user,
        'total_employees': total_employees,
        'total_departments': total_departments,
        'total_reviews': total_reviews,
        'total_attendance': total_attendance,
        'total_leaves': total_leaves,
        'ml_models': ml_models,
        'months': months,
        'departments': Department.objects.all(),
        'employees': Employee.objects.filter(is_active=True).order_by('first_name'),
    }
    return render(request, 'employees/settings.html', context)


# ─── API Endpoints ─────────────────────────────────────────────────────────────

@login_required
def api_search_employees(request):
    query = request.GET.get('q', '')
    emp_qs = Employee.objects.filter(is_active=True).select_related('department')
    emp_list = [{
        'id': e.pk,
        'name': e.full_name,
        'email': e.email,
        'department': e.department.name if e.department else '',
        'designation': e.designation,
        'skills': e.skills,
        'employee_id': e.employee_id,
        'employment_status': e.employment_status,
    } for e in emp_qs]
    results = search_engine.search(query, emp_list)
    return JsonResponse({'results': results[:20], 'query': query})


@login_required
def api_mark_attendance(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    data = json.loads(request.body)
    employee_id = data.get('employee_id')
    status = data.get('status', 'present')
    check_in = data.get('check_in')
    check_out = data.get('check_out')
    employee = get_object_or_404(Employee, pk=employee_id)
    attendance, created = Attendance.objects.update_or_create(
        employee=employee,
        date=date.today(),
        defaults={
            'status': status,
            'check_in': check_in,
            'check_out': check_out,
        }
    )
    recent_records = list(Attendance.objects.filter(employee=employee).order_by('-date')[:20].values(
        'date', 'check_in', 'check_out', 'status', 'is_anomaly'
    ))
    anomalies = anomaly_detector.detect_anomaly(recent_records)
    if anomalies:
        attendance.is_anomaly = True
        attendance.anomaly_reason = '; '.join(anomalies[0].get('reasons', []))
        attendance.save()
    return JsonResponse({'success': True, 'created': created, 'is_anomaly': attendance.is_anomaly})


@login_required
def api_leave_action(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    leave = get_object_or_404(LeaveRequest, pk=pk)
    data = json.loads(request.body)
    action = data.get('action')
    if action == 'approve':
        leave.status = 'approved'
        leave.approved_by = request.user
        leave.reviewed_on = timezone.now()
        leave.save()
        leave.employee.employment_status = 'on_leave'
        leave.employee.save()
    elif action == 'reject':
        leave.status = 'rejected'
        leave.approved_by = request.user
        leave.reviewed_on = timezone.now()
        leave.save()
    return JsonResponse({'success': True, 'status': leave.status})


@login_required
def api_run_ml_analysis(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    att_records = list(Attendance.objects.filter(employee=employee).order_by('-date')[:30].values(
        'date', 'check_in', 'check_out', 'status', 'is_anomaly'
    ))
    attendance_score = anomaly_detector.get_attendance_score(att_records)
    anomalies = anomaly_detector.detect_anomaly(att_records)
    reviews = PerformanceReview.objects.filter(employee=employee)
    review_scores = [r.overall_score for r in reviews]
    emp_data = {
        'attendance_score': attendance_score,
        'review_scores': review_scores,
        'years_of_service': employee.years_of_service,
        'skill_count': len(employee.skills_list),
    }
    perf = performance_predictor.predict(emp_data)

    salary_list = list(Employee.objects.filter(department=employee.department, is_active=True).values_list('salary', flat=True))
    salary_pct = 50
    if salary_list:
        below = sum(1 for s in salary_list if s < employee.salary)
        salary_pct = (below / len(salary_list)) * 100

    recent_absences = Attendance.objects.filter(employee=employee, status='absent').count()
    risk = attrition_analyzer.analyze({
        'years_of_service': employee.years_of_service,
        'performance_score': perf['score'],
        'salary_percentile': salary_pct,
        'recent_absences': recent_absences,
    })

    employee.performance_score = perf['score']
    employee.risk_score = risk['risk_score']
    employee.last_ml_update = timezone.now()
    employee.save()

    return JsonResponse({
        'employee': employee.full_name,
        'performance': perf,
        'risk': risk,
        'attendance_score': attendance_score,
        'anomalies_detected': len(anomalies),
    })


@login_required
def api_department_analytics(request):
    departments = Department.objects.prefetch_related('employees').all()
    result = []
    for dept in departments:
        employees = dept.employees.filter(is_active=True)
        emp_data = [{
            'salary': float(e.salary),
            'performance_score': e.performance_score,
            'risk_score': e.risk_score,
        } for e in employees]
        summary = dept_analytics.generate_summary({'employees': emp_data})
        summary['name'] = dept.name
        summary['code'] = dept.code
        result.append(summary)
    return JsonResponse({'departments': result})


@login_required
def api_dashboard_stats(request):
    today = date.today()
    stats = {
        'total': Employee.objects.filter(is_active=True).count(),
        'present': Attendance.objects.filter(date=today, status__in=['present', 'work_from_home']).count(),
        'absent': Attendance.objects.filter(date=today, status='absent').count(),
        'on_leave': Employee.objects.filter(employment_status='on_leave').count(),
        'pending_leaves': LeaveRequest.objects.filter(status='pending').count(),
        'high_risk': Employee.objects.filter(risk_score__gte=50, is_active=True).count(),
    }
    return JsonResponse(stats)


@login_required
def api_ml_bulk_update(request):
    """Run ML analysis on all employees at once"""
    updated = 0
    for emp in Employee.objects.filter(is_active=True):
        att_records = list(Attendance.objects.filter(employee=emp).order_by('-date')[:30].values(
            'date', 'check_in', 'check_out', 'status', 'is_anomaly'
        ))
        att_score = anomaly_detector.get_attendance_score(att_records)
        reviews = list(PerformanceReview.objects.filter(employee=emp))
        review_scores = [r.overall_score for r in reviews] if reviews else [3.0]
        perf = performance_predictor.predict({
            'attendance_score': att_score,
            'review_scores': review_scores,
            'years_of_service': emp.years_of_service,
            'skill_count': len(emp.skills_list),
        })
        salary_list = list(Employee.objects.filter(department=emp.department, is_active=True).values_list('salary', flat=True))
        salary_pct = 50
        if salary_list:
            below = sum(1 for s in salary_list if s < emp.salary)
            salary_pct = (below / len(salary_list)) * 100
        risk = attrition_analyzer.analyze({
            'years_of_service': emp.years_of_service,
            'performance_score': perf['score'],
            'salary_percentile': salary_pct,
            'recent_absences': Attendance.objects.filter(employee=emp, status='absent').count(),
        })
        emp.performance_score = perf['score']
        emp.risk_score = risk['risk_score']
        emp.last_ml_update = timezone.now()
        emp.save()
        updated += 1
    return JsonResponse({'success': True, 'updated': updated, 'message': f'Updated {updated} employees'})


@login_required
def api_employee_trend(request, employee_id):
    """Attendance trend for last 30 days for a specific employee"""
    employee = get_object_or_404(Employee, pk=employee_id)
    trend = []
    for i in range(29, -1, -1):
        d = date.today() - timedelta(days=i)
        try:
            att = Attendance.objects.get(employee=employee, date=d)
            status = att.status
            hours = att.hours_worked
        except Attendance.DoesNotExist:
            status = 'no_record'
            hours = 0
        trend.append({'date': d.strftime('%b %d'), 'status': status, 'hours': hours})
    return JsonResponse({'trend': trend, 'employee': employee.full_name})


@login_required
def api_data_create(request):
    """Single endpoint handling all in-app form creations"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    record_type = data.get('type')

    try:
        if record_type == 'employee':
            dept = None
            if data.get('department'):
                dept = Department.objects.filter(pk=data['department']).first()
            emp = Employee.objects.create(
                first_name=data['first_name'],
                last_name=data['last_name'],
                employee_id=data['employee_id'],
                email=data['email'],
                phone=data.get('phone', ''),
                designation=data['designation'],
                department=dept,
                employment_type=data.get('employment_type', 'full_time'),
                salary=float(data.get('salary') or 0),
                date_joined=data.get('date_joined') or date.today(),
                gender=data.get('gender', 'M'),
                skills=data.get('skills', ''),
            )
            return JsonResponse({'success': True, 'message': f'Employee {emp.full_name} added successfully', 'id': emp.pk})

        elif record_type == 'department':
            dept = Department.objects.create(
                name=data['name'],
                code=data['code'],
                description=data.get('description', ''),
            )
            return JsonResponse({'success': True, 'message': f'Department "{dept.name}" created'})

        elif record_type == 'review':
            emp = get_object_or_404(Employee, pk=data['employee'])
            review = PerformanceReview.objects.create(
                employee=emp,
                reviewer=request.user,
                review_period=data['review_period'],
                review_date=data['review_date'],
                quality_score=int(data.get('quality_score', 3)),
                productivity_score=int(data.get('productivity_score', 3)),
                teamwork_score=int(data.get('teamwork_score', 3)),
                communication_score=int(data.get('communication_score', 3)),
                initiative_score=int(data.get('initiative_score', 3)),
                comments=data.get('comments', ''),
            )
            return JsonResponse({'success': True, 'message': f'Review added for {emp.full_name} — score: {review.overall_score}/5'})

        elif record_type == 'leave':
            emp = get_object_or_404(Employee, pk=data['employee'])
            leave = LeaveRequest.objects.create(
                employee=emp,
                leave_type=data['leave_type'],
                start_date=data['start_date'],
                end_date=data['end_date'],
                reason=data['reason'],
                status=data.get('status', 'pending'),
            )
            return JsonResponse({'success': True, 'message': f'Leave request added for {emp.full_name} ({leave.days_count} days)'})

        elif record_type == 'payroll':
            emp = get_object_or_404(Employee, pk=data['employee'])
            payroll = Payroll.objects.create(
                employee=emp,
                month=int(data['month']),
                year=int(data['year']),
                basic_salary=float(data['basic_salary']),
                allowances=float(data.get('allowances', 0)),
                deductions=float(data.get('deductions', 0)),
                tax=float(data.get('tax', 0)),
                net_salary=float(data['net_salary']),
                status=data.get('status', 'pending'),
            )
            return JsonResponse({'success': True, 'message': f'Payroll record added for {emp.full_name} — net ₹{payroll.net_salary:,.0f}'})

        elif record_type == 'edit_employee':
            emp = get_object_or_404(Employee, pk=data['id'])
            if data.get('first_name'): emp.first_name = data['first_name']
            if data.get('last_name'): emp.last_name = data['last_name']
            if data.get('designation'): emp.designation = data['designation']
            if data.get('employment_status'): emp.employment_status = data['employment_status']
            if data.get('salary'): emp.salary = float(data['salary'])
            emp.save()
            return JsonResponse({'success': True, 'message': f'{emp.full_name} updated successfully'})

        else:
            return JsonResponse({'error': 'Unknown type'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def admin_panel_view(request):
    stats = {
        'employees': Employee.objects.filter(is_active=True).count(),
        'departments': Department.objects.count(),
        'attendance': Attendance.objects.count(),
        'leaves': LeaveRequest.objects.count(),
        'reviews': PerformanceReview.objects.count(),
        'payrolls': Payroll.objects.count(),
    }
    tabs = [
        {'id': 'employees', 'label': 'Employees', 'icon': 'fa-users'},
        {'id': 'departments', 'label': 'Departments', 'icon': 'fa-building'},
        {'id': 'attendance', 'label': 'Attendance', 'icon': 'fa-calendar-check'},
        {'id': 'leaves', 'label': 'Leave Requests', 'icon': 'fa-calendar-minus'},
        {'id': 'payroll', 'label': 'Payroll', 'icon': 'fa-money-bill'},
        {'id': 'reviews', 'label': 'Reviews', 'icon': 'fa-star'},
    ]
    context = {
        'stats': stats,
        'tabs': tabs,
        'all_employees': Employee.objects.filter(is_active=True).select_related('department').order_by('first_name'),
        'all_departments': Department.objects.all(),
        'recent_attendance': Attendance.objects.select_related('employee').order_by('-date', '-created_at')[:50],
        'all_leaves': LeaveRequest.objects.select_related('employee', 'employee__department').order_by('-applied_on'),
        'all_payrolls': Payroll.objects.select_related('employee').order_by('-year', '-month')[:50],
        'all_reviews': PerformanceReview.objects.select_related('employee').order_by('-review_date')[:50],

    }
    return render(request, 'employees/admin_panel.html', context)


@login_required
def payroll_view(request):
    from django.db.models import Sum, Avg
    payrolls = Payroll.objects.select_related('employee', 'employee__department').order_by('-year', '-month')

    current_month = date.today().month
    current_year = date.today().year

    total_payout = Payroll.objects.filter(
        month=current_month, year=current_year
    ).aggregate(total=Sum('net_salary'))['total'] or 0

    paid_count = Payroll.objects.filter(status='paid').count()
    pending_count = Payroll.objects.filter(status='pending').count()
    avg_salary = Payroll.objects.aggregate(avg=Avg('net_salary'))['avg'] or 0

    # Salary by department
    dept_salary = []
    for dept in Department.objects.all():
        avg = Employee.objects.filter(
            department=dept, is_active=True
        ).aggregate(avg=Avg('salary'))['avg'] or 0
        if avg > 0:
            dept_salary.append({'name': dept.name, 'avg': float(avg)})

    context = {
        'payrolls': payrolls,
        'total_payout': total_payout,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'avg_salary': avg_salary,
        'salary_by_dept': json.dumps(dept_salary),
    }
    return render(request, 'employees/payroll.html', context)


@login_required
def team_view(request):
    employees = Employee.objects.filter(is_active=True).select_related('department').order_by('department__name', 'first_name')
    departments = Department.objects.all()
    context = {
        'employees': employees,
        'departments': departments,
    }
    return render(request, 'employees/team.html', context)


@login_required
def reports_view(request):
    return render(request, 'employees/reports.html')


@login_required
def api_payroll_mark_paid(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    payroll = get_object_or_404(Payroll, pk=pk)
    payroll.status = 'paid'
    payroll.payment_date = date.today()
    payroll.save()
    return JsonResponse({'success': True})


@login_required
def api_payroll_generate(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    data = json.loads(request.body)
    month = int(data.get('month', date.today().month))
    year = int(data.get('year', date.today().year))

    employees = Employee.objects.filter(is_active=True)
    created = 0
    skipped = 0
    for emp in employees:
        if Payroll.objects.filter(employee=emp, month=month, year=year).exists():
            skipped += 1
            continue
        basic = float(emp.salary)
        allowances = basic * 0.1
        deductions = basic * 0.05
        tax = basic * 0.08
        net = basic + allowances - deductions - tax
        Payroll.objects.create(
            employee=emp,
            month=month,
            year=year,
            basic_salary=basic,
            allowances=round(allowances, 2),
            deductions=round(deductions, 2),
            tax=round(tax, 2),
            net_salary=round(net, 2),
            status='pending',
        )
        created += 1
    return JsonResponse({
        'success': True,
        'message': f'Generated {created} payroll records for {month}/{year}. {skipped} already existed.'
    })


@login_required
def api_report(request, report_type):
    if report_type == 'headcount':
        headers = ['Name', 'Employee ID', 'Department', 'Designation', 'Type', 'Status', 'Joined', 'Tenure (yrs)']
        rows = []
        for emp in Employee.objects.filter(is_active=True).select_related('department').order_by('department__name', 'first_name'):
            rows.append([
                emp.full_name, emp.employee_id,
                emp.department.name if emp.department else '—',
                emp.designation,
                emp.get_employment_type_display(),
                emp.get_employment_status_display(),
                emp.date_joined.strftime('%Y-%m-%d'),
                str(emp.years_of_service),
            ])
        return JsonResponse({'title': 'Headcount Report', 'headers': headers, 'rows': rows})

    elif report_type == 'attendance':
        headers = ['Employee', 'Department', 'Present', 'Absent', 'Late', 'WFH', 'Anomalies', 'Attendance %']
        rows = []
        thirty_ago = date.today() - timedelta(days=30)
        for emp in Employee.objects.filter(is_active=True).select_related('department'):
            recs = Attendance.objects.filter(employee=emp, date__gte=thirty_ago)
            total = recs.count()
            present = recs.filter(status__in=['present', 'work_from_home']).count()
            absent = recs.filter(status='absent').count()
            late = recs.filter(status='late').count()
            wfh = recs.filter(status='work_from_home').count()
            anomalies = recs.filter(is_anomaly=True).count()
            rate = f"{round((present/total)*100,1)}%" if total > 0 else "N/A"
            rows.append([emp.full_name, emp.department.name if emp.department else '—',
                         str(present), str(absent), str(late), str(wfh), str(anomalies), rate])
        return JsonResponse({'title': 'Attendance Report (Last 30 Days)', 'headers': headers, 'rows': rows})

    elif report_type == 'payroll':
        headers = ['Employee', 'Department', 'Month', 'Year', 'Basic', 'Allowances', 'Deductions', 'Tax', 'Net', 'Status']
        rows = []
        for pay in Payroll.objects.select_related('employee', 'employee__department').order_by('-year', '-month'):
            rows.append([
                pay.employee.full_name,
                pay.employee.department.name if pay.employee.department else '—',
                str(pay.month), str(pay.year),
                f"₹{pay.basic_salary:,.0f}", f"₹{pay.allowances:,.0f}",
                f"₹{pay.deductions:,.0f}", f"₹{pay.tax:,.0f}",
                f"₹{pay.net_salary:,.0f}", pay.status,
            ])
        return JsonResponse({'title': 'Payroll Report', 'headers': headers, 'rows': rows})

    elif report_type == 'performance':
        headers = ['Employee', 'Department', 'Performance Score', 'Grade', 'Risk Score', 'Risk Level', 'Last ML Update']
        rows = []
        for emp in Employee.objects.filter(is_active=True).select_related('department').order_by('-performance_score'):
            risk_level = 'Critical' if emp.risk_score >= 70 else 'High' if emp.risk_score >= 50 else 'Medium' if emp.risk_score >= 30 else 'Low'
            grade = 'A+' if emp.performance_score >= 85 else 'A' if emp.performance_score >= 75 else 'B+' if emp.performance_score >= 65 else 'B' if emp.performance_score >= 55 else 'C' if emp.performance_score >= 45 else 'D'
            rows.append([
                emp.full_name,
                emp.department.name if emp.department else '—',
                str(round(emp.performance_score, 1)),
                grade,
                str(round(emp.risk_score, 1)),
                risk_level,
                emp.last_ml_update.strftime('%Y-%m-%d %H:%M') if emp.last_ml_update else 'Never',
            ])
        return JsonResponse({'title': 'Performance Report', 'headers': headers, 'rows': rows})

    elif report_type == 'attrition':
        headers = ['Employee', 'Department', 'Risk Score', 'Risk Level', 'Tenure', 'Performance', 'Salary']
        rows = []
        for emp in Employee.objects.filter(is_active=True).select_related('department').order_by('-risk_score'):
            risk_level = 'Critical' if emp.risk_score >= 70 else 'High' if emp.risk_score >= 50 else 'Medium' if emp.risk_score >= 30 else 'Low'
            rows.append([
                emp.full_name,
                emp.department.name if emp.department else '—',
                str(round(emp.risk_score, 1)),
                risk_level,
                f"{emp.years_of_service} yrs",
                str(round(emp.performance_score, 1)),
                f"₹{emp.salary:,.0f}",
            ])
        return JsonResponse({'title': 'Attrition Risk Report', 'headers': headers, 'rows': rows})

    elif report_type == 'leave':
        headers = ['Employee', 'Department', 'Leave Type', 'Start', 'End', 'Days', 'Status', 'Applied On']
        rows = []
        for leave in LeaveRequest.objects.select_related('employee', 'employee__department').order_by('-applied_on'):
            rows.append([
                leave.employee.full_name,
                leave.employee.department.name if leave.employee.department else '—',
                leave.get_leave_type_display(),
                leave.start_date.strftime('%Y-%m-%d'),
                leave.end_date.strftime('%Y-%m-%d'),
                str(leave.days_count),
                leave.status,
                leave.applied_on.strftime('%Y-%m-%d'),
            ])
        return JsonResponse({'title': 'Leave Report', 'headers': headers, 'rows': rows})

    return JsonResponse({'error': 'Unknown report type'}, status=400)


@login_required
def calendar_view(request):
    from collections import defaultdict
    cal_events = defaultdict(list)

    # Leave requests
    for leave in LeaveRequest.objects.filter(status='approved').select_related('employee'):
        current = leave.start_date
        while current <= leave.end_date:
            cal_events[str(current)].append({
                'title': f"{leave.employee.first_name} — {leave.get_leave_type_display()}",
                'type': 'leave',
            })
            current += timedelta(days=1)

    # Birthdays
    for emp in Employee.objects.filter(is_active=True, date_of_birth__isnull=False):
        today = date.today()
        bday = emp.date_of_birth.replace(year=today.year)
        cal_events[str(bday)].append({
            'title': f"{emp.first_name}'s Birthday",
            'type': 'birthday',
        })

    # Performance reviews
    for rev in PerformanceReview.objects.select_related('employee').order_by('-review_date')[:20]:
        cal_events[str(rev.review_date)].append({
            'title': f"{rev.employee.first_name} Review — {rev.review_period}",
            'type': 'review',
        })

    context = {
        'cal_events': json.dumps(dict(cal_events)),
    }
    return render(request, 'employees/calendar.html', context)


@login_required
def profile_view(request):
    linked_employee = Employee.objects.filter(user=request.user).first()
    total_employees = Employee.objects.filter(is_active=True).count()
    leaves_reviewed = LeaveRequest.objects.filter(approved_by=request.user).count()
    reviews_submitted = PerformanceReview.objects.filter(reviewer=request.user).count()
    ml_runs = Employee.objects.filter(last_ml_update__isnull=False).count()

    context = {
        'linked_employee': linked_employee,
        'total_employees': total_employees,
        'leaves_reviewed': leaves_reviewed,
        'reviews_submitted': reviews_submitted,
        'ml_runs': ml_runs,
    }
    return render(request, 'employees/profile.html', context)


@login_required
def search_view(request):
    query = request.GET.get('q', '')

    # Popular skills
    all_skills = []
    for emp in Employee.objects.filter(is_active=True):
        all_skills.extend(emp.skills_list)
    skill_counts = {}
    for s in all_skills:
        skill_counts[s] = skill_counts.get(s, 0) + 1
    popular_skills = sorted(skill_counts, key=skill_counts.get, reverse=True)[:8]

    context = {
        'query': query,
        'popular_skills': popular_skills,
    }
    return render(request, 'employees/search.html', context)


@login_required
def notifications_view(request):
    high_risk = Employee.objects.filter(risk_score__gte=50, is_active=True).order_by('-risk_score')[:5]
    pending_leaves = LeaveRequest.objects.filter(status='pending').select_related('employee').order_by('-applied_on')[:5]
    anomaly_records = Attendance.objects.filter(is_anomaly=True).select_related('employee').order_by('-date')[:5]

    context = {
        'high_risk_employees': high_risk,
        'pending_leaves': pending_leaves,
        'anomaly_records': anomaly_records,
        'system_notifications': [],
    }
    return render(request, 'employees/notifications.html', context)


def setup_view(request):
    """
    One-time setup URL for Render deployment.
    Visit /setup/ after deploying to create admin and configure site.
    Disabled after first use via SETUP_DONE env var.
    """
    import os
    from django.http import HttpResponse
    from django.contrib.sites.models import Site

    if os.environ.get('SETUP_DONE') == 'true':
        return HttpResponse("Setup already done. Remove SETUP_DONE env var to re-run.", status=403)

    log = []

    # Create superuser
    try:
        from allauth.account.models import EmailAddress
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser('admin', 'admin@nexforce.com', 'admin123')
            log.append("✅ Admin created — username: admin / password: admin123")
        else:
            admin = User.objects.get(username='admin')
            log.append("ℹ️ Admin already exists")

        # Ensure EmailAddress record exists for email login
        email_obj, created = EmailAddress.objects.get_or_create(
            user=admin,
            email='admin@nexforce.com',
            defaults={'primary': True, 'verified': True}
        )
        if not email_obj.verified:
            email_obj.verified = True
            email_obj.primary = True
            email_obj.save()
        log.append(f"✅ Admin email confirmed for login ({'created' if created else 'already exists'})")

        # Fix all existing users' email addresses
        for user in User.objects.filter(email__isnull=False).exclude(email=''):
            EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={'primary': True, 'verified': True}
            )
        log.append("✅ All user emails confirmed")
    except Exception as e:
        log.append(f"❌ Admin error: {e}")

    # Fix site domain
    try:
        site = Site.objects.first()
        host = request.get_host().split(':')[0]
        site.domain = host
        site.name = 'NexForce EMS'
        site.save()
        log.append(f"✅ Site domain set to: {host}")
    except Exception as e:
        log.append(f"❌ Site error: {e}")

    # Google OAuth — using APP config in settings.py via env vars
    # Delete any DB entries to avoid MultipleObjectsReturned conflict
    try:
        from allauth.socialaccount.models import SocialApp
        google_id = os.environ.get('GOOGLE_CLIENT_ID')
        if google_id:
            deleted = SocialApp.objects.filter(provider='google').delete()
            if deleted[0] > 0:
                log.append(f"🗑️ Deleted {deleted[0]} DB Google app(s) — using env vars instead")
            else:
                log.append("✅ No duplicate Google apps in DB — credentials loaded from env vars")
        else:
            log.append("⚠️ GOOGLE_CLIENT_ID not set in Render environment variables")
    except Exception as e:
        log.append(f"❌ Google OAuth cleanup error: {e}")

    # Run seed
    try:
        from django.core.management import call_command
        emp_count = Employee.objects.count()
        if emp_count == 0:
            call_command('seed_demo')
            log.append(f"✅ Demo data seeded — {Employee.objects.count()} employees created")
        else:
            log.append(f"ℹ️ Employees already exist ({emp_count} employees)")
    except Exception as e:
        log.append(f"❌ Seed error: {e}")

    log.append("")
    log.append("⚠️  IMPORTANT: Add SETUP_DONE=true in Render Environment Variables to disable this URL.")
    log.append("Then visit /admin/ to log in with admin / admin123")

    html = "<pre style='font-family:monospace;padding:20px;background:#111;color:#eee;min-height:100vh;'>"
    html += "<h2 style='color:#6c63ff;'>NexForce EMS — Setup</h2>"
    html += "\n".join(log)
    html += f"\n\n<a href='/admin/' style='color:#6c63ff;'>→ Go to Admin Panel</a>"
    html += f"\n<a href='/' style='color:#6c63ff;'>→ Go to Login Page</a>"
    html += "</pre>"

    return HttpResponse(html)