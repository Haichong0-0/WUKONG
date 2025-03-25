from django.conf import settings
from django.shortcuts import redirect
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import send_mail
from django.db.models import Q, Case, When, IntegerField
from tickets.models import Ticket, TicketAttachment
from django.core.files.base import ContentFile
from django.utils.text import get_valid_filename
from tickets.models import user_directory_path


def login_prohibited(view_function):
    """Decorator for view functions that redirect users away if they are logged in."""

    def modified_view_function(request):
        if request.user.is_authenticated:
            return redirect(settings.REDIRECT_URL_WHEN_LOGGED_IN)
        else:
            return view_function(request)

    return modified_view_function


# Student will receive an email when they submit a ticket in tickets system
def send_ticket_confirmation_email(ticket):
    """
    Send a confirmation email to the student after submitting a ticket.
    Uses HTML + plain text fallback.
    """
    ticket_id = ticket.id
    subject = f"Ticket #{ticket_id} Confirmation"
    recipient_email = ticket.creator.email
    context = {"user": ticket.creator, "ticket": ticket}

    html_content = render_to_string("emails/ticket_confirmation.html", context)
    text_content = strip_tags(html_content)  # Convert HTML to plain text

    email = EmailMultiAlternatives(
        subject, text_content, "wukonghelpdesk@gmail", [recipient_email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


# This function sends an email to the student when their ticket has been responded to.
def send_response_notification_email(
    student_email, ticket_title, response_message, ticket_id
):
    """Sends an email to notify the student that their ticket has been responded to."""

    subject = f"Update on Your Ticket: '{ticket_title}'"

    context = {
        "student_name": student_email.split("@")[0],
        "ticket_title": ticket_title,
        "response_message": response_message,
        "ticket_id": ticket_id,
    }

    html_message = render_to_string("emails/response_notification.html", context)
    text_message = strip_tags(html_message)

    send_mail(
        subject,
        text_message,  # Plain text version
        settings.EMAIL_HOST_USER,
        [student_email],
        fail_silently=False,
        html_message=html_message,  # HTML version
    )


# This function sends an email to the student when their ticket has been updated.
def send_updated_notification_email(
    student_email, ticket_title, response_message, ticket_id
):
    """Sends an email to notify the student that their ticket has been updated."""

    subject = f"Update on Your Ticket: '{ticket_title}'"

    context = {
        "student_name": student_email.split("@")[0],
        "ticket_title": ticket_title,
        "response_message": response_message,
        "ticket_id": ticket_id,
    }

    html_message = render_to_string("emails/updated_notification.html", context)
    text_message = strip_tags(html_message)

    send_mail(
        subject,
        text_message,  # Plain text version
        settings.EMAIL_HOST_USER,
        [student_email],
        fail_silently=False,
        html_message=html_message,  # HTML version
    )


def send_notification_email_to_specialist(
    specialist_email, ticket_title, ticket_id, student_email, response_message
):
    """Sends an email to notify the specialist they are assigned to a ticket."""

    subject = f"You have a new ticket to handle: '{ticket_title}'"

    context = {
        "specialist_name": specialist_email.split("@")[0],
        "ticket_title": ticket_title,
        "response_message": response_message,
        "ticket_id": ticket_id,
    }

    html_message = render_to_string("emails/notice_to_specialist.html", context)
    text_message = strip_tags(html_message)

    send_mail(
        subject,
        text_message,
        settings.EMAIL_HOST_USER,
        [specialist_email],
        fail_silently=False,
        html_message=html_message,
    )


def send_updated_notification_email_to_specialist_or_program_officer(
    school_email, ticket_title, ticket_id, student_email, response_message
):
    """Sends an email to notify the specialist they are assigned to a ticket."""

    subject = f"Your assigned ticket is updated by student: '{ticket_title}'"

    context = {
        "name": school_email.split("@")[0],
        "ticket_title": ticket_title,
        "response_message": response_message,
        "ticket_id": ticket_id,
    }

    html_message = render_to_string("emails/update_notice.html", context)
    text_message = strip_tags(html_message)

    send_mail(
        subject,
        text_message,
        settings.EMAIL_HOST_USER,
        [school_email],
        fail_silently=False,
        html_message=html_message,
    )


def filter_tickets(request, tickets):
    """Filter tickets based on search query, status filter and sort option."""
    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    sort_option = request.GET.get("sort", "")

    priority_case = Case(
        When(priority="urgent", then=4),
        When(priority="high", then=3),
        When(priority="medium", then=2),
        When(priority="low", then=1),
        output_field=IntegerField(),
    )

    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    if status_filter:
        tickets = tickets.filter(status=status_filter)

    if sort_option == "date_asc":
        tickets = tickets.order_by("created_at")
    elif sort_option == "date_desc":
        tickets = tickets.order_by("-created_at")
    elif sort_option == "priority_asc":
        tickets = tickets.order_by(priority_case)
    elif sort_option == "priority_desc":
        tickets = tickets.order_by(-priority_case)

    return tickets


def get_filtered_tickets(
    user, base_queryset=None, search_query="", status_filter="", sort_option=""
):
    """
    Apply search, status filtering, and sorting to a base ticket queryset.
    """
    if base_queryset is None:
        base_queryset = Ticket.objects.all()

    if search_query:
        base_queryset = base_queryset.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    if status_filter:
        base_queryset = base_queryset.filter(status=status_filter)

    priority_case = Case(
        When(priority="urgent", then=4),
        When(priority="high", then=3),
        When(priority="medium", then=2),
        When(priority="low", then=1),
        output_field=IntegerField(),
    )

    if sort_option == "date_asc":
        base_queryset = base_queryset.order_by("created_at")
    elif sort_option == "date_desc":
        base_queryset = base_queryset.order_by("-created_at")
    elif sort_option == "priority_asc":
        base_queryset = base_queryset.order_by(priority_case)
    elif sort_option == "priority_desc":
        base_queryset = base_queryset.order_by(-priority_case)

    return base_queryset


def handle_uploaded_file_in_chunks(ticket, file_obj, filename=None):
    """
    Save uploaded file to the ticket.
    Handles both file objects and bytes data.
    """

    filename = get_valid_filename(filename or "unnamed_attachment")
    attachment = TicketAttachment(ticket=ticket)

    try:
        if isinstance(file_obj, bytes):
            content = ContentFile(file_obj)
            attachment.file.save(filename, content, save=True)
        elif hasattr(file_obj, "read"):
            attachment.file.save(
                getattr(file_obj, "name", filename), file_obj, save=True
            )
        else:
            return
    except Exception as e:
        raise e

    attachment.save()
