from unittest.mock import patch, ANY, MagicMock
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponse
from tickets.forms import ReturnTicketForm
from tickets.views.ticket_operations import get_specialists
from tickets.models import (
    DailyTicketClosureReport,
    Department,
    Ticket,
    TicketActivity,
    User,
    MergedTicket,
    AITicketProcessing,
)


class TicketViewTestCase(TestCase):
    fixtures = ["tickets/tests/fixtures/default_user.json"]

    def setUp(self):
        self.department = Department.objects.create(
            name="it_support", description="IT Support"
        )

        self.student = User.objects.create_user(
            username="@student",
            password="Password123",
            role="students",
            email="student@example.com",
            first_name="Student",
            last_name="One",
        )
        self.student.department = self.department
        self.student.save()

        self.specialist = User.objects.create_user(
            username="@specialist",
            password="Password123",
            role="specialists",
            email="specialist@example.com",
            first_name="Specialist",
            last_name="One",
        )
        self.specialist.department = self.department
        self.specialist.save()

        self.ticket = Ticket.objects.create(
            creator=self.student,
            title="Test Ticket",
            description="This is a test ticket.",
            assigned_department=self.department.name,
            assigned_user=self.specialist,
            status="in_progress",
        )

    def test_return_ticket_by_specialist(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse(
            "return_ticket",
            kwargs={
                "ticket_id": self.ticket.id,
            },
        )
        response = self.client.post(url, {"return_reason": "Need more details"})

        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.ticket.status, "in_progress")
        self.assertEqual(self.ticket.return_reason, "Need more details")
        self.assertFalse(self.ticket.can_be_managed_by_specialist)
        self.assertFalse(self.ticket.can_be_managed_by_program_officers)
        self.assertTrue(self.ticket.need_student_update)

        activity = TicketActivity.objects.filter(
            ticket=self.ticket, action="returned"
        ).first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.action_by, self.specialist)
        self.assertEqual(
            activity.comment, f"Return to student : {self.student.full_name()}"
        )

    def test_close_ticket_by_student(self):
        self.client.login(username="@student", password="Password123")
        url = reverse("close_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url)

        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.ticket.status, "closed")
        self.assertFalse(self.ticket.can_be_managed_by_program_officers)
        self.assertFalse(self.ticket.can_be_managed_by_specialist)
        self.assertTrue(self.ticket.program_officer_resolved)
        self.assertTrue(self.ticket.specialist_resolved)

        activity = TicketActivity.objects.filter(
            ticket=self.ticket, action="closed_manually"
        ).first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.action_by, self.student)
        self.assertEqual(activity.comment, "Ticket closed manually by the student.")

        report = DailyTicketClosureReport.objects.filter(
            date=timezone.now().date(), department=self.department.name
        ).first()
        self.assertIsNotNone(report)
        self.assertGreaterEqual(report.closed_manually, 1)

    def test_close_ticket_by_specailist(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse("close_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url)
        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)

    def test_by_specialist(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse("return_ticket", kwargs={"ticket_id": self.ticket.id})
        self.ticket.status = "closed"
        self.ticket.save()
        response = self.client.post(url)
        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)

    def test_close_ticket_by_student_without_form(self):
        self.client.login(username="@student", password="Password123")
        url = reverse("close_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url)
        self.ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)

    @patch(
        "tickets.models.DailyTicketClosureReport.objects.get_or_create",
        side_effect=Exception("Database error"),
    )
    def test_close_ticket_report_creation_failure(self, mock_get_or_create):
        self.client.login(username="@student", password="Password123")
        url = reverse("close_ticket", kwargs={"ticket_id": self.ticket.id})

        # with self.assertRaises(Exception) as context:
        response = self.client.post(url, {"return_reason": "System error test"})
        self.assertEqual(response.status_code, 302)


class RedirectTicketViewTestCase(TestCase):
    fixtures = ["tickets/tests/fixtures/default_user.json"]

    def setUp(self):
        self.department = Department.objects.create(
            name="it_support", description="IT Support"
        )

        self.student = User.objects.create_user(
            username="@student",
            password="Password123",
            role="students",
            email="student@example.com",
            first_name="Student",
            last_name="One",
        )
        self.student.department = self.department
        self.student.save()

        self.specialist = User.objects.create_user(
            username="@specialist",
            password="Password123",
            role="specialists",
            email="specialist@example.com",
            first_name="Specialist",
            last_name="One",
        )
        self.specialist.department = self.department
        self.specialist.save()

        self.officer = User.objects.create_user(
            username="@officer",
            password="Password123",
            role="program_officers",
            email="officer@example.com",
            first_name="Officer",
            last_name="One",
        )
        self.officer.department = self.department

        self.officer.save()
        self.ticket = Ticket.objects.create(
            creator=self.student,
            title="Test Ticket",
            description="This is a test ticket.",
            assigned_department="it_support",
            assigned_user=self.specialist,
            status="in_progress",
        )
        self.ticket.save()
        self.potential_ticket = Ticket.objects.create(
            creator=self.student,
            title="Potential Ticket",
            description="Test description for potential ticket",
            assigned_user=self.specialist,
            status="in_progress",
        )
        self.potential_ticket.save()

    def test_redirect_ticket_unauthenticated(self):
        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url, {"new_assignee_id": "ai"})
        self.assertEqual(response.status_code, 302)

    def test_redirect_ticket_unauthorized(self):
        self.client.login(username="@student", password="Password123")
        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url, {"new_assignee_id": "ai"})
        self.assertEqual(response.status_code, 403)

    def test_redirect_ticket_ai_assignment(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})

        response = self.client.post(url, {"new_assignee_id": "ai"})
        self.ticket.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ticket.status, "in_progress")
        self.assertEqual(self.ticket.latest_action, "redirected")

    def test_redirect_ticket_assign_specialist(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})

        response = self.client.post(url, {"new_assignee_id": self.specialist.id})
        self.ticket.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ticket.assigned_user, self.specialist)
        self.assertEqual(self.ticket.status, "in_progress")
        self.assertEqual(self.ticket.latest_action, "redirected")

    def test_redirect_ticket_invalid_specialist(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})

        response = self.client.post(url, {"new_assignee_id": 9999})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Selected specialist does not exist")

    def test_redirect_ticket_missing_assignee(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})

        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Selected specialist does not exist")

    def test_redirect_ticket_get_specialists(self):

        self.client.login(username="@officer", password="Password123")

        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("specialists", data)
        self.assertIsInstance(data["specialists"], list)
        self.assertGreater(len(data["specialists"]), 0)

    def test_redirect_ticket_classify_department_exception(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})

        with patch(
            "tickets.ai_service.classify_department",
            side_effect=Exception("Simulated AI failure"),
        ):
            response = self.client.post(url, {"new_assignee_id": "ai"})

        self.ticket.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.ticket.assigned_department, "general_enquiry"
        )  # fallback to existing department
        self.assertEqual(self.ticket.status, "in_progress")
        self.assertEqual(self.ticket.latest_action, "redirected")

        activity = TicketActivity.objects.filter(
            ticket=self.ticket, action="redirected"
        ).first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.action_by, self.officer)

    def test_get_specialists_classify_department_fallback(self):
        with patch(
            "tickets.views.ticket_operations.classify_department",
            side_effect=Exception("Simulated error"),
        ):
            self.ticket.assigned_department = "general_enquiry"
            self.ticket.save()
            specialists = get_specialists(self.ticket)
            self.assertEqual(specialists[0]["department_name"], "general_enquiry")

    @patch(
        "tickets.views.ticket_operations.classify_department", return_value="it_support"
    )
    def test_get_specialists_recommend_username_modified(self, mock_classify):
        self.ticket.assigned_department = "it_support"
        self.ticket.save()

        specialists = get_specialists(self.ticket)

        self.assertTrue(any("(recommend)" in spec["username"] for spec in specialists))
        self.assertTrue(
            any(spec["department_name"] == "it_support" for spec in specialists)
        )

    @patch("tickets.models.Ticket.save", autospec=True)
    @patch(
        "tickets.ai_service.classify_department",
        side_effect=Exception("Simulated AI failure"),
    )
    def test_redirect_ticket_classify_department_exception_fallback(
        self, mock_classify, mock_save
    ):
        self.client.login(username="@officer", password="Password123")
        self.ticket.assigned_department = ""
        self.ticket.save()

        url = reverse("redirect_ticket", kwargs={"ticket_id": self.ticket.id})

        response = self.client.post(url, {"new_assignee_id": "ai"})

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_department, "it_support")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(mock_save.call_count, 2)

    def test_return_ticket_get_request(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse("return_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/ticket_detail.html")
        self.assertIn("form", response.context)
        self.assertIn("ticket", response.context)

    def test_return_ticket_invalid_post(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse("return_ticket", kwargs={"ticket_id": self.ticket.id})

        response = self.client.post(url, {"return_reason": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/ticket_detail.html")
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)

    def test_respond_ticket(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("respond_ticket", kwargs={"ticket_id": self.ticket.id})
        response_message = "Test response"
        response = self.client.post(url, {"response_message": response_message})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "in_progress")
        activity = TicketActivity.objects.filter(
            ticket=self.ticket, action="responded"
        ).first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.comment, response_message)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/ticket_detail.html")

    def test_respond_ticket_permission_denied(self):
        random_user = User.objects.create_user(
            username="@intruder",
            password="Password123",
            role="students",
            email="intruder@example.com",
        )
        self.client.login(username="@intruder", password="Password123")

        url = reverse("respond_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url, {"response_message": "Hacked!"})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard"), response.url)

    def test_respond_ticket_with_merged_tickets(self):
        self.client.login(username="@officer", password="Password123")

        merged_ticket_1 = Ticket.objects.create(
            creator=self.student,
            title="Merged Ticket 1",
            description="Another ticket",
            assigned_department=self.department.name,
            status="in_progress",
        )

        merged = MergedTicket.objects.create(primary_ticket=self.ticket)
        merged.approved_merged_tickets.add(merged_ticket_1)

        url = reverse("respond_ticket", kwargs={"ticket_id": self.ticket.id})
        response_message = "Responding with merge"
        response = self.client.post(url, {"response_message": response_message})

        merged_ticket_1.refresh_from_db()
        self.ticket.refresh_from_db()

        self.assertIn(response_message, merged_ticket_1.answers)
        self.assertEqual(merged_ticket_1.status, "in_progress")

        activity = TicketActivity.objects.filter(
            ticket=merged_ticket_1, action="responded"
        ).first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.comment, response_message)

        self.assertIn(response_message, self.ticket.answers)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/ticket_detail.html")

    @patch("tickets.views.ticket_operations.classify_department")
    def test_redirect_ticket_fallback_on_classification_error(self, mock_classify):
        mock_classify.side_effect = Exception("AI error")
        self.client.login(username="@officer", password="Password123")

        response = self.client.post(
            reverse("redirect_ticket", args=[self.ticket.id]),
            {"new_assignee_id": self.officer.id},
            follow=True,
        )

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_department, "it_support")

        self.assertEqual(response.status_code, 200)
        self.assertIn("success", response.json() or {})


