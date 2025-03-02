from django.core.exceptions import ValidationError
from django.test import TestCase
from tickets.models import Ticket, User,TicketActivity


class TicketActivityModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="@testuser",
            first_name="Test",
            last_name="User",
            email="test@example.org")
        self.ticket = Ticket.objects.create(
            title="Test Ticket",
            description="This is a test ticket",
            creator=self.user)
        self.ticket.save()
        self.activity = TicketActivity.objects.create(
            ticket=self.ticket,
            action_by=self.user,
            action="created",
            comment="Test activity")
    
    def test_ticket_activity_creation(self):
        self.assertEqual(self.activity.ticket, self.ticket)
        self.assertEqual(self.activity.action_by, self.user)
        self.assertEqual(self.activity.action, "created")
        self.assertEqual(self.activity.comment, "Test activity")
    
    def test_ticket_activity_str(self):
        self.assertEqual(str(self.activity), f"Activity for Ticket {self.activity.ticket.id} by {self.activity.action_by.username} on {self.activity.action_time}")