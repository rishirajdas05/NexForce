from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    head = models.ForeignKey('Employee', null=True, blank=True, on_delete=models.SET_NULL, related_name='headed_dept')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def employee_count(self):
        return self.employees.filter(is_active=True).count()


class Employee(models.Model):
    EMPLOYMENT_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
        ('terminated', 'Terminated'),
    ]
    EMPLOYMENT_TYPE = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('intern', 'Intern'),
    ]
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL)
    employee_id = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)

    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    designation = models.CharField(max_length=100)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE, default='full_time')
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_STATUS, default='active')

    date_joined = models.DateField(default=timezone.now)
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    manager = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subordinates')

    skills = models.TextField(blank=True, help_text='Comma-separated skills')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ML-computed fields
    performance_score = models.FloatField(default=0.0)
    risk_score = models.FloatField(default=0.0)  # attrition risk
    last_ml_update = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def skills_list(self):
        return [s.strip() for s in self.skills.split(',') if s.strip()]

    @property
    def years_of_service(self):
        from datetime import date
        delta = date.today() - self.date_joined
        return round(delta.days / 365, 1)


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('work_from_home', 'Work From Home'),
        ('on_leave', 'On Leave'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    notes = models.TextField(blank=True)
    is_anomaly = models.BooleanField(default=False)
    anomaly_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee.full_name} - {self.date} - {self.status}"

    @property
    def hours_worked(self):
        if self.check_in and self.check_out:
            from datetime import datetime, date
            ci = datetime.combine(date.today(), self.check_in)
            co = datetime.combine(date.today(), self.check_out)
            diff = co - ci
            return round(diff.seconds / 3600, 2)
        return 0


class LeaveRequest(models.Model):
    LEAVE_TYPE = [
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('unpaid', 'Unpaid Leave'),
        ('emergency', 'Emergency Leave'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    applied_on = models.DateTimeField(auto_now_add=True)
    reviewed_on = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.leave_type} ({self.start_date} to {self.end_date})"

    @property
    def days_count(self):
        delta = self.end_date - self.start_date
        return delta.days + 1


class PerformanceReview(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='performance_reviews')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    review_period = models.CharField(max_length=50)
    review_date = models.DateField()

    quality_score = models.IntegerField(choices=RATING_CHOICES, default=3)
    productivity_score = models.IntegerField(choices=RATING_CHOICES, default=3)
    teamwork_score = models.IntegerField(choices=RATING_CHOICES, default=3)
    communication_score = models.IntegerField(choices=RATING_CHOICES, default=3)
    initiative_score = models.IntegerField(choices=RATING_CHOICES, default=3)

    comments = models.TextField(blank=True)
    goals = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.review_period}"

    @property
    def overall_score(self):
        scores = [self.quality_score, self.productivity_score, self.teamwork_score,
                  self.communication_score, self.initiative_score]
        return round(sum(scores) / len(scores), 2)


class Payroll(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('paid', 'Paid'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_records')
    month = models.IntegerField()
    year = models.IntegerField()
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['employee', 'month', 'year']

    def __str__(self):
        return f"{self.employee.full_name} - {self.month}/{self.year}"