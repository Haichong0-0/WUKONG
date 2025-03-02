"""Test this script must run seed.py first to create users and departments or create them manually."""

import os
import django
import random
from django.core.mail import send_mail
from django.conf import settings
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Moves one level up
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Moves two levels up

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "query_hub.settings")  
django.setup()

from tickets.models import User

test_messages = [
    ("Course Registration Issue", "I need help enrolling in a course.", "academic_support"),
    ("Sick Leave Application", "I am sick and need a medical leave form.", "health_services"),
    ("Tuition Payment Delay", "My tuition payment is delayed. What should I do?", "financial_aid"),
    ("Internship Opportunity", "I am looking for career guidance on internships.", "career_services"),
    ("Counseling Needed", "I am feeling stressed and need welfare support.", "welfare"),
    ("WiFi Issue", "I can't connect to the university WiFi.", "it_support"),
    ("Dorm Problem", "My dorm room has maintenance issues.", "housing"),
    ("Admissions Help", "I need help with my application.", "admissions"),
    ("Library Book Overdue", "I forgot to return my library book.", "library_services"),
]

def test_sending_test_tickets():
    """Randomly selects 50 students and sends an email to the help desk."""
    
    # Get 50 random students
    students = list(User.objects.filter(role="students"))
    selected_students = random.sample(students, min(10, len(students)))

    for student in selected_students:
        selected_message = random.choice(test_messages)
        subject = selected_message[0]
        message = selected_message[1]
        expected_category = selected_message[2]

        full_message = f"""
        Hello Support Team,

        {message}

        Best regards,
        {student.first_name} {student.last_name}
        """
        try:
            send_mail(
                subject,
                full_message,
                student.email,  # Sender (From)
                [settings.EMAIL_HOST_USER],  # Receiver (To: Help Desk)
                fail_silently=False,
            )
            print(f"✅ Email sent from {student.email} with subject '{subject}' (Expected: {expected_category})")
        except Exception as e:
            print(f"❌ Failed to send email from {student.email}: {e}")

if __name__ == "__main__":
    test_sending_test_tickets()
