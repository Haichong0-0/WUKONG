from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib import messages
from tickets.models import Ticket, Department

User = get_user_model()


class TicketListViewTestCase(TestCase):
    fixtures = [
        "tickets/tests/fixtures/default_user.json",
        "tickets/tests/fixtures/other_users.json",
    ]

    def setUp(self):
        self.department = Department.objects.create(
            name="welfare",
            description="txt",
        )
        self.specialist = User.objects.get(username="@peterpickles")
        self.program_officer = User.objects.get(username="@janedoe")
        self.student = User.objects.get(username="@johndoe")
        self.student2 = User.objects.get(username="@petrapickles")
        self.ticket1 = Ticket.objects.create(
            title="Test Ticket 1",
            creator=self.student,
            status="in_progress",
            assigned_user=self.specialist,
            assigned_department=self.department.name,
        )
        self.ticket2 = Ticket.objects.create(
            title="Test Ticket 2",
            creator=self.student,
            status="in_progress",
            assigned_user=self.program_officer,
            assigned_department=self.department.name,
        )
        self.ticket3 = Ticket.objects.create(
            title="Test Ticket 3",
            creator=self.student2,
            status="in_progress",
            assigned_user=self.specialist,
            assigned_department=self.department.name,
        )
        self.url = reverse("ticket_list")

    def test_redirect_if_student(self):
        self.client.login(username="@johndoe", password="Password123")
        response = self.client.get(self.url, follow=True)
        self.assertRedirects(response, reverse("dashboard_student"))
        messages_list = list(response.context["messages"])
        self.assertEqual(len(messages_list), 1)
        self.assertEqual(messages_list[0].level, messages.ERROR)
        self.assertEqual(
            messages_list[0].message,
            "You do not have permission to view the ticket list.",
        )

    def test_ticket_list_view_as_program_officer(self):
        self.client.login(username="@janedoe", password="Password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/ticket_list.html")
        self.assertContains(response, self.ticket1.title)
        self.assertContains(response, self.ticket2.title)

    def test_ticket_list_view_as_specialist(self):
        specialist = User.objects.get(username="@peterpickles")

        self.ticket1.latest_editor = specialist
        self.ticket1.save()

        self.ticket2.latest_editor = None
        self.ticket2.save()

        self.ticket3.latest_editor = specialist
        self.ticket3.save()

        self.client.login(username="@peterpickles", password="Password123")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/ticket_list.html")

        self.assertContains(response, self.ticket1.title)
        self.assertContains(response, self.ticket3.title)

        self.assertNotContains(response, self.ticket2.title)
