"""Unit tests for the Ticket Attachemnt model."""
from django.core.exceptions import ValidationError
from django.test import TestCase
from tickets.models import Ticket, User,TicketAttachment

class TicketAttachmentModelTest(TestCase):
    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="Test Ticket",
            description="This is a test ticket",
            creator=User.objects.create_user(
                username="@testuser",
                first_name="Test",
                last_name="User",
                email="test@example.com"))
        self.ticket.save()
        self.attachment = TicketAttachment.objects.create(
            ticket=self.ticket,
            file="test.txt",
        )

    def test_ticket_attachment_creation(self):
        self.assertEqual(self.attachment.ticket, self.ticket)
        self.assertEqual(self.attachment.file, "test.txt")
    
    def test_ticket_attachment_str(self):
        self.assertEqual(str(self.attachment), f"Attachment {self.attachment.file} for Ticket {self.ticket.id}")