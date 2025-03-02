from django.core.management.base import BaseCommand, CommandError
from tickets.models import User, Department, Ticket
import pytz
from faker import Faker
import random
from django.core.mail import get_connection, send_mail
from django.conf import settings
import time

user_fixtures = [
    {'username': '@johndoe', 'email': 'john.doe@example.org', 'first_name': 'John', 'last_name': 'Doe', 'role': 'students'},
    {'username': '@janedoe', 'email': 'jane.doe@example.org', 'first_name': 'Jane', 'last_name': 'Doe', 'role': 'specialists'},
    {'username': '@charlie', 'email': 'charlie.johnson@example.org', 'first_name': 'Charlie', 'last_name': 'Johnson', 'role': 'program_officers'},
]


class Command(BaseCommand):
    """Build automation command to seed the database."""

    USER_COUNT = 300
    DEFAULT_PASSWORD = 'Password123'
    help = 'Seeds the database with sample data'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.faker = Faker('en_GB')

    def handle(self, *args, **options):
        # Seed Departments
        self.seed_departments()

        # Seed Users
        self.create_users()
    
        # Seed Tickets
        self.create_sample_tickets()
        
    def send_bulk_emails(self, users):
        connection = get_connection()

        # choose 50 random students
        students = list(User.objects.filter(role='students'))
        selected_students = random.sample(students, min(50, len(students)))
        for user in selected_students:
            try:
                self.send_welcome_email(user, connection)
                time.sleep(2)  
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error sending email to {user.email}: {e}"))

        connection.close()
        
    def seed_departments(self):
        departments = [
            {'name': 'general_enquiry', 'description': 'General queries managed by program officers.', 'responsible_roles': 'program_officers'},
            {'name': 'academic_support', 'description': 'Academic support provided by personal tutors.', 'responsible_roles': 'specialists'},
            {'name': 'health_services', 'description': 'Health-related issues handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'financial_aid', 'description': 'Financial aid inquiries managed by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'career_services', 'description': 'Career guidance provided by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'welfare', 'description': 'Welfare support provided by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'misconduct', 'description': 'Misconduct cases managed by personal tutors.', 'responsible_roles': 'specialists'},
            {'name': 'it_support', 'description': 'IT-related issues handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'housing', 'description': 'Housing queries handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'admissions', 'description': 'Admissions queries managed by program officers.', 'responsible_roles': 'program_officers'},
            {'name': 'library_services', 'description': 'Library-related support by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'research_support', 'description': 'Research-related assistance by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'study_abroad', 'description': 'Study abroad support managed by personal tutors.', 'responsible_roles': 'specialists'},
            {'name': 'alumni_relations', 'description': 'Alumni relations managed by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'exam_office', 'description': 'Examination office queries handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'security', 'description': 'Campus security issues handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'language_centre', 'description': 'Language centre support provided by specialists.', 'responsible_roles': 'specialists'},
        ]

        for department_data in departments:
            department, created = Department.objects.get_or_create(name=department_data['name'], defaults=department_data)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Department '{department.name}' created."))
            else:
                self.stdout.write(self.style.WARNING(f"Department '{department.name}' already exists."))

    def create_users(self):
        connection = get_connection() # Use default email connection
        self.generate_user_fixtures(connection)
        self.generate_random_users(connection)
        
        # Send welcome emails to students
        users = User.objects.filter(role="students") 
        self.send_bulk_emails(users)

        connection.close()

    def generate_user_fixtures(self, connection = None):
        for data in user_fixtures:
            department = None
            if data['role'] == 'specialists':    
                specialist_departments = Department.objects.filter(responsible_roles__icontains='specialists')
                if specialist_departments.exists():
                    department = random.choice(specialist_departments)
            elif data['role'] == 'program_officers':
                    department = Department.objects.get(name="general_enquiry")
            self.try_create_user(data, department, connection)


    def generate_random_users(self, connection=None):
        user_count = User.objects.count()
        while  user_count < self.USER_COUNT:
            print(f"Seeding user {user_count}/{self.USER_COUNT}", end='\r')
            self.generate_user(connection)
            user_count = User.objects.count()
        print("User seeding complete.      ")

    def generate_user(self, connection=None):
        first_name = self.faker.first_name()
        last_name = self.faker.last_name()
        email = create_email(first_name, last_name)
        username = create_username(first_name, last_name)
        
         # Ensure unique email
        while User.objects.filter(email=email).exists():
            email = create_email(first_name, last_name)
            
        role = self.faker.random_element(['students', 'program_officers', 'specialists'])
        department = None
        # Only assign department to specialists
        if role == 'specialists':
            department = Department.objects.filter(responsible_roles__icontains='specialists')
            if department.exists():
                department = random.choice(department)

        self.try_create_user({'username': username, 'email': email, 'first_name': first_name, 'last_name': last_name, 'role': role}, department)
       
    def try_create_user(self, data, department=None, connection=None):
        try:
            if 'role' not in data:  # Default to 'others', this is for the admin, superuser.
                data['role'] = 'others'
            self.create_user(data, department, connection)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating user {data['username']}: {e}"))

    def send_welcome_email(self, user, connection=None):
        subject = f"Welcome, {user.first_name}!"
        message = f"""
        Hello {user.first_name},

        Your university account has been created successfully.

        Username: {user.username}
        Email: {user.email}
        Password: {Command.DEFAULT_PASSWORD} (Please change it after login)

        You can log in to the system and manage your tickets.

        Regards,
        WuKong Help Desk
        """
        try:
            send_mail(
                subject, 
                message, 
                settings.EMAIL_HOST_USER, 
                [user.email], 
                connection=connection  
            )
            self.stdout.write(self.style.SUCCESS(f"✅ Email sent to {user.email}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error sending email to {user.email}: {e}"))  # ✅ 记录详细错误

        
    def create_user(self, data, department=None, connection=None):
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=Command.DEFAULT_PASSWORD,
            first_name=data['first_name'],
            last_name=data['last_name'],
            role=data.get('role', 'others'), # Default to 'others'
        )
        if department:
            user.department = department
            user.save()
    
    def create_sample_tickets(self):
        """Generate random tickets for students"""
        students = User.objects.filter(role='students')
        if students.exists():
            for student in students[:20]:  # Create only for first 20 students
                Ticket.objects.create(
                    title=self.faker.sentence(),
                    description=self.faker.text(),
                    status=random.choice(['open', 'pending', 'closed']),
                    creator=student
                )
                self.stdout.write(self.style.SUCCESS(f"Sample ticket created for {student.username}"))

        
def create_username(first_name, last_name):
    return '@' + first_name.lower() + last_name.lower()

def create_email(first_name, last_name):
    return first_name + '.' + last_name + '@example.org'

