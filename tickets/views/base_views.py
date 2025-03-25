from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, FormView, UpdateView
from tickets.forms import (
    LogInForm,
    PasswordForm,
    ReturnTicketForm,
    SupplementTicketForm,
    TicketAttachmentForm,
    TicketForm,
    UserForm,
)
from tickets.helpers import login_prohibited
from tickets.models import (
    AITicketProcessing,
    Ticket,
    TicketActivity,
    TicketAttachment,
    User,
)

from tickets.helpers import (
    handle_uploaded_file_in_chunks,
    send_ticket_confirmation_email,
)

from tickets.ai_service import ai_process_ticket, find_potential_tickets_to_merge

from tickets.models import Ticket, TicketActivity, Department, MergedTicket


@login_prohibited
def home(request):
    """Display the application's start/home screen."""

    return render(request, "home.html")


class TicketListView(ListView):
    """Displays a list of tickets depending on the user's role."""

    model = Ticket
    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"

    def get_queryset(self):
        user = self.request.user

        # Program officers can see all
        if user.is_program_officer():
            return Ticket.objects.all()

        # Specialists can only see tickets they edited
        else:
            return Ticket.objects.filter(
            Q(latest_editor=user) | Q(assigned_user=user)
        )


    def dispatch(self, request, *args, **kwargs):
        # Prevent students from accessing the general ticket list view
        if request.user.is_student():
            messages.error(
                request, "You do not have permission to view the ticket list."
            )
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)


class CreateTicketView(LoginRequiredMixin, CreateView):
    """
    View for students to create new tickets (queries).
    Attaches uploaded files, sends confirmation, and starts AI processing.
    """

    model = Ticket
    form_class = TicketForm
    template_name = "tickets/create_ticket.html"
    success_url = "/tickets/"

    def dispatch(self, request, *args, **kwargs):

        # if request.user.is_authenticated and not request.user.is_student():
        #     messages.error(request, "Only students can create tickets.")
        #     return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        # Pass user info to the form
        kwargs = super().get_form_kwargs()

        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Save the ticket and related files, notify, and return JSON response."""
        ticket = form.save(commit=False)
        ticket.creator = self.request.user
        ticket.status = "in_progress"

        ticket.priority = "low"

        ticket.save()

        # Save file attachments (if any)
        files = self.request.FILES.getlist("file")
        for f in files:
            handle_uploaded_file_in_chunks(ticket, f)

        # Log creation activity
        TicketActivity.objects.create(
            ticket=ticket, action="created", action_by=self.request.user
        )

        # Start AI processing logic
        ai_process_ticket(ticket)

        # Send confirmation email
        send_ticket_confirmation_email(ticket)

        # Return success JSON
        messages.success(self.request, "Query submitted successfully!")
        return JsonResponse(
            {
                "success": True,
                "redirect_url": reverse(
                    "ticket_detail", kwargs={"ticket_id": ticket.id}
                ),
            }
        )


@login_required
def ticket_detail(request, ticket_id):
    """
    Show the ticket detail page including its activity history and attachments.
    Permissions vary by role and assignment.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    attachments = ticket.attachments.order_by("uploaded_at")

    # List of activity log entries with formatted times
    activities = TicketActivity.objects.filter(ticket=ticket).order_by("-action_time")
    formatted_activities = [
        {
            "username": activity.action_by.username,
            "action": activity.get_action_display(),
            "action_time": date_format(activity.action_time, "F j, Y, g:i a"),
            "comment": activity.comment or "No comments.",
        }
        for activity in activities
    ]

    # Student submitted, staff returned to update
    if (
        not request.user.is_student()
        and ticket.status == "in_progress"
        and ticket.return_reason
    ):
        messages.warning(request, "This ticket is waiting for the student to update.")

    # Ticket is still being handled by staff
    if (
        request.user.is_student()
        and ticket.status == "in_progress"
        and (
            ticket.can_be_managed_by_program_officers
            or ticket.can_be_managed_by_specialist
        )
    ):
        messages.warning(request, "This ticket is waiting for the staff to process.")
    
    # Block access if user is unrelated to this ticket
    if (
        request.user != ticket.creator
        and request.user != ticket.latest_editor
        and not request.user.is_program_officer()
    ):
        return redirect("dashboard")

    return render(
        request,
        "tickets/ticket_detail.html",
        {
            "ticket": ticket,
            "activities": formatted_activities,
            "attachments": attachments,
        },
    )
