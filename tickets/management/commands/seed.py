import random
import time
import re
import os

import pytz
from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand, CommandError
from faker import Faker
from tickets.models import Department, Ticket, User, AITicketProcessing
from tickets.ai_service import generate_ai_answer, classify_department, query_bedrock
import boto3
from botocore.exceptions import ClientError
import json

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

# Predefined users 
USER_FIXTURES = [
    {'username': '@johndoe', 'email': 'john.doe@wukong.ac.uk', 'first_name': 'John', 'last_name': 'Doe', 'role': 'students'},
    {'username': '@janedoe', 'email': 'jane.doe@wukong.ac.uk', 'first_name': 'Jane', 'last_name': 'Doe', 'role': 'specialists'},
    {'username': '@charlie', 'email': 'charlie.johnson@wukong.ac.uk', 'first_name': 'Charlie', 'last_name': 'Johnson', 'role': 'program_officers'},
]

# Departments for seeding
DEPARTMENTS = [
            {'name': 'general_enquiry', 'description': 'General queries managed by program officers.', 'responsible_roles': 'program_officers'},
            {'name': 'academic_support', 'description': 'Academic support provided by personal tutors.', 'responsible_roles': 'specialists'},
            {'name': 'health_services', 'description': 'Health-related issues handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'financial_aid', 'description': 'Financial aid inquiries managed by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'career_services', 'description': 'Career guidance provided by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'welfare', 'description': 'Welfare support provided by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'misconduct', 'description': 'Misconduct cases managed by personal tutors.', 'responsible_roles': 'specialists'},
            {'name': 'it_support', 'description': 'IT-related issues handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'housing', 'description': 'Housing queries handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'admissions', 'description': 'Admissions queries managed by program officers.', 'responsible_roles': 'specialists'},
            {'name': 'library_services', 'description': 'Library-related support by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'research_support', 'description': 'Research-related assistance by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'study_abroad', 'description': 'Study abroad support managed by personal tutors.', 'responsible_roles': 'specialists'},
            {'name': 'alumni_relations', 'description': 'Alumni relations managed by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'exam_office', 'description': 'Examination office queries handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'security', 'description': 'Campus security issues handled by specialists.', 'responsible_roles': 'specialists'},
            {'name': 'language_centre', 'description': 'Language centre support provided by specialists.', 'responsible_roles': 'specialists'},
]


