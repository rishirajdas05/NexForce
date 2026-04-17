from django.contrib import admin
from .models import Employee, Department, Attendance, LeaveRequest, PerformanceReview, Payroll

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'employee_count']

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'full_name', 'department', 'designation', 'employment_status', 'performance_score']
    list_filter = ['department', 'employment_status', 'employment_type']
    search_fields = ['first_name', 'last_name', 'email', 'employee_id']

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'status', 'check_in', 'check_out', 'is_anomaly']
    list_filter = ['status', 'is_anomaly', 'date']

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'status']
    list_filter = ['status', 'leave_type']

@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display = ['employee', 'review_period', 'review_date', 'overall_score']

@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ['employee', 'month', 'year', 'net_salary', 'status']