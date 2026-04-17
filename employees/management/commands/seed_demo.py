"""
Management command to seed demo data for the EMS.
Run: python manage.py seed_demo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from employees.models import (Department, Employee, Attendance,
                                LeaveRequest, PerformanceReview, Payroll)
from datetime import date, timedelta, time
import random


class Command(BaseCommand):
    help = 'Seed demo data for EMS'

    def handle(self, *args, **options):
        self.stdout.write('🌱 Seeding demo data...')

        # Update site
        site = Site.objects.get_current()
        site.domain = 'localhost:8000'
        site.name = 'NexForce EMS'
        site.save()

        # Superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@nexforce.com', 'admin123')
            self.stdout.write('✅ Created admin / admin123')

        # Departments
        depts_data = [
            ('Engineering', 'ENG'),
            ('Product', 'PRD'),
            ('Design', 'DES'),
            ('Marketing', 'MKT'),
            ('HR', 'HR'),
            ('Finance', 'FIN'),
            ('Sales', 'SLS'),
            ('Operations', 'OPS'),
        ]
        depts = {}
        for name, code in depts_data:
            dept, _ = Department.objects.get_or_create(code=code, defaults={'name': name})
            depts[code] = dept

        # Employees
        employees_data = [
            ('Arjun', 'Sharma', 'Engineering', 'Senior Engineer', 120000, ['Python', 'Django', 'React', 'AWS']),
            ('Priya', 'Patel', 'Product', 'Product Manager', 130000, ['Roadmapping', 'Analytics', 'Figma']),
            ('Vikram', 'Singh', 'Design', 'Lead Designer', 100000, ['Figma', 'UI/UX', 'Prototyping']),
            ('Ananya', 'Reddy', 'Engineering', 'Backend Developer', 95000, ['Python', 'PostgreSQL', 'Redis']),
            ('Rahul', 'Gupta', 'Marketing', 'Marketing Manager', 85000, ['SEO', 'Content', 'Analytics']),
            ('Sneha', 'Joshi', 'HR', 'HR Manager', 80000, ['Recruitment', 'Compliance', 'Payroll']),
            ('Kiran', 'Nair', 'Finance', 'Finance Lead', 110000, ['Accounting', 'Tally', 'Excel']),
            ('Rohit', 'Verma', 'Sales', 'Sales Executive', 75000, ['CRM', 'Negotiation', 'Lead Generation']),
            ('Deepa', 'Kumar', 'Engineering', 'Frontend Developer', 90000, ['React', 'TypeScript', 'CSS']),
            ('Aditya', 'Mishra', 'Operations', 'Ops Manager', 95000, ['Logistics', 'Process Improvement']),
            ('Meera', 'Iyer', 'Design', 'UX Researcher', 85000, ['User Research', 'Figma', 'A/B Testing']),
            ('Suresh', 'Pillai', 'Engineering', 'DevOps Engineer', 115000, ['Kubernetes', 'Docker', 'CI/CD', 'AWS']),
        ]

        created_employees = []
        for i, (first, last, dept_name, designation, salary, skills) in enumerate(employees_data):
            emp_id = f'NX{str(i+1).zfill(4)}'
            dept_code = {
                'Engineering': 'ENG', 'Product': 'PRD', 'Design': 'DES',
                'Marketing': 'MKT', 'HR': 'HR', 'Finance': 'FIN',
                'Sales': 'SLS', 'Operations': 'OPS'
            }.get(dept_name, 'ENG')

            emp, created = Employee.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f'{first.lower()}.{last.lower()}@nexforce.com',
                    'phone': f'+91 98{random.randint(10000000, 99999999)}',
                    'department': depts[dept_code],
                    'designation': designation,
                    'salary': salary,
                    'employment_status': random.choice(['active', 'active', 'active', 'on_leave']),
                    'employment_type': random.choice(['full_time', 'full_time', 'full_time', 'contract']),
                    'date_joined': date.today() - timedelta(days=random.randint(90, 1500)),
                    'skills': ', '.join(skills),
                    'performance_score': random.uniform(45, 95),
                    'risk_score': random.uniform(10, 70),
                }
            )
            if created:
                created_employees.append(emp)

        # Attendance — last 30 days
        all_employees = Employee.objects.filter(is_active=True)
        statuses = ['present', 'present', 'present', 'present', 'late', 'absent', 'work_from_home']

        for emp in all_employees:
            for days_back in range(30, 0, -1):
                att_date = date.today() - timedelta(days=days_back)
                if att_date.weekday() >= 5:
                    continue  # skip weekends

                status = random.choice(statuses)
                check_in = None
                check_out = None

                if status in ['present', 'late', 'work_from_home']:
                    hour = 9 if status == 'present' else random.randint(10, 12)
                    check_in = time(hour, random.randint(0, 59))
                    check_out = time(random.randint(17, 19), random.randint(0, 59))

                Attendance.objects.get_or_create(
                    employee=emp,
                    date=att_date,
                    defaults={
                        'status': status,
                        'check_in': check_in,
                        'check_out': check_out,
                        'is_anomaly': random.random() < 0.05,  # 5% anomaly rate
                    }
                )

        # Leave requests
        leave_types = ['annual', 'sick', 'emergency', 'paternity', 'unpaid']
        statuses_leave = ['pending', 'approved', 'rejected']
        for emp in list(all_employees)[:6]:
            LeaveRequest.objects.get_or_create(
                employee=emp,
                start_date=date.today() + timedelta(days=random.randint(2, 20)),
                defaults={
                    'end_date': date.today() + timedelta(days=random.randint(22, 28)),
                    'leave_type': random.choice(leave_types),
                    'reason': 'Personal reasons and family matters',
                    'status': random.choice(statuses_leave),
                }
            )

        # Performance reviews
        periods = ['Q1 2024', 'Q2 2024', 'Q3 2024', 'Q4 2023']
        admin_user = User.objects.get(username='admin')
        for emp in all_employees:
            for period in random.sample(periods, 2):
                PerformanceReview.objects.get_or_create(
                    employee=emp,
                    review_period=period,
                    defaults={
                        'reviewer': admin_user,
                        'review_date': date.today() - timedelta(days=random.randint(10, 200)),
                        'quality_score': random.randint(3, 5),
                        'productivity_score': random.randint(2, 5),
                        'teamwork_score': random.randint(3, 5),
                        'communication_score': random.randint(2, 5),
                        'initiative_score': random.randint(2, 5),
                        'comments': 'Strong performance with good teamwork skills.',
                    }
                )

        self.stdout.write(self.style.SUCCESS(
            f'✅ Demo seeding complete!\n'
            f'   Departments: {Department.objects.count()}\n'
            f'   Employees: {Employee.objects.count()}\n'
            f'   Attendance records: {Attendance.objects.count()}\n'
            f'   Leave requests: {LeaveRequest.objects.count()}\n'
            f'   Performance reviews: {PerformanceReview.objects.count()}\n\n'
            f'   🔑 Admin login: admin / admin123\n'
            f'   🌐 Run: python manage.py runserver\n'
            f'   🌍 Visit: http://localhost:8000'
        ))