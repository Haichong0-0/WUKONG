from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from tickets.models import Department, Ticket, TicketActivity, User
from ..ai_service import ai_process_ticket



class RespondTicketViewTestCase(TestCase):
    fixtures = ['tickets/tests/fixtures/default_user.json']

    def setUp(self):
        self.department = Department.objects.create(name='it_support', description='IT Support')

        self.program_officer = User.objects.create_user(
            username='@programofficer', password='Password123', role='program_officers',
            email='111@qq.com', first_name='Program', last_name='Officer'
        )
        self.program_officer.department = self.department
        self.program_officer.save()

        self.student = User.objects.create_user(
            username='@student', password='Password123', role='students',
            email='222@qq.com', first_name='Student', last_name='Student'
        )
        self.student.department = self.department
        self.student.save()

        self.specialist = User.objects.create_user(
            username='@specialist', password='Password123', role='specialists',
            email='333@qq.com', first_name='Specialist', last_name='One'
        )
        self.specialist.department = self.department
        self.specialist.save()

        self.ticket = Ticket.objects.create(
            creator=self.student,
            title="Test Ticket",
            description="This is a test ticket.",
            assigned_department=self.department.name,
            assigned_user=self.specialist
        )
        ai_process_ticket(self.ticket)

        self.url = reverse('respond_ticket_page', kwargs={'ticket_id': self.ticket.id})

    def test_respond_ticket_for_specialist(self):
        """Test the respond ticket functionality for specialists."""
        self.client.login(username='@specialist', password='Password123')

        response_message = "This is a test response."
        response = self.client.post(self.url, {'response_message': response_message})

        self.ticket.refresh_from_db()
        self.assertNotEqual(response.status_code, 302)


    def test_respond_ticket_for_program_officer(self):
        """Test the respond ticket functionality for program officers."""
        self.client.login(username='@programofficer', password='Password123')

        response_message = "This is a program officer's response."
        response = self.client.post(self.url, {'response_message': response_message})

        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 200) 


    def test_respond_ticket_for_unauthorized_user(self):
        """Test if unauthorized user can't respond to the ticket."""
        self.client.login(username='@student', password='Password123')

        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200) 

