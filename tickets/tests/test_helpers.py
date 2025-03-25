from django.test import TestCase, override_settings, RequestFactory
from unittest.mock import patch
from django.core.mail import send_mail
from tickets.models import TicketAttachment, User, Ticket
from unittest.mock import MagicMock
from tickets.helpers import (
    filter_tickets,
    get_filtered_tickets,
    send_response_notification_email,
    send_updated_notification_email,
    handle_uploaded_file_in_chunks,
    send_updated_notification_email_to_specialist_or_program_officer,
)
from django.core.files.uploadedfile import SimpleUploadedFile


class EmailNotificationTests(TestCase):

    @patch("tickets.helpers.send_mail")
    @patch("tickets.helpers.render_to_string")
    def test_send_response_notification_email(self, mock_render, mock_send_mail):
        mock_render.return_value = "<p>Test HTML</p>"

        send_response_notification_email(
            "student@example.com", "Test Ticket", "This is a reply", 42
        )

        mock_render.assert_called_once_with(
            "emails/response_notification.html",
            {
                "student_name": "student",
                "ticket_title": "Test Ticket",
                "response_message": "This is a reply",
                "ticket_id": 42,
            },
        )

        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args
        self.assertEqual(args[0], "Update on Your Ticket: 'Test Ticket'")
        self.assertIn("student@example.com", args[3])

        self.assertIn("html_message", kwargs)

    @patch("tickets.helpers.send_mail")
    @patch("tickets.helpers.render_to_string")
    def test_send_updated_notification_email(self, mock_render, mock_send_mail):
        mock_render.return_value = "<p>Updated!</p>"

        send_updated_notification_email(
            "student@example.com", "Updated Ticket", "Something changed", 77
        )

        mock_render.assert_called_once_with(
            "emails/updated_notification.html",
            {
                "student_name": "student",
                "ticket_title": "Updated Ticket",
                "response_message": "Something changed",
                "ticket_id": 77,
            },
        )

        mock_send_mail.assert_called_once()

    @patch("tickets.helpers.send_mail")
    @patch("tickets.helpers.render_to_string")
    def test_send_updated_notification_email_to_specialist_or_program_officer(
        self, mock_render, mock_send_mail
    ):
        mock_render.return_value = "<p>Update Notice</p>"

        send_updated_notification_email_to_specialist_or_program_officer(
            "john.doe@university.edu",
            "Assignment Help Needed",
            "abc-123-ticket-id",
            "student@uni.edu",
            "Here is the updated info",
        )

        mock_render.assert_called_once_with(
            "emails/update_notice.html",
            {
                "name": "john.doe",
                "ticket_title": "Assignment Help Needed",
                "response_message": "Here is the updated info",
                "ticket_id": "abc-123-ticket-id",
            },
        )

        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args

        self.assertEqual(
            args[0],
            "Your assigned ticket is updated by student: 'Assignment Help Needed'",
        )
        self.assertIn("john.doe@university.edu", args[3])
        self.assertEqual(kwargs["html_message"], "<p>Update Notice</p>")


class FilterTicketsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.mock_queryset = MagicMock(name="original")
        self.mock_filtered_1 = MagicMock(name="filtered1")
        self.mock_filtered_2 = MagicMock(name="filtered2")
        self.mock_ordered = MagicMock(name="ordered")

        self.mock_queryset.filter.return_value = self.mock_filtered_1
        self.mock_filtered_1.filter.return_value = self.mock_filtered_2
        self.mock_filtered_2.order_by.return_value = self.mock_ordered

    def test_filter_by_search_and_status_and_sort(self):
        request = self.factory.get(
            "/?search=login&status=in_progress&sort=priority_desc"
        )

        result = filter_tickets(request, self.mock_queryset)

        self.assertTrue(self.mock_queryset.filter.called)
        self.assertTrue(self.mock_filtered_1.filter.called)
        self.assertTrue(self.mock_filtered_2.order_by.called)
        self.assertEqual(result, self.mock_ordered)

    def test_filter_with_date_asc(self):
        request = self.factory.get("/?search=test&status=in_progress&sort=date_asc")
        result = filter_tickets(request, self.mock_queryset)

        self.mock_filtered_2.order_by.assert_called_with("created_at")
        self.assertEqual(result, self.mock_ordered)

    def test_filter_with_date_desc(self):
        request = self.factory.get("/?search=test&status=in_progress&sort=date_desc")
        result = filter_tickets(request, self.mock_queryset)

        self.mock_filtered_2.order_by.assert_called_with("-created_at")
        self.assertEqual(result, self.mock_ordered)

    def test_filter_with_priority_asc(self):
        request = self.factory.get("/?search=test&status=in_progress&sort=priority_asc")
        result = filter_tickets(request, self.mock_queryset)

        self.mock_filtered_2.order_by.assert_called()
        self.assertEqual(result, self.mock_ordered)

    def test_filter_with_priority_desc(self):
        request = self.factory.get(
            "/?search=test&status=in_progress&sort=priority_desc"
        )
        result = filter_tickets(request, self.mock_queryset)

        self.mock_filtered_2.order_by.assert_called()
        self.assertEqual(result, self.mock_ordered)

    def test_filter_with_no_search_status_or_sort(self):
        request = self.factory.get("/")
        result = filter_tickets(request, self.mock_queryset)

        self.mock_queryset.filter.assert_not_called()

        self.mock_filtered_1.filter.assert_not_called()
        self.mock_filtered_2.order_by.assert_not_called()

        self.assertEqual(result, self.mock_queryset)

    def test_filter_with_no_filters_applied(self):
        request = self.factory.get("/")
        result = filter_tickets(request, self.mock_queryset)

        self.mock_queryset.filter.assert_not_called()
        self.assertEqual(result, self.mock_queryset)


class GetFilteredTicketsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.ticket = Ticket.objects.create(
            title="Base query test",
            description="This should appear",
            status="in_progress",
            priority="low",
            creator=self.user,
        )
        self.mock_queryset = MagicMock(name="base_queryset")
        self.mock_filtered = MagicMock(name="filtered_queryset")
        self.mock_ordered = MagicMock(name="ordered_queryset")

        self.mock_queryset.filter.return_value = self.mock_filtered
        self.mock_filtered.filter.return_value = self.mock_filtered
        self.mock_filtered.order_by.return_value = self.mock_ordered

    def test_no_filters_applied(self):
        # base_queryset is provided, all params empty
        result = get_filtered_tickets(self.user, base_queryset=self.mock_queryset)
        self.assertEqual(result, self.mock_queryset)

    def test_filter_with_search_only(self):
        result = get_filtered_tickets(
            self.user, base_queryset=self.mock_queryset, search_query="login"
        )
        self.mock_queryset.filter.assert_called_once()
        self.assertEqual(result, self.mock_filtered)

    def test_filter_with_status_only(self):
        self.mock_queryset.filter.reset_mock()
        result = get_filtered_tickets(
            self.user, base_queryset=self.mock_queryset, status_filter="in_progress"
        )
        self.mock_queryset.filter.assert_called_once_with(status="in_progress")
        self.assertEqual(result, self.mock_filtered)

    def test_filter_with_search_and_status(self):
        result = get_filtered_tickets(
            self.user,
            base_queryset=self.mock_queryset,
            search_query="issue",
            status_filter="in_progress",
        )
        self.assertEqual(self.mock_filtered.filter.call_count, 1)  # second filter
        self.assertEqual(result, self.mock_filtered)

    def test_sort_date_asc(self):
        result = get_filtered_tickets(
            self.user,
            base_queryset=self.mock_queryset,
            search_query="x",
            status_filter="in_progress",
            sort_option="date_asc",
        )
        self.assertTrue(self.mock_filtered.order_by.called)
        self.mock_filtered.order_by.assert_called_with("created_at")
        self.assertEqual(result, self.mock_ordered)

    def test_sort_date_desc(self):
        result = get_filtered_tickets(
            self.user, self.mock_queryset, "x", "in_progress", "date_desc"
        )
        self.mock_filtered.order_by.assert_called_with("-created_at")
        self.assertEqual(result, self.mock_ordered)

    def test_sort_priority_asc(self):
        result = get_filtered_tickets(
            self.user, self.mock_queryset, "x", "in_progress", "priority_asc"
        )
        self.mock_filtered.order_by.assert_called()
        self.assertEqual(result, self.mock_ordered)

    def test_sort_priority_desc(self):
        result = get_filtered_tickets(
            self.user, self.mock_queryset, "x", "in_progress", "priority_desc"
        )
        self.mock_filtered.order_by.assert_called()
        self.assertEqual(result, self.mock_ordered)

    def test_invalid_sort_option(self):
        result = get_filtered_tickets(
            self.user, self.mock_queryset, "x", "in_porgess", "invalid_sort"
        )
        self.assertEqual(result, self.mock_filtered)

    def test_base_queryset_defaults_to_all(self):
        result = get_filtered_tickets(self.user)
        self.assertIn(self.ticket, result)


class HandleUploadedFileInChunksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.ticket = Ticket.objects.create(
            title="Test Ticket",
            description="This is a test ticket",
            status="in_progress",
            priority="low",
            creator=self.user,
        )
        self.file_content = b"some binary data"

    def test_handle_uploaded_file_bytes(self):
        handle_uploaded_file_in_chunks(
            self.ticket, self.file_content, filename="test.txt"
        )
        attachment = TicketAttachment.objects.get(ticket=self.ticket)
        self.assertEqual(attachment.file.read(), self.file_content)

    def test_handle_uploaded_file_readable_object(self):
        file_obj = SimpleUploadedFile("uploaded.txt", b"file content")
        handle_uploaded_file_in_chunks(self.ticket, file_obj)
        attachment = TicketAttachment.objects.get(ticket=self.ticket)
        self.assertEqual(attachment.file.read(), b"file content")

    def test_handle_uploaded_file_invalid_object(self):
        class Dummy:
            pass

        dummy_obj = Dummy()
        handle_uploaded_file_in_chunks(self.ticket, dummy_obj)
        self.assertEqual(TicketAttachment.objects.filter(ticket=self.ticket).count(), 0)

    def test_handle_uploaded_file_exception(self):
        file_obj = SimpleUploadedFile("error.txt", b"error content")

        with patch(
            "django.core.files.storage.Storage.save",
            side_effect=Exception("save error"),
        ):
            with self.assertRaises(Exception) as context:
                handle_uploaded_file_in_chunks(self.ticket, file_obj)
            self.assertIn("save error", str(context.exception))
