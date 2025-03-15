import imaplib
import email
import re
import sys
import requests
from email.header import decode_header
from django.core.management.base import BaseCommand
from tickets.models import Ticket, Department, User, AITicketProcessing
from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now, timedelta
import os
from django.db.models import Count
from tickets.ai_service import ai_process_ticket


class Command(BaseCommand):
    help = "Fetch unread emails from Gmail and convert them into tickets"

    def handle(self, *args, **kwargs):
        try:
            # Connect to Gmail IMAP server
            #1.
            mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
            mail.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            mail.select("inbox")  # Select the inbox

            # Search for unread emails
            status, messages = mail.search(None, "UNSEEN")
            email_ids = messages[0].split()

            for email_id in email_ids:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    payload = response_part[1]
                    msg = email.message_from_bytes(payload)

                    # Decode email subject
                    subject, sender_email, body = self.parse_email_message(msg)
                    
                    # filter out failure notifications
                    if "mailer-daemon" in sender_email.lower() or "delivery status notification" in subject.lower():
                        continue
                    
                    # revise the code to create a new user if the sender is not in the database
                    user, created = User.objects.get_or_create(
                        email=sender_email,
                        defaults={
                            "username": sender_email.split("@")[0],
                            "password": "TemporaryPass123",
                        }
                    )
                    if created:
                        user.set_password("TemporaryPass123")
                        user.save()
                        
                    # Check for AI-based spam detection
                    if self.is_spam(subject, body):
                        continue
                    
                    # Check for duplicate tickets
                    existing_ticket = self.is_duplicate_ticket(sender_email, subject, body)

                    if existing_ticket:
                        self.send_duplicate_notice(sender_email, subject, existing_ticket.id)
                        continue  # Skip creating the ticket                       

                    department = self.categorize_ticket(subject, body)

                    # create a new ticket
                    ticket = Ticket.objects.create(
                        title=subject,
                        description=body,
                        creator=user,
                        sender_email=sender_email,
                        status="open",
                        assigned_department=department
                    )

                    ai_process_ticket(ticket)

                    # send a confirmation email to the student
                    self.send_confirmation_email(sender_email, subject)

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

        # Check if any keyword is present in the subject or body
        for keyword_pattern, category_name in categories.items():
            if any(keyword in subject.lower() or keyword in body.lower() for keyword in keyword_pattern.split("|")):
                return Department.objects.filter(name=category_name).first()
            

        return Department.objects.filter(name="general_enquiry").first()
    
    def send_confirmation_email(self, student_email, ticket_title):
        """Sends a confirmation email to the student with a signature, school logo, and styled font."""
        
        subject = f"Your Ticket '{ticket_title}' Has Been Received"
        
        # HTML Email Content
        # 吗的彩色的Logo和Signature打不出来 需要替换成其他的
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333; text-align: center;">
                <div style="border: 1px solid #ddd; padding: 20px; border-radius: 10px; max-width: 600px; margin: auto;">
        
                    <!-- WUKONG Logo with Gradient Background -->
                    <h1 style="font-size: 32px; font-weight: bold; display: inline-block;
                            background: linear-gradient(90deg, red, orange, yellow, green, blue, indigo, violet);
                            color: white; padding: 10px 20px; border-radius: 5px;">
                        WUKONG
                    </h1>

                    <h2 style="text-align: center; color: #0056b3;">Your Ticket Has Been Received</h2>

                    <p style="text-align: left;">Hello,</p>
                    <p style="text-align: left;">Thank you for reaching out. Your ticket titled <b>'{ticket_title}'</b> has been received and assigned to the relevant department.</p>
                    <p style="text-align: left;">We will get back to you as soon as possible.</p>
                    <br>

                    <!-- Signature Part -->
                    <p style="border-top: 2px solid #0056b3; padding-top: 10px; font-size: 14px; text-align: left; line-height: 1.6;">
                        <strong>Best regards,</strong><br>

                        <!-- WuKong Help Desk Gradient -->
                        <span style="font-size: 16px; font-weight: bold; display: inline-block; margin-top: 5px;
                                    background: linear-gradient(90deg, red, orange, yellow, green, blue, indigo, violet);
                                    color: white; padding: 3px 8px; border-radius: 5px;">
                            WuKong Help Desk
                        </span>
                        <br><br>

                        <span style="color: #007BFF;"><strong>Email:</strong></span> 
                        <a href="mailto:wukonghelpdesk@gmail.com" style="color: #007BFF; text-decoration: none;">wukonghelpdesk@gmail.com</a><br>

                        <span style="color: #28A745;"><strong>Phone:</strong></span> 
                        <span style="color: #28A745;">+1 (234) 567-890</span><br>

                        <span style="color: #DC3545;"><strong>Website:</strong></span> 
                        <a href="https://github.com/Haichong0-0/WUKONG" style="color: #DC3545; text-decoration: none;">https://github.com/Haichong0-0/WUKONG</a>
                    </p>
                </div>
            </body>
        </html>
        """
    
        # Sending email with HTML content
        send_mail(
            subject,
            message="",  # Leave plain text empty
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[student_email],
            fail_silently=False,
            html_message=html_message,  # Use the HTML content
        )
        
    def is_duplicate_ticket(self, sender_email, subject, body):
        """
        Checks if a duplicate ticket exists in the last 7 days.
        - It allows resubmission if no response is received within 7 days.
        """
        time_threshold = now() - timedelta(days=7)
        # search for an old ticket with the same details
        old_ticket = Ticket.objects.annotate(response_count=Count("responses")).filter(
            sender_email=sender_email.strip(),
            title__iexact=subject.strip(),
            description__iexact=body.strip(),
            created_at__lt=time_threshold  # 7 days ago
        ).order_by("-created_at").first()

        if old_ticket:
            if old_ticket.response_count == 0:  # Allow resubmission if no response over 7 days
                return None
            else:
                self.send_duplicate_notice(sender_email, subject, old_ticket.id)  # Notify student
                return old_ticket  # Reject resubmission if there is a response even after 7 days
    
        # Search for a recent ticket within 7 days
        recent_ticket = Ticket.objects.filter(
            sender_email=sender_email.strip(),
            title__iexact=subject.strip(),
            description__iexact=body.strip(),
            created_at__gte=time_threshold  # within 7 days
        ).order_by("-created_at").first()
        
        if recent_ticket:
            self.send_duplicate_notice(sender_email, subject, recent_ticket.id)  # Notify student
            return recent_ticket  # Check for a recent ticket within 7 days
        
        return None  # No duplicate ticket found

    def send_duplicate_notice(self, student_email, ticket_title, ticket_id):
        """
        Sends an email notifying the student that their ticket is a duplicate.
        """
        subject = f"Duplicate Ticket Submission - {ticket_title}"
        message = f"""
        Hello,

        You have already submitted a ticket with the same details: '{ticket_title}'.
        You can track it using Ticket ID #{ticket_id}.

        Our team is currently working on it. Please wait for a response before submitting again.
        If no response is received within 7 days, you may resubmit.

        Thank you for your patience.

        Regards,
        WuKong Help Desk 
        """
        send_mail(subject, message, settings.EMAIL_HOST_USER, [student_email])

    def is_spam(self, subject, body):
        """Uses Google's Perspective API to detect spam."""
        if settings.TESTING:
            return False
        
        PERSPECTIVE_API_KEY = settings.PERSPECTIVE_API_KEY
        
        url = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"
        content = f"{subject} {body}"

        data = {
            "comment": {"text": content},
            "requestedAttributes": {"TOXICITY": {}, "SPAM": {}},
            "languages": ["en"],
            "doNotStore": True,
        }

        try:
            response = requests.post(f"{url}?key={PERSPECTIVE_API_KEY}", json=data)
            response.raise_for_status()  # check for any request errors
            result = response.json()

            # Check if the spam score is above the threshold
            spam_score = result.get("attributeScores", {}).get("SPAM", {}).get("summaryScore", {}).get("value", 0)
            return spam_score > 0.8  
        except requests.RequestException as e:
            print("❌ Error connecting to Perspective API:", e)
            return False
        except ValueError:
            print("❌ Invalid JSON response from Perspective API")
            return False

    def parse_email_message(self, msg):
        """Decodes the email message and extracts the subject, sender, and body."""
        
        # Decode email subject
        subject = ""
        for part, encoding in decode_header(msg.get("Subject", "")):
            if isinstance(part, bytes):
                subject += part.decode(encoding or "utf-8", errors="ignore")
            else:
                subject += part

        # Extract sender's email    
        sender = msg.get("From", "")
        match = re.search(r"<(.+?)>", sender)
        sender_email = match.group(1) if match else sender

        # Extract email body only if necessary
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    part_payload = part.get_payload(decode=True)
                    if part_payload:
                        body = part_payload.decode("utf-8", errors="ignore")
                    break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="ignore")
            
        return subject, sender_email, body
    
    

      