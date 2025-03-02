import imaplib
import email
import re
from email.header import decode_header
from django.core.management.base import BaseCommand
from tickets.models import Ticket, Department, User
from django.conf import settings
from django.core.mail import send_mail


class Command(BaseCommand):
    help = "Fetch unread emails from Gmail and convert them into tickets"

    def handle(self, *args, **kwargs):
        try:
            # Connect to Gmail IMAP server
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login("wukonghelpdesk@gmail.com", "bynw apnb vmuu nmun")
            mail.select("inbox")  # Select the inbox

            # Search for unread emails
            status, messages = mail.search(None, "UNSEEN")
            email_ids = messages[0].split()

            for email_id in email_ids:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Decode email subject
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8")

                        sender = msg.get("From")
                        
                        # Extract the sender's email address
                        match = re.search(r"<(.+?)>", sender)
                        sender_email = match.group(1) if match else sender

                        # filter out failure notifications
                        if "mailer-daemon" in sender_email.lower() or "delivery status notification" in subject.lower():
                            self.stdout.write(self.style.WARNING(f"⚠️ Skipping failure notification from {sender_email}: {subject}"))
                            continue
                        
                        body = ""

                        # Extract the email body
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                if content_type == "text/plain":
                                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                            
                        assigned_department = self.categorize_ticket(subject, body)
                        
                        # revise the code to create a new user if the sender is not in the database
                        user = User.objects.filter(email=sender_email).first()
                        if not user:
                            user = User.objects.create(username=sender_email.split("@")[0], email=sender_email, password="TemporaryPass123")
                            self.stdout.write(self.style.WARNING(f"⚠️ Created new user for {sender_email}"))

                        # create a new ticket
                        Ticket.objects.create(
                            title=subject,
                            description=body,
                            creator=user,
                            sender_email=sender_email,
                            status="open",
                            assigned_department=assigned_department
                        )

                        # send a confirmation email to the student
                        self.send_confirmation_email(sender_email, subject)

                        self.stdout.write(self.style.SUCCESS(f"🎫 Ticket created from email: {subject}"))

                        # mark the email as read
                        mail.store(email_id, "+FLAGS", "\\Seen")

            mail.logout()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error fetching emails: {e}"))

    
    def categorize_ticket(self, subject, body):
        """Assigns a category based on keywords in the subject or body."""
        categories = {
            "general": "general_enquiry",
            "course|academic|exam|grades|study": "academic_support",
            "health|medical|doctor|sick|hospital": "health_services",
            "financial|payment|tuition|scholarship": "financial_aid",
            "career|job|internship|resume": "career_services",
            "welfare|counseling|support": "welfare",
            "misconduct|disciplinary|plagiarism": "misconduct",
            "wifi|login|it support|computer|software": "it_support",
            "housing|accommodation|dorm|rent": "housing",
            "admissions|application|enrollment": "admissions",
            "library|books|borrowing|overdue": "library_services",
            "research|thesis|proposal|publication": "research_support",
            "study abroad|exchange|visa": "study_abroad",
            "alumni|graduate|networking": "alumni_relations",
            "exam|grades|schedule|timetable": "exam_office",
            "security|crime|theft|safety": "security",
            "language|english|spanish|french": "language_centre",
        }

        for keyword_pattern, category_name in categories.items():
            if any(keyword in subject.lower() or keyword in body.lower() for keyword in keyword_pattern.split("|")):
                return Department.objects.filter(name=category_name).first()

        return Department.objects.filter(name="general_enquiry").first()  
    
    def send_confirmation_email(self, student_email, ticket_title):
        """Sends a confirmation email to the student."""
        subject = f"Your Ticket '{ticket_title}' Has Been Received"
        message = f"""
        Hello,

        Thank you for reaching out. Your ticket has been received and assigned to the relevant department.
        We will get back to you as soon as possible.

        Regards,  
        WuKong Help Desk
        """
        send_mail(subject, message, settings.EMAIL_HOST_USER, [student_email])
        self.stdout.write(self.style.SUCCESS(f"📧 Confirmation email sent to {student_email}"))
