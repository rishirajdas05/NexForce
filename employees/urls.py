from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_page, name='login'),
    path('signup/', views.signup_page, name='signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('attendance/', views.attendance_view, name='attendance'),
    path('leave/', views.leave_management, name='leave_management'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('settings/', views.settings_view, name='settings'),

    # API
    path('api/search/', views.api_search_employees, name='api_search'),
    path('api/attendance/mark/', views.api_mark_attendance, name='api_mark_attendance'),
    path('api/leave/<int:pk>/action/', views.api_leave_action, name='api_leave_action'),
    path('api/ml/<int:employee_id>/analyze/', views.api_run_ml_analysis, name='api_ml_analyze'),
    path('api/ml/bulk-update/', views.api_ml_bulk_update, name='api_ml_bulk'),
    path('api/analytics/departments/', views.api_department_analytics, name='api_dept_analytics'),
    path('api/dashboard/stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/employee/<int:employee_id>/trend/', views.api_employee_trend, name='api_employee_trend'),
    path('api/data/create/', views.api_data_create, name='api_data_create'),
    path('admin-panel/', views.admin_panel_view, name='admin_panel'),
    path('payroll/', views.payroll_view, name='payroll'),
    path('team/', views.team_view, name='team'),
    path('reports/', views.reports_view, name='reports'),
    path('api/payroll/<int:pk>/mark-paid/', views.api_payroll_mark_paid, name='api_payroll_mark_paid'),
    path('api/payroll/generate/', views.api_payroll_generate, name='api_payroll_generate'),
    path('api/reports/<str:report_type>/', views.api_report, name='api_report'),
    path('setup/', views.setup_view, name='setup'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('profile/', views.profile_view, name='profile'),
    path('search/', views.search_view, name='search'),
    path('notifications/', views.notifications_view, name='notifications'),
]