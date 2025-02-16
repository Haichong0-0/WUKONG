from django.db.models import Count
from django.test import TestCase
from django.urls import reverse
from tickets.models import Department, Ticket, TicketActivity, User

# add merge request

class DashboardViewTestCase(TestCase):
    """Tests for the dashboard view."""

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

        self.url = reverse('dashboard')

    def test_dashboard_for_student(self):
        self.client.login(username='@student', password='Password123')
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertIn('student_tickets', response.context)

    def test_dashboard_for_specialist(self):
        self.client.login(username='@specialist', password='Password123')
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertIn('assigned_tickets', response.context)

    def test_dashboard_for_unauthorized_user(self):
        user = User.objects.create_user(
            username='@unauthorized', password='Password123', role='others'
        )
        self.client.login(username='@unauthorized', password='Password123')
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertIn('message', response.context)
        self.assertEqual(response.context['message'], "You do not have permission to view this dashboard.")

    def test_redirect_ticket(self):
        self.client.login(username='@programofficer', password='Password123')

        response = self.client.post(self.url, {
            'redirect_ticket': True,
            'ticket_id': self.ticket.id,
            'new_assignee_id': self.specialist.id
        })

        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)  # Should redirect
        self.assertEqual(self.ticket.assigned_user, self.specialist)
        self.assertEqual(self.ticket.latest_action, 'redirected')

        ticket_activity = TicketActivity.objects.filter(ticket=self.ticket, action='redirected').first()
        self.assertIsNotNone(ticket_activity)
        self.assertEqual(ticket_activity.action_by, self.program_officer)
        self.assertIn(f"Redirected to {self.specialist.username}", ticket_activity.comment)

    def test_respond_ticket(self):
        self.client.login(username='@specialist', password='Password123')

        response_message = "This is a test response."
        self.ticket.answers = "This is a previous answer."
        self.ticket.save()
        response = self.client.post(self.url, {
            'respond_ticket': True,
            'ticket_id': self.ticket.id,
            'response_message': response_message
        })

        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)  # Should redirect
        self.assertIn(f"Response by {self.specialist.username}: {response_message}", self.ticket.answers)

        ticket_activity = TicketActivity.objects.filter(ticket=self.ticket, action='responded').first()
        self.assertIsNotNone(ticket_activity)
        self.assertEqual(ticket_activity.action_by, self.specialist)
        self.assertEqual(ticket_activity.comment, response_message)

    def test_search_functionality_for_student(self):
        self.client.login(username='@student', password='Password123')

        search_query = 'Test'
        response = self.client.get(self.url, {'search': search_query})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        student_tickets = response.context.get('student_tickets')
        self.assertIsNotNone(student_tickets)
        self.assertTrue(all(search_query.lower() in ticket.title.lower() for ticket in student_tickets))

    def test_ticket_answers_none(self):
        """Test response when ticket.answers is None."""
        self.client.login(username='@specialist', password='Password123')

        response_message = "New response"
        response = self.client.post(self.url, {
            'respond_ticket': True,
            'ticket_id': self.ticket.id,
            'response_message': response_message,
        })

        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.ticket.answers, f"Response by @specialist: {response_message}")

    def test_ticket_search_for_program_officer(self):
        """Test search functionality for program officer."""
        self.client.login(username='@programofficer', password='Password123')
        response = self.client.get(f"{self.url}?search=Test")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Ticket")

    def test_ticket_search_for_student(self):
        """Test search functionality for student."""
        self.client.login(username='@student', password='Password123')
        response = self.client.get(f"{self.url}?search=Test")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Ticket")

    def test_ticket_search_for_specialist(self):
        """Test search functionality for specialist."""
        self.client.login(username='@specialist', password='Password123')
        response = self.client.get(f"{self.url}?search=Test")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Ticket")

    def test_redirect_ticket(self):
        """Test the redirect ticket action."""
        self.client.login(username='@programofficer', password='Password123')

        response = self.client.post(self.url, {
            'redirect_ticket': True,
            'ticket_id': self.ticket.id,
            'new_assignee_id': self.specialist.id,
        })

        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.ticket.assigned_user, self.specialist)
        self.assertEqual(self.ticket.latest_action, 'redirected')

    def test_render_dashboard_no_tickets(self):
        """Test rendering the dashboard with no tickets."""
        self.client.login(username='@programofficer', password='Password123')
        Ticket.objects.all().delete()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Test Ticket")