class Command(BaseCommand):
    """Build automation command to seed the database."""
    TICKET_COUNT = 5
    USER_COUNT = 30
    DEFAULT_PASSWORD = 'pbkdf2_sha256$260000$4BNvFuAWoTT1XVU8D6hCay$KqDCG+bHl8TwYcvA60SGhOMluAheVOnF1PMz0wClilc='
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
        self.create_tickets()
    
    def seed_departments(self):
        """Create departments from the predefined list if they do not exist."""
        for department_data in DEPARTMENTS:
            department, created = Department.objects.get_or_create(name=department_data['name'], defaults=department_data)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Department '{department.name}' created."))
            else:
                self.stdout.write(self.style.WARNING(f"Department '{department.name}' already exists."))

    def create_users(self):
        """Creates both predefined and randomly generated users, ensuring balanced role distribution."""
        
        total_users_needed = self.USER_COUNT
        specialist_departments = list(Department.objects.filter(responsible_roles="specialists"))

        # Define target role distribution
        target_specialists = max(1, total_users_needed // 5)  # 20% specialists
        target_program_officers = max(1, total_users_needed // 10)  # 10% program officers
        target_students = total_users_needed - (target_specialists + target_program_officers)  # Remaining are students

        users = []

        # Add predefined users
        for data in USER_FIXTURES:
            users.append(self.prepare_user_data(data, data["role"], specialist_departments))

        # Assign at least one specialist to every department
        for dept in specialist_departments:
            if len(users) >= total_users_needed:
                break  # Stop if have enough users
            users.append(self.prepare_user_data(self.generate_random_user_data(), "specialists", [dept]))

        # Generate remaining users while ensuring balanced role distribution
        assigned_specialists = len([u for u in users if u.role == "specialists"])
        assigned_program_officers = len([u for u in users if u.role == "program_officers"])
        assigned_students = len([u for u in users if u.role == "students"])

        while len(users) + User.objects.count() < total_users_needed:
            user_data = self.generate_random_user_data()

            if assigned_specialists < target_specialists:
                role = "specialists"
                assigned_specialists += 1
            elif assigned_program_officers < target_program_officers:
                role = "program_officers"
                assigned_program_officers += 1
            else:
                role = "students"
                assigned_students += 1

            users.append(self.prepare_user_data(user_data, role, specialist_departments))

        # Bulk create users
        User.objects.bulk_create(users, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"Successfully created {len(users)} users."))

    def prepare_user_data(self, data, role=None, specialist_departments=None):
        """Assigns users to roles and departments proportionally."""
        department = None

        if role == 'specialists' and specialist_departments:
            department = min(specialist_departments, key=lambda d: User.objects.filter(department=d).count())
        elif role == 'program_officers':
            department = Department.objects.get(name="general_enquiry")

        return User(
            username=data['username'],
            email=data['email'],
            password=self.DEFAULT_PASSWORD,
            first_name=data['first_name'],
            last_name=data['last_name'],
            role=role,
            department=department
        )

    def generate_random_user_data(self):
        """Generates random user data."""
        first_name, last_name = self.faker.first_name(), self.faker.last_name()
        return {
            "username": f"@{first_name.lower()}{last_name.lower()}",
            "email": f"{first_name.lower()}.{last_name.lower()}@wukong.ac.uk",
            "first_name": first_name,
            "last_name": last_name
        }
        
    def create_tickets(self):
        """Generate meaningful tickets for students using AWS Bedrock."""
        students = list(User.objects.filter(role='students'))
        if not students:
            self.stdout.write(self.style.WARNING("No students found, skipping ticket creation."))
            return

        departments = list(Ticket.DEPARTMENT_CHOICES)
        new_tickets = []
        new_ai_tickets = []

        while len(new_tickets) < self.TICKET_COUNT:
            student = random.choice(students)
            department = random.choice(departments)[0]

            # Prompt for student query generation
            prompt = f"Create a meaningful/realistic university student query with a title and a description for the {department} department. 50 words max. Answer in a paragraph, do not involve quotation marks or words like: 1.Here is a university student query for the study_abroad department: 2.title/description, just keep the query itself. The first sentence should be the title of the query, the rest should be the description. Separate the title and description with a period."
            ai_generated_query = query_bedrock(prompt)

            if not ai_generated_query:
                continue

            match = re.match(r"^(.*?[.?!])\s*(.*)", ai_generated_query.strip())
            if match:
                title = match.group(1).strip()
                description = match.group(2).strip() or "Further details required."
            else:
                title = ai_generated_query.strip()
                description = "Further details required."
            
            ticket = Ticket(
                creator=student,
                title=title,
                description=description,
                status='open',
                priority=random.choice(['low', 'medium', 'high', 'urgent']),
            )
            new_tickets.append(ticket)
        
        created_tickets = Ticket.objects.bulk_create(new_tickets)
        self.stdout.write(self.style.SUCCESS(f"Successfully created {len(created_tickets)} tickets."))

        for ticket in created_tickets:
            ai_department = classify_department(ticket.description)
            ai_answer = generate_ai_answer(ticket.description)

            ai_ticket = AITicketProcessing.objects.create(
                ticket=ticket,
                ai_generated_response=ai_answer,
                ai_assigned_department=ai_department
            )
            new_ai_tickets.append(ai_ticket)
            self.stdout.write(self.style.SUCCESS(f"Ticket title: {ticket.title}"))
            self.stdout.write(self.style.SUCCESS(f"Description: {ticket.description}"))
            self.stdout.write(self.style.SUCCESS(f"   "))
            self.stdout.write(self.style.SUCCESS(f"AI Response: {ai_answer}"))
            self.stdout.write(self.style.SUCCESS(f"==============================================================================="))
            self.stdout.write(self.style.SUCCESS(f"==============================================================================="))
            self.stdout.write(self.style.SUCCESS(f"   "))
        self.stdout.write(self.style.SUCCESS(f"Successfully answered {len(new_ai_tickets)} tickets."))

def create_username(first_name, last_name):
    return '@' + first_name.lower() + last_name.lower()

def create_email(first_name, last_name):
    return first_name + '.' + last_name + '@wukong.ac.uk'

