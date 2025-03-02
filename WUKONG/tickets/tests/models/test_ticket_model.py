"""Unit tests for the Ticket model."""
from django.core.exceptions import ValidationError
from django.test import TestCase
from tickets.models import Ticket, User, Department

class TicketModelTest(TestCase):
    def setUp(self):
        self.departmentS = Department.objects.create(
            name="welfare",
            description="txt",
            responsible_roles="specialist"
        )
        self.department = Department.objects.create(
            name="admissions",
            description="txt",
            responsible_roles="program_officers"
        )
        self.user1 = User.objects.create_user(
            username="@testuser",
            first_name="Test",
            last_name="User",
            email="testuser@example.com",
            role="specialists",
            department=self.departmentS
        )
        self.user2 = User.objects.create_user(
            username="@testuser2",
            first_name="Test2",
            last_name="User",
            email="testuser2@example.com",
            role="program_officers",
            department=self.department
        )
        self.ticket = Ticket.objects.create(
            title="Test Ticket",
            description="This is a test ticket",
            creator=self.user2,
            assigned_user=self.user1,
            assigned_department = "program_officers",
            latest_action="created",
            latest_editor = self.user2,
            status="open"
        )
        self.ticket.save()
        return super().setUp()

    def test_ticket_creation(self):
        self.assertEqual(self.ticket.title, "Test Ticket")
        self.assertEqual(self.ticket.description, "This is a test ticket")
        self.assertEqual(self.ticket.creator, self.user2)
        self.assertEqual(self.ticket.assigned_user, self.user1)
        self.assertEqual(self.ticket.status, "open")

    def test_ticket_str(self):
        self.assertEqual(str(self.ticket), f"Ticket {self.ticket.id}: {self.ticket.title} ({self.ticket.status})")
    
    def test_ticket_change(self):
        self.ticket.status = "closed"
        self.ticket.save()
        self.assertEqual(self.ticket.status, "closed")

    def test_ticket_invalid_status(self):
        with self.assertRaises(ValidationError):
            self.ticket.status = "invalid_status"
            self.ticket.full_clean()

    def test_ticket_without_title(self):
        with self.assertRaises(ValidationError):
            self.ticket.title = ""
            self.ticket.full_clean()

    def test_ticket_without_description(self):
        with self.assertRaises(ValidationError):
            self.ticket.description = ""
            self.ticket.full_clean()