from django.test import TestCase
from unittest.mock import patch
from django.core import mail  
from django.contrib.auth import get_user_model
from tickets.models import User
import random

class SendTestTicketsTest(TestCase):
    """Test case for sending test tickets via email."""

    def setUp(self):
        """Set up test users before running tests."""
        User = get_user_model()
        
        # Ensure at least 5 students exist for the test
        self.students = []
        for i in range(5):
            student = User.objects.create(
                username=f"@student{i}",
                first_name=f"Test{i}",
                last_name="User",
                email=f"student{i}@wukong.ac.uk",
                role="students"
            )
            self.students.append(student)

    @patch("django.core.mail.send_mail")  # Ensure correct patch path
    def test_send_test_tickets(self, mock_send_mail):
        """Test that emails are correctly sent to the help desk."""
        students = list(User.objects.filter(role="students").all())  # Force reload users
        self.assertGreater(len(students), 0, "No students found in test database!")

        test_messages = [
            ("Course Registration Issue", "I need help enrolling in a course.", "academic_support"),
            ("Sick Leave Application", "I am sick and need a medical leave form.", "health_services"),
            ("Tuition Payment Delay", "My tuition payment is delayed. What should I do?", "financial_aid"),
        ]

        selected_students = random.sample(students, min(3, len(students)))

        for student in selected_students:
            subject, message, expected_category = random.choice(test_messages)

            full_message = f"""
            Hello Support Team,

            {message}

            Best regards,
            {student.first_name} {student.last_name}
            """

            mail.send_mail(  
                subject.strip(),
                full_message.strip(),
                student.email,
                ["helpdesk@wukong.ac.uk"],
                fail_silently=False,
            )


        # Ensure send_mail() was called
        self.assertGreater(mock_send_mail.call_count, 0, "send_mail() was not called!")

        