class TicketManageViewTestCase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="it_support", description="IT Support"
        )
        self.student = User.objects.create_user(
            username="@student",
            password="Password123",
            role="students",
            email="student@example.com",
            first_name="Student",
            last_name="One",
        )
        self.student.department = self.department
        self.student.save()
        self.specialist = User.objects.create_user(
            username="@specialist",
            password="Password123",
            role="specialists",
            email="specialist@example.com",
            first_name="Specialist",
            last_name="One",
        )
        self.specialist.department = self.department
        self.specialist.save()
        self.officer = User.objects.create_user(
            username="@officer",
            password="Password123",
            role="program_officers",
            email="officer@example.com",
            first_name="Officer",
            last_name="One",
        )
        self.officer.department = self.department
        self.officer.save()
        self.ticket = Ticket.objects.create(
            creator=self.student,
            title="Test Ticket",
            description="This is a test ticket.",
            assigned_department=self.department.name,
            assigned_user=self.specialist,
            status="in_progress",
        )
        self.ticket.save()
        self.potential_ticket = Ticket.objects.create(
            creator=self.student,
            title="Potential Ticket",
            description="Test description for potential ticket",
            assigned_user=self.specialist,
            status="in_progress",
        )
        self.potential_ticket.save()

    def test_update_ticket_success(self):
        self.client.login(username="@student", password="Password123")
        url = reverse("update_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url, {"update_message": "New update information"})
        self.ticket.refresh_from_db()
        self.assertIn("New update information", self.ticket.description)
        self.assertEqual(self.ticket.status, "in_progress")
        activity = TicketActivity.objects.filter(ticket=self.ticket).first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.action, "status_updated")
        self.assertEqual(activity.comment, "New update information")
        self.assertRedirects(
            response, reverse("ticket_detail", kwargs={"ticket_id": self.ticket.id})
        )

    def test_update_ticket_permission_denied(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse("update_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url, {"update_message": "Unauthorized update"})
        self.ticket.refresh_from_db()
        self.assertNotIn("Unauthorized update", self.ticket.description)
        self.assertEqual(response.status_code, 302)

    def test_update_ticket_by_program_officer_sets_program_resolved(self):
        self.ticket.creator = self.officer
        self.ticket.save()

        self.client.login(username="@officer", password="Password123")
        url = reverse("update_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url, {"update_message": "Officer update"})

        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.program_officer_resolved)
        self.assertEqual(response.status_code, 302)

    def test_update_ticket_by_specialist_sets_specialist_resolved(self):
        self.ticket.creator = self.specialist

        self.assigned_user = self.specialist
        self.ticket.save()

        self.client.login(username="@specialist", password="Password123")
        url = reverse("update_ticket", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url, {"update_message": "Specialist update"})

        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.specialist_resolved)
        self.assertEqual(response.status_code, 302)

    def test_manage_ticket_page_student(self):
        self.client.login(username="@student", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "tickets/manage_tickets_page_for_student.html"
        )
        self.assertIn("update_ticket", response.context["actions"])

    def test_manage_ticket_page_specialist(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "tickets/manage_tickets_page_for_specialist.html"
        )
        self.assertIn("respond_ticket", response.context["actions"])

    def test_manage_ticket_page_specialist_respond_ticket(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        with patch(
            "tickets.views.ticket_operations.respond_ticket",
            return_value=HttpResponse("respond ticket"),
        ) as mock_respond:
            response = self.client.post(
                url, {"action_type": "respond_ticket", "response_message": "response"}
            )
            self.assertEqual(response.content, b"respond ticket")
            mock_respond.assert_called_once_with(ANY, self.ticket.id)

    def test_manage_ticket_page_specialist_return_ticket(self):
        self.client.login(username="@specialist", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        with patch(
            "tickets.views.ticket_operations.return_ticket",
            return_value=HttpResponse("return ticket"),
        ) as mock_return:
            response = self.client.post(
                url, {"action_type": "return_to_student", "return_reason": "More info"}
            )
            self.assertEqual(response.content, b"return ticket")
            mock_return.assert_called_once_with(ANY, ticket_id=self.ticket.id)

    def test_manage_ticket_page_student_update_ticket(self):
        self.client.login(username="@student", password="Password123")
        self.ticket.assigned_user = self.student
        self.ticket.save()
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(
            url, {"action_type": "update_ticket", "update_message": "Update via manage"}
        )
        self.ticket.refresh_from_db()
        self.assertIn("Update via manage", self.ticket.description)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse("ticket_detail", kwargs={"ticket_id": self.ticket.id})
        )

    def test_manage_ticket_page_student_close_ticket(self):
        self.client.login(username="@student", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        response = self.client.post(url, {"action_type": "close_ticket"})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "closed")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_manage_ticket_page_program_officer_get(self):
        self.client.login(username="@officer", password="Password123")
        self.ticket.assigned_user = self.officer
        self.ticket.save()
        AITicketProcessing.objects.create(
            ticket=self.ticket, ai_assigned_department=self.department.name
        )

        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "tickets/manage_tickets_page_for_program_officer.html"
        )
        self.assertIn("ticket", response.context)
        self.assertIn("activities", response.context)
        self.assertIn("potential_tickets", response.context)
        self.assertIn("approved_merged_tickets", response.context)

    def test_manage_ticket_page_program_officer_respond_ticket(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        with patch(
            "tickets.views.ticket_operations.respond_ticket",
            return_value=HttpResponse("respond ticket"),
        ) as mock_respond:
            response = self.client.post(
                url,
                {"action_type": "respond_ticket", "response_message": "dummy response"},
            )
            self.assertEqual(response.content, b"respond ticket")
            mock_respond.assert_called_once_with(ANY, self.ticket.id)

    def test_manage_ticket_page_program_officer_merge_ticket(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        with patch(
            "tickets.views.ticket_operations.merge_ticket",
            return_value=HttpResponse("merge ticket"),
        ) as mock_merge:
            response = self.client.post(
                url,
                {
                    "action_type": "merge_ticket",
                    "potential_ticket_id": str(self.potential_ticket.id),
                },
            )
            self.assertEqual(response.content, b"merge ticket")
            mock_merge.assert_called_once_with(
                ANY,
                ticket_id=self.ticket.id,
                potential_ticket_id=str(self.potential_ticket.id),
            )

    def test_manage_ticket_page_program_officer_with_merged_ticket(self):
        self.client.login(username="@officer", password="Password123")

        AITicketProcessing.objects.create(
            ticket=self.ticket, ai_assigned_department=self.department.name
        )

        merged = MergedTicket.objects.create(primary_ticket=self.ticket)
        merged.approved_merged_tickets.add(self.potential_ticket)

        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "tickets/manage_tickets_page_for_program_officer.html"
        )
        self.assertIn(
            self.potential_ticket, response.context["approved_merged_tickets"]
        )

    def test_manage_ticket_page_program_officer_return_to_student(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        with patch(
            "tickets.views.ticket_operations.return_ticket",
            return_value=HttpResponse("return ticket"),
        ) as mock_return:
            response = self.client.post(url, {"action_type": "return_to_student"})
            self.assertEqual(response.content, b"return ticket")
            mock_return.assert_called_once_with(ANY, ticket_id=self.ticket.id)

    def test_manage_ticket_page_program_officer_redirect_ticket(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id})
        with patch(
            "tickets.views.ticket_operations.redirect_ticket",
            return_value=HttpResponse("redirect ticket"),
        ) as mock_redirect:
            response = self.client.post(url, {"action_type": "redirect_ticket"})
            self.assertEqual(response.content, b"redirect ticket")
            mock_redirect.assert_called_once_with(ANY, ticket_id=self.ticket.id)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_update_ticket_triggers_notification(self):
        self.client.login(username="@student", password="Password123")

        self.ticket.creator = self.student
        self.ticket.assigned_user = self.officer
        self.ticket.latest_editor = self.officer
        self.ticket.save()

        response = self.client.post(
            reverse("manage_ticket_page", kwargs={"ticket_id": self.ticket.id}),
            {
                "action_type": "update_ticket",
                "update_message": "Student updated the ticket",
            },
        )

        self.ticket.refresh_from_db()
        self.assertIn("Student updated the ticket", self.ticket.description)
        self.assertEqual(response.status_code, 302)

        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.officer.email, mail.outbox[0].to)
        self.assertIn("updated by student", mail.outbox[0].subject.lower())


class MergeTicketViewTestCase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="it_support", description="IT Support"
        )
        self.officer = User.objects.create_user(
            username="@officer",
            password="Password123",
            role="program_officers",
            email="officer@example.com",
        )
        self.officer.department = self.department
        self.officer.save()

        self.student = User.objects.create_user(
            username="@student",
            password="Password123",
            role="students",
            email="student@example.com",
            first_name="Student",
            last_name="One",
        )
        self.student.department = self.department
        self.student.save()

        self.ticket = Ticket.objects.create(
            creator=self.student,
            title="Primary Ticket",
            description="Primary ticket description",
            assigned_department=self.department.name,
            status="in_progress",
        )
        self.potential_ticket = Ticket.objects.create(
            creator=self.student,
            title="Potential Ticket",
            description="Potential ticket description",
            assigned_department=self.department.name,
            status="in_progress",
        )

        self.find_patch = patch(
            "tickets.ai_service.find_potential_tickets_to_merge", return_value=[]
        )
        self.mock_find = self.find_patch.start()

        AITicketProcessing.objects.create(
            ticket=self.ticket, ai_assigned_department=self.department.name
        )
        AITicketProcessing.objects.create(
            ticket=self.potential_ticket, ai_assigned_department=self.department.name
        )

    def tearDown(self):
        self.find_patch.stop()

    def test_merge_ticket_merge(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse(
            "merge_ticket",
            kwargs={
                "ticket_id": self.ticket.id,
                "potential_ticket_id": self.potential_ticket.id,
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "tickets/manage_tickets_page_for_program_officer.html"
        )
        merged_ticket = MergedTicket.objects.get(primary_ticket=self.ticket)
        self.assertIn(
            self.potential_ticket, merged_ticket.approved_merged_tickets.all()
        )
        self.assertContains(response, "Success! There are currently 1 tickets merged")

    def test_merge_ticket_unmerge(self):
        merged_ticket = MergedTicket.objects.create(primary_ticket=self.ticket)
        merged_ticket.approved_merged_tickets.add(self.potential_ticket)
        self.client.login(username="@officer", password="Password123")
        url = reverse(
            "merge_ticket",
            kwargs={
                "ticket_id": self.ticket.id,
                "potential_ticket_id": self.potential_ticket.id,
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "tickets/manage_tickets_page_for_program_officer.html"
        )
        merged_ticket.refresh_from_db()
        self.assertNotIn(
            self.potential_ticket, merged_ticket.approved_merged_tickets.all()
        )
        self.assertContains(response, "Tickets unmerged successfully.")

    def test_merge_ticket_get_not_allowed(self):
        self.client.login(username="@officer", password="Password123")
        url = reverse(
            "merge_ticket",
            kwargs={
                "ticket_id": self.ticket.id,
                "potential_ticket_id": self.potential_ticket.id,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_merge_ticket_unauthenticated(self):
        url = reverse(
            "merge_ticket",
            kwargs={
                "ticket_id": self.ticket.id,
                "potential_ticket_id": self.potential_ticket.id,
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/log_in/", response.url)

    def test_merge_ticket_real_logic(self):
        self.client.login(username="@officer", password="Password123")

        url = reverse(
            "merge_ticket",
            kwargs={
                "ticket_id": self.ticket.id,
                "potential_ticket_id": self.potential_ticket.id,
            },
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "tickets/manage_tickets_page_for_program_officer.html"
        )

        merged_ticket = MergedTicket.objects.get(primary_ticket=self.ticket)
        self.assertIn(
            self.potential_ticket, merged_ticket.approved_merged_tickets.all()
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        merged_ticket.refresh_from_db()
        self.assertNotIn(
            self.potential_ticket, merged_ticket.approved_merged_tickets.all()
        )
