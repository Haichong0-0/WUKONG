import os
import io
import django
import sys
from unittest.mock import patch, MagicMock
from tickets.management.commands.fetch_emails import Command
from tickets.models import Ticket, User, Department, Response
from email import message_from_bytes
from django.utils.timezone import now, timedelta
from django.core import mail
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TransactionTestCase
from django.test import override_settings
from django.conf import settings
import email
from email.mime.text import MIMEText
import imaplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

# Setup Django environment

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "query_hub.settings")
django.setup()

class FetchEmailsTest(TransactionTestCase):
    """Test the fetch_emails command"""

    def setUp(self):
        """Creates a Ticket and User before each test"""
        self.command = Command()
        self.sender_email = "student@wukong.ac.uk"
        self.subject = "Test Ticket Subject"
        self.body = "This is a test ticket body."
        self.department = Department.objects.create(name="academic_support")
        
        self.mock_post_patcher = patch("requests.post")
        self.mock_post = self.mock_post_patcher.start()
        
        self.mock_post.return_value.status_code = 200
        self.mock_post.return_value.json.return_value = {
            "attributeScores": {
                "SPAM": {"summaryScore": {"value": 0.9}}
            }
        }
        self.mock_post.return_value.text = '{"attributeScores": {"SPAM": {"summaryScore": {"value": 0.9}}}}'

        settings.TESTING = True
        settings.PERSPECTIVE_API_KEY = "fake_api_key"
        settings.IMAP_HOST = "fake_imap_host"
        settings.IMAP_PORT = 993
        settings.EMAIL_HOST_USER = "test@wukong.ac.uk"
        settings.EMAIL_HOST_PASSWORD = "password"
        

        with transaction.atomic():  
            self.department = Department.objects.create(name="general_enquiry")
            self.user = User.objects.create(email=self.sender_email.strip(), username="@student")
            self.old_ticket_no_response = Ticket.objects.create(
                title=self.subject.strip(),
                description=self.body.strip(),
                creator=self.user,
                sender_email=self.sender_email.strip(),
                status="open",
                assigned_department=self.department,
                created_at=now() - timedelta(days=8)
            )
            self.existing_ticket = Ticket.objects.create(
                title=self.subject.strip(),
                description=self.body.strip(),
                creator=self.user,
                sender_email=self.sender_email.strip(),
                status="open",
                assigned_department=self.department,
                created_at=now() - timedelta(days=3)
            )
            self.response = Response.objects.create(
                ticket=self.existing_ticket,
                responder=self.user,
                content="This is a response from the officer.",
                created_at=now() - timedelta(days=2)
            )
        self.old_ticket_no_response.refresh_from_db()
        self.existing_ticket.refresh_from_db()
        
    def tearDown(self):
        """Deletes all Tickets and Users after each test"""
        Ticket.objects.all().delete()
        User = get_user_model()
        User.objects.all().delete()
        Department.objects.all().delete()
        Response.objects.all().delete()
        self.mock_post_patcher.stop()

    
   
    @patch("tickets.management.commands.fetch_emails.imaplib.IMAP4_SSL")
    @patch("tickets.management.commands.fetch_emails.send_mail")  # Mock send_mail 
    def test_fetch_emails_sends_confirmation(self, mock_send_mail, mock_imap):
        """Test if the fetch_emails command sends a confirmation email"""
      
        Ticket.objects.all().delete()
        
        # 1️⃣ Mock IMAP Sever
        mock_mail = MagicMock()
        mock_imap.return_value = mock_mail

        # 2️⃣ Mock IMAP Commands
        mock_mail.search.return_value = ("OK", [b"1"])  # Only one email
        mock_mail.fetch.return_value = ("OK", [(b"1", (b"Fake Email Content"))])  # Mock email content

        # 3️⃣ Mock Email Content
        fake_email_bytes = b"From: student1@wukong.ac.uk\nSubject: Help Needed\n\nThis is a test email."
        fake_email_msg = message_from_bytes(fake_email_bytes)  # Make sure it's a valid email message
        mock_mail.fetch.return_value = ("OK", [(b"1", fake_email_msg.as_bytes())])

        # 4️⃣ Run the fetch_emails command
        command = Command()
        command.handle()

        # 5️⃣ Check if a Ticket is created
        ticket = Ticket.objects.first()
        self.assertIsNotNone(ticket, "❌ Ticket not created")
        self.assertEqual(ticket.title, "Help Needed")

        # 6️⃣ Check if send_mail is called
        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args

        # 7️⃣ Check if the email is sent to the student
        self.assertIn("student1@wukong.ac.uk", kwargs.get("recipient_list"))

        # 8️⃣ Check if the email content is correct
        self.assertIn("WuKong Help Desk", kwargs.get("html_message"))
        self.assertIn("Your Ticket Has Been Received", kwargs.get("html_message"))

    def test_email_subject_decoding(self):
        """Test that the email subject is correctly decoded."""
        Ticket.objects.all().delete()
        encoded_subject = "=?utf-8?b?dGVzdCBzdWJqZWN0?="
        fake_email_bytes = f"From: student@wukong.ac.uk\nSubject: {encoded_subject}\n\nTest Body.".encode()
    
        fake_email_msg = message_from_bytes(fake_email_bytes)
    
        with patch("tickets.management.commands.fetch_emails.imaplib.IMAP4_SSL") as mock_imap:
            mock_mail = MagicMock()
            mock_imap.return_value = mock_mail
            mock_mail.search.return_value = ("OK", [b"1"])
            mock_mail.fetch.return_value = ("OK", [(b"1", fake_email_msg.as_bytes())])

            self.command.handle()
             
            ticket = Ticket.objects.first()
            self.assertIsNotNone(ticket)
            self.assertEqual(ticket.title, "test subject")
       
    def test_duplicate_ticket_with_response(self):
        """Test that a ticket with a response is detected as a duplicate."""
        if self.existing_ticket.responses.count() > 0:
            self.existing_ticket.status = "closed"
            self.existing_ticket.save()
            self.existing_ticket.refresh_from_db()
        
        duplicate_ticket = self.command.is_duplicate_ticket(
        self.sender_email,
        self.subject,
        self.body
        )
        
        self.assertIsNotNone(duplicate_ticket)  # Should detect a duplicate
        self.assertEqual(duplicate_ticket.id, self.existing_ticket.id, "❌ Duplicate ticket not detected")

    def test_duplicate_ticket_without_response_after_7_days(self):
        """Test that a ticket can be resubmitted if no response after 7 days."""
        old_created_at = now() - timedelta(days=8)

        with transaction.atomic():
            old_ticket = Ticket.objects.create(
                title=self.subject,
                description=self.body,
                creator=self.user,
                sender_email=self.sender_email,
                status="open",
                assigned_department=self.department.name
            )

        # Update the created_at date to 8 days ago
        Ticket.objects.filter(id=old_ticket.id).update(created_at=old_created_at)

        # Refresh the ticket
        old_ticket.refresh_from_db()
        # Ensure the ticket was created 8 days ago
        self.assertLess(old_ticket.created_at, now() - timedelta(days=7), "❌ created_at date is not 8 days ago")
        duplicate_ticket= self.command.is_duplicate_ticket(self.sender_email, self.subject, self.body)
        # Ensure the ticket can be resubmitted after 7 days without a response
        self.assertIsNone(duplicate_ticket, "❌ Duplicate ticket detected after 7 days")
        
    def test_duplicate_ticket_email_notification(self):
        """Test that a duplicate ticket sends a notification email."""
        
        # Create a recent duplicate ticket
        existing_ticket = Ticket.objects.create(
            title=self.subject,
            description=self.body,
            creator=self.user,
            sender_email=self.sender_email,
            status="open",
            assigned_department=self.department,
            created_at=now() - timedelta(days=3)  # Within 7 days
        )

        # Call the function to send an email
        self.command.send_duplicate_notice(self.sender_email, self.subject, existing_ticket.id)

        # Verify an email was sent
        self.assertEqual(len(mail.outbox), 1, "❌ No email sent")
        
        sent_mail = mail.outbox[0]
        self.assertIn("Duplicate Ticket Submission", sent_mail.subject, "❌ Email subject is incorrect")

        self.assertIn("You have already submitted a ticket", sent_mail.body, "❌ Email body is incorrect")
        self.assertIn(str(existing_ticket.id), sent_mail.body, "❌ Ticket ID not found in email body")

    def test_skip_failure_notification(self):
        """Test that failure notification emails are skipped."""
        Ticket.objects.all().delete()
        fake_email_bytes = b"From: <mailer-daemon@server.com>\nSubject: Delivery Status Notification\n\nFailure report."
        fake_email_msg = message_from_bytes(fake_email_bytes)

        with patch("tickets.management.commands.fetch_emails.imaplib.IMAP4_SSL") as mock_imap:
            mock_mail = MagicMock()
            mock_imap.return_value = mock_mail
            mock_mail.search.return_value = ("OK", [b"1"])
            mock_mail.fetch.return_value = ("OK", [(b"1", fake_email_msg.as_bytes())])

            self.command.handle()

            # Ensure no ticket was created
            ticket = Ticket.objects.first()
            self.assertIsNone(ticket, "❌ Ticket created for failure notification")
    
    @patch("django.conf.settings.TESTING", False)
    def test_is_spam_detects_high_score(self):
        """Test is_spam returns True for high spam score"""
        result = self.command.is_spam("Spammy subject", "This is a spam message")
        self.assertTrue(result, "Spam email should return True")
    
    @patch("django.conf.settings.TESTING", False)
    def test_is_spam_detects_low_score(self):
        """Test is_spam returns False for low spam score"""
        self.mock_post.return_value.json.return_value = {
            "attributeScores": {
                "SPAM": {"summaryScore": {"value": 0.2}}
            }
        }
        
        result = self.command.is_spam("Normal subject", "This is a normal message")
        self.assertFalse(result, "Non-spam email should return False")

    def test_is_spam_handles_api_failure(self):
        """Test is_spam returns False when the API fails"""
        self.mock_post.return_value.status_code = 500  # Return a server error
        self.mock_post.return_value.text = "Internal Server Error"  # Return a server error message
        self.mock_post.return_value.json.side_effect = ValueError("Invalid JSON")  # Raise an exception

        result = self.command.is_spam("Test subject", "Test body")
        self.assertFalse(result, "API failure should return False")
    
    def _get_fake_imap(self, msg):
        """Simulates an IMAP connection returning one unread email."""
        fake_mail = MagicMock()
        fake_mail.search.return_value = ("OK", [b"1"])
        payload = msg.as_bytes()
        fake_mail.fetch.return_value = ("OK", [(None, payload)])
        fake_mail.store.return_value = ("OK", [])
        fake_mail.logout.return_value = ("OK",)
        return fake_mail
   
    def _create_dummy_email_message(self, subject, sender, body):
        """Creates a dummy email message for testing."""
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = f"Test User <{sender}>"
        return msg
    
    @patch.object(Command, 'is_spam', return_value=True)
    @patch('imaplib.IMAP4_SSL')
    def test_handle_spam_email(self, mock_imap, mock_is_spam):
        """
        Test that if is_spam returns True, no ticket is created.
        A user is still created for the sender.
        """
        Ticket.objects.all().delete()
        subject = "Spam Email"
        sender_email = "spammer@wukong.ac.uk"
        body = "Buy cheap products now!"
        msg = self._create_dummy_email_message(subject, sender_email, body)
        fake_imap = self._get_fake_imap(msg)
        mock_imap.return_value = fake_imap

        command = Command()
        command.handle()

        # Assert that no ticket is created because the email is flagged as spam.
        self.assertEqual(Ticket.objects.count(), 0)
        # Assert that a user was created.
        self.assertTrue(User.objects.filter(email=sender_email).exists())

    @patch.object(Command, 'is_duplicate_ticket')
    @patch.object(Command, 'send_duplicate_notice')
    @patch.object(Command, 'is_spam', return_value=False)
    @patch('imaplib.IMAP4_SSL')
    def test_handle_duplicate_ticket(self, mock_imap, mock_is_spam, mock_send_duplicate_notice, mock_is_duplicate_ticket):
        """
        Test that if is_duplicate_ticket returns an existing ticket,
        the duplicate notice is sent and no new ticket is created.
        """
        Ticket.objects.all().delete()
        subject = "Duplicate Email"
        sender_email = "duplicate@wukong.ac.uk"
        body = "I need help with my account."
        msg = self._create_dummy_email_message(subject, sender_email, body)
        fake_imap = self._get_fake_imap(msg)
        mock_imap.return_value = fake_imap

        # Create a dummy ticket object with an id to simulate an existing ticket.
        dummy_ticket = MagicMock()
        dummy_ticket.id = 123
        mock_is_duplicate_ticket.return_value = dummy_ticket

        command = Command()
        command.handle()

        # Check that the duplicate notice was sent with the correct parameters.
        mock_send_duplicate_notice.assert_called_once_with(sender_email, subject, dummy_ticket.id)
        # Assert that no new ticket was created.
        self.assertEqual(Ticket.objects.count(), 0)
        # Assert that a user was created.
        self.assertTrue(User.objects.filter(email=sender_email).exists())
        
    @patch("tickets.management.commands.fetch_emails.imaplib.IMAP4_SSL")
    def test_handle_exception_handling(self, mock_imap):
        """Test that the handle method correctly catches and logs exceptions."""

        # Mock the IMAP connection to raise an exception
        mock_imap.side_effect = imaplib.IMAP4.error("IMAP Connection Failed")

        command = Command()

        with patch("sys.stderr.write") as mock_stderr:
            command.handle()
            # Ensure the error message is logged to stderr
            mock_stderr.assert_called()
            error_message = mock_stderr.call_args[0][0]
            self.assertIn("❌ Error fetching emails: IMAP Connection Failed", error_message)
            
    def test_categorize_ticket_academic_support(self):
        """Test that a ticket is categorized as academic_support"""

        subject = "I need help with my exam schedule"
        body = "Can you tell me when the exams are scheduled?"

        department = self.command.categorize_ticket(subject, body)

        self.assertIsNotNone(department, "❌ Department should not be None")
        self.assertEqual(department.name, "academic_support", "❌ Incorrect department assigned")
        
    def test_old_ticket_with_no_response_allows_resubmission(self):
        Ticket.objects.filter(id=self.old_ticket_no_response.id).update(created_at=now() - timedelta(days=8))
            
        self.old_ticket_no_response.refresh_from_db()
        response_count = self.old_ticket_no_response.responses.count()
        self.assertEqual(response_count, 0, "❌ Ticket should have no responses")

        duplicate_ticket = self.command.is_duplicate_ticket(
            self.sender_email, self.subject, self.body
        )
        self.assertIsNone(duplicate_ticket, "❌ Duplicate ticket should be allowed for resubmission")
    
    @patch.object(Command, "send_duplicate_notice")
    def test_old_ticket_with_response_is_duplicate(self, mock_send_duplicate_notice):
        """Test that a ticket with a response is considered a duplicate and sends a notification"""
        Ticket.objects.filter(id=self.old_ticket_no_response.id).update(created_at=now() - timedelta(days=8))
        self.old_ticket_no_response.refresh_from_db()
        # Create a response for the old ticket
        self.response = Response.objects.create(
            ticket=self.old_ticket_no_response,
            responder=self.user,
            content="This is an officer's response.",
            created_at=now() - timedelta(days=7)
        )
        
        duplicate_ticket = self.command.is_duplicate_ticket(
            self.sender_email, self.subject, self.body
        )

        # ✅ ensure return old_ticket_no_response
        self.assertIsNotNone(duplicate_ticket, "❌ Duplicate ticket should NOT be allowed for resubmission")
        self.assertEqual(duplicate_ticket.id, self.old_ticket_no_response.id, "❌ Incorrect duplicate ticket detected")

        # ✅ enture send_duplicate_notice is called
        mock_send_duplicate_notice.assert_called_once_with(self.sender_email, self.subject, self.old_ticket_no_response.id)

    
    @override_settings(TESTING=False)
    @patch("builtins.print")
    @patch("tickets.management.commands.fetch_emails.requests.post")
    def test_is_spam_exception_prints_error(self, mock_post, mock_print):
        
        mock_post.side_effect = requests.RequestException("API Timeout")
        
        result = self.command.is_spam(self.subject, self.body)
        self.assertFalse(result, "is_spam should return False when requests.post raises an exception")
        
        # varify print is called with the correct error message
        mock_print.assert_called_once()
        args, kwargs = mock_print.call_args
        self.assertEqual(args[0], "❌ Error connecting to Perspective API:")
        self.assertIn("API Timeout", str(args[1]))
    
    @override_settings(TESTING=False)
    @patch("builtins.print")
    @patch("tickets.management.commands.fetch_emails.requests.post")
    def test_is_spam_value_error(self, mock_post, mock_print):
        
        """Test that is_spam returns False and prints an error message for invalid JSON responses"""
        # Mock the post request to return a 200 status code, but invalid
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.side_effect = ValueError
        mock_post.return_value = fake_response
        
        result = self.command.is_spam(self.subject, self.body)
        self.assertFalse(result, "is_spam should return False when requests.post raises a ValueError")
        
        # Verify that the error message is printed
        mock_print.assert_called_once_with("❌ Invalid JSON response from Perspective API")
        
    
    def test_multipart_first_valid_part(self):
        """
        Build a multipart email with multiple parts, where the first text/plain part
        is valid and should be used as the body of the email.
        """
        subject = "Test subject"
        from_addr = "Test <test@wukong.ac.uk>"
        valid_text = "This is valid text."
        
        # Build a multipart email
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = from_addr
        
        # Attachments should be
        # ignored, only the first text/plain part should be used
        part_attachment = MIMEText("Attachment content", "plain", "utf-8")
        part_attachment.add_header("Content-Disposition", "attachment")
        msg.attach(part_attachment)
        
        # Then add a valid text/plain part
        part_valid = MIMEText(valid_text, "plain", "utf-8")
        part_valid.add_header("Content-Disposition", "inline")
        msg.attach(part_valid)
        
        parsed_subject, parsed_sender, parsed_body = self.command.parse_email_message(msg)
        self.assertEqual(parsed_body, valid_text)
        self.assertEqual(parsed_sender, "test@wukong.ac.uk")

    def test_multipart_no_valid_part(self):
        """
        Build a multipart email with multiple parts, where no text/plain part
        is valid, so the body should be an empty string.
        """
        subject = "Test subject"
        from_addr = "Test <test@wukong.ac.uk>"
        attachment_text = "This is an attachment text."
        
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = from_addr
        
        # Add an attachment part that should be ignored
        part_attachment = MIMEText(attachment_text, "plain", "utf-8")
        part_attachment.add_header("Content-Disposition", "attachment")
        msg.attach(part_attachment)
        
        parsed_subject, parsed_sender, parsed_body = self.command.parse_email_message(msg)
        self.assertEqual(parsed_body, "")
        self.assertEqual(parsed_sender, "test@wukong.ac.uk")
    
    def test_multipart_part_payload_none(self):
        """
        Build a multipart email with a text/plain part where the payload is None,
        which should result in an empty
        """
        subject = "Test subject"
        from_addr = "Test <test@wukong.ac.uk>"
        
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = from_addr

        part_none = MIMEText("dummy", "plain", "utf-8")
        part_none.add_header("Content-Disposition", "inline")
        part_none.get_payload = lambda decode=True: None  
        
        msg.attach(part_none)
        
        parsed_subject, parsed_sender, parsed_body = self.command.parse_email_message(msg)
        self.assertEqual(parsed_body, "", "When payload is None, body should be an empty string")
    
    def test_non_multipart_payload_none(self):
        """
        Test that when a non-multipart email has a payload of None,
        the body is an empty string.
        """
        subject = "Test subject"
        from_addr = "Test <test@wukong.ac.uk>"

        msg = MIMEText("dummy text", "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_addr

        # Mock the get_payload method to return None
        msg.get_payload = lambda decode=True: None

        parsed_subject, parsed_sender, parsed_body = self.command.parse_email_message(msg)
        self.assertEqual(parsed_body, "", "When payload is None, body should be an empty string")