import logging
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import escape
from django.views.decorators.http import require_POST
from tickets.ai_service import (
    ai_process_ticket,
    classify_department,
    find_potential_tickets_to_merge,
)
from tickets.forms import ReturnTicketForm, SupplementTicketForm, TicketForm
from tickets.helpers import (
    send_ticket_confirmation_email,
    send_updated_notification_email,
    send_response_notification_email,
    send_notification_email_to_specialist,
    send_updated_notification_email_to_specialist_or_program_officer,
)
from tickets.models import (
    DailyTicketClosureReport,
    Department,
    MergedTicket,
    Ticket,
    TicketActivity,
    TicketAttachment,
    User,
)

logger = logging.getLogger(__name__)


@login_required
def close_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    #only student should use this function
    if request.user.is_student() and request.user == ticket.creator:
        ticket.status = "closed"
        ticket.can_be_managed_by_program_officers = False
        ticket.can_be_managed_by_specialist = False
        ticket.program_officer_resolved = True
        ticket.specialist_resolved = True
        ticket.save()

        TicketActivity.objects.create(
            ticket=ticket,
            action="closed_manually",
            action_by=request.user,
            action_time=timezone.now(),
            comment="Ticket closed manually by the student.",
        )

        # Update or create DailyTicketClosureReport for the department
        today = timezone.now().date()
        try:
            report, created = DailyTicketClosureReport.objects.get_or_create(
                date=today,
                department=ticket.assigned_department,
                defaults={
                    "closed_by_inactivity": 0,
                    "closed_by_inactivity": 0,
                    "closed_manually": 0,
                },
            )
            report.closed_manually += 1
            report.save()
        except Exception as e:
            messages.error(request, "An error occurred while closing the ticket.")
            return redirect("dashboard")

        messages.success(request, "Ticket closed successfully.")
    else:
        messages.error(request, "You do not have permission to close this ticket.")
    return redirect("dashboard")


@login_required
def return_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if (
        not (request.user.is_specialist() or request.user.is_program_officer())
        or ticket.status != "in_progress"
    ):
        return redirect("ticket_detail", ticket_id=ticket_id)

    student_email = ticket.creator.email
    ticket_title = ticket.title

    #return ticket to student
    if request.method == "POST":
        form = ReturnTicketForm(request.POST)
        if form.is_valid():
            ticket.status = "in_progress"
            return_reason = form.cleaned_data["return_reason"]
            ticket.return_reason = return_reason
            ticket.latest_action = "status_updated"
            ticket.assigned_user = ticket.creator
            ticket.latest_editor = request.user
            ticket.can_be_managed_by_specialist = False
            ticket.can_be_managed_by_program_officers = False
            ticket.program_officer_resolved = False
            ticket.specialist_resolved = False
            ticket.need_student_update = True
            ticket.save()

            ticket.refresh_from_db()

            send_updated_notification_email(
                student_email, ticket_title, ticket.return_reason, ticket_id
            )

            TicketActivity.objects.create(
                ticket=ticket,
                action="returned",
                action_by=request.user,
                action_time=timezone.now(),
                comment=f"Return to student : {ticket.creator.full_name()}",
            )

            return redirect("ticket_detail", ticket_id=ticket_id)

    else:
        form = ReturnTicketForm()

    return render(
        request, "tickets/ticket_detail.html", {"form": form, "ticket": ticket}
    )


@login_required
def redirect_ticket(request, ticket_id):

    if not request.user.is_program_officer():
        return JsonResponse({"error": "Unauthorized"}, status=403)

    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.method == "GET":
        specialists = get_specialists(ticket)
        return JsonResponse({"specialists": specialists})

    new_assignee_id = request.POST.get("new_assignee_id")
    #if ticket was created when the bedrock was down, error will happen here
    try:
        ai_assigned_department = classify_department(ticket.description)
        ticket.assigned_department = ai_assigned_department
        ticket.save()
    except Exception as e:
        ai_assigned_department = ticket.assigned_department or "it_support"
        ticket.assigned_department = ai_assigned_department
        ticket.save()


    if new_assignee_id == "ai":
        ticket.assigned_user = None
        ticket.status = "in_progress"
        ticket.latest_action = "redirected"
        #access modifier
        ticket.can_be_managed_by_program_officers = False
        ticket.can_be_managed_by_specialist = True
        ticket.program_officer_resolved = False
        ticket.save()

        TicketActivity.objects.create(
            ticket=ticket,
            action="redirected",
            action_by=request.user,
            action_time=timezone.now(),
            comment=f"Redirected to General Enquiry (AI recommended)",
        )
        messages.warning(request, f"Ticket still need you to reponse, AI recommended.")
        return JsonResponse(
            {
                "success": True,
                "redirect_url": reverse(
                    "ticket_detail", kwargs={"ticket_id": ticket.id}
                ),
            }
        )
    try:
        new_assignee = User.objects.get(id=new_assignee_id)
        ticket.assigned_user = new_assignee
        ticket.assigned_department = new_assignee.department.name
        ticket.status = "in_progress"
        ticket.latest_action = "redirected"
        ticket.can_be_managed_by_specialist = True
        ticket.can_be_managed_by_program_officers = False
        ticket.program_officer_resolved = True
        ticket.save()

        send_notification_email_to_specialist(
            specialist_email=new_assignee.email,
            ticket_title=ticket.title,
            ticket_id=ticket.id,
            student_email=ticket.creator.email,
            response_message=ticket.description,
        )

        TicketActivity.objects.create(
            ticket=ticket,
            action="redirected",
            action_by=request.user,
            action_time=timezone.now(),
            comment=f"Redirected to {new_assignee.username}",
        )

        open_tickets_count = Ticket.objects.filter(
            assigned_user=new_assignee, status="in_progress"
        ).count()

        new_assignee.open_tickets = open_tickets_count

        messages.success(
            request, f"Ticket successfully redirected to {new_assignee.username}!"
        )
        return JsonResponse(
            {
                "success": True,
                "redirect_url": reverse(
                    "ticket_detail", kwargs={"ticket_id": ticket.id}
                ),
            }
        )

    except User.DoesNotExist:
        return JsonResponse({"error": "Selected specialist does not exist"}, status=400)

    return JsonResponse({"error": "No specialist selected"}, status=400)


@login_required
@require_POST
def merge_ticket(request, ticket_id, potential_ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    potential_ticket = get_object_or_404(Ticket, id=potential_ticket_id)
    #merge ticket shouold be a singleton object associated with the primary ticket
    merged_ticket, created = MergedTicket.objects.get_or_create(primary_ticket=ticket)
    if potential_ticket in merged_ticket.approved_merged_tickets.all():
        merged_ticket.approved_merged_tickets.remove(potential_ticket)
        #change button displaed in page
        action = "unmerged"
        messages.success(request, "Tickets unmerged successfully.")
    else:
        merged_ticket.approved_merged_tickets.add(potential_ticket)
        numtickets = merged_ticket.approved_merged_tickets.count()
        action = "merged"
        messages.success(
            request,
            f'Success! There are currently {numtickets} tickets merged with the current ticket, by submitting a response to the current ticket your answer will be sent to all the merged tickets you selected. If you want to check or edit which tickets are merged, click the "Merge”button again.',
        )

    merged_ticket.save()
    potential_tickets = find_potential_tickets_to_merge(ticket)
    approved_merged_tickets = (
        merged_ticket.approved_merged_tickets.all() if merged_ticket else []
    )

    activities = (
        TicketActivity.objects.filter(ticket=ticket)
        .select_related("action_by")
        .order_by("-action_time")[:20]
    )

    actions = ["respond_ticket", "return_to_student", "redirect_ticket", "merge_ticket"]
    specialists = get_specialists(ticket)

    return render(
        request,
        "tickets/manage_tickets_page_for_program_officer.html",
        {
            "ticket": ticket,
            "actions": actions,
            "activities": activities,
            "specialists": specialists,
            "potential_tickets": potential_tickets,
            "approved_merged_tickets": approved_merged_tickets,
        },
    )


@login_required
def respond_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.user != ticket.assigned_user and not request.user.is_program_officer():
        return redirect("dashboard")

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

    if request.method == "POST" and "response_message" in request.POST:
        response_message = request.POST.get("response_message")
        merged_ticket = MergedTicket.objects.filter(primary_ticket=ticket).first()
        if merged_ticket and len(merged_ticket.approved_merged_tickets.all()) > 0:
            #reply to all merged tickets
            for approved_ticket in merged_ticket.approved_merged_tickets.all():
                approved_ticket.answers = (
                    approved_ticket.answers or ""
                ) + f"\nResponse by {request.user.full_name()}: {response_message}"
            approved_ticket.status = "in_progress"
            approved_ticket.save()
            send_response_notification_email(
                student_email=approved_ticket.creator.email,
                ticket_title=approved_ticket.title,
                response_message=approved_ticket.answers,
                ticket_id=approved_ticket.id,
            )
            TicketActivity.objects.create(
                ticket=approved_ticket,
                action="responded",
                action_by=request.user,
                comment=response_message,
            )

        ticket.answers = (
            ticket.answers or ""
        ) + f"\nResponse by {request.user.full_name()}: {response_message}"
        ticket.status = "in_progress"
        ticket.save()
        TicketActivity.objects.create(
            ticket=ticket,
            action="responded",
            action_by=request.user,
            comment=response_message,
        )
    messages.success(request, "Response sent successfully.")
    ticket.status = "in_progress"
    ticket.program_officer_resolved = request.user.is_program_officer()
    ticket.specialist_resolved = request.user.is_specialist()
    ticket.save()
    send_response_notification_email(
        student_email=ticket.creator.email,
        ticket_title=ticket.title,
        response_message=response_message,
        ticket_id=ticket.id,
    )

    return render(
        request,
        "tickets/ticket_detail.html",
        {"ticket": ticket, "activities": formatted_activities},
    )


@login_required
def update_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.user != ticket.creator:
        #only student can and program officer can eidt ticket
        messages.error(request, "You do not have permission to modify this ticket.")
        return redirect("dashboard")

    if request.method == "POST" and "update_message" in request.POST:
        update_message = escape(request.POST.get("update_message"))
        ticket.description += f"\n\nAdded Information:\n{update_message}"
        ticket.status = "in_progress"
        ticket.latest_action = "status_updated"
        assigned_user = ticket.latest_editor
        ticket.assigned_user = ticket.latest_editor
        ticket.latest_editor = request.user
        ticket.can_be_managed_by_specialist = True
        ticket.can_be_managed_by_program_officers = True
        if ticket.latest_editor.is_program_officer():
            ticket.program_officer_resolved = True
        if ticket.latest_editor.is_specialist():
            ticket.specialist_resolved = True
        ticket.need_student_update = False
        ticket.save()
        if assigned_user and assigned_user != request.user:
            send_updated_notification_email_to_specialist_or_program_officer(
                assigned_user.email,
                ticket.title,
                ticket.id,
                ticket.creator.email,
                update_message,
            )
        TicketActivity.objects.create(
            ticket=ticket,
            action="status_updated",
            action_by=request.user,
            comment=update_message,
        )

    return redirect("ticket_detail", ticket_id=ticket_id)


@login_required
def manage_ticket_page(request, ticket_id):
    ticket = get_object_or_404(
        Ticket.objects.select_related("creator", "assigned_user"), id=ticket_id
    )

    attachments = ticket.attachments.all().order_by("uploaded_at")

    user = request.user
    is_student = user.is_student()
    is_specialist = user.is_specialist()
    is_program_officer = user.is_program_officer()

    actions = []
    if is_student:
        actions.extend(["update_ticket", "close_ticket", "create_ticket"])
        if request.method == "POST":
            action = request.POST.get("action_type")
            if action == "update_ticket":
                return update_ticket(request, ticket_id=ticket.id)
            elif action == "close_ticket":
                return close_ticket(request, ticket_id=ticket.id)

        return render(
            request,
            "tickets/manage_tickets_page_for_student.html",
            {
                "ticket": ticket,
                "actions": actions,
                "attachments": attachments,
            },
        )

    if is_specialist:
        actions.extend(["respond_ticket", "return_ticket"])
        if request.method == "POST":
            action = request.POST.get("action_type")
            if action == "respond_ticket":
                return respond_ticket(request, ticket_id)
            elif action == "return_to_student":
                return return_ticket(request, ticket_id=ticket.id)

        activities = (
            TicketActivity.objects.filter(ticket=ticket)
            .select_related("action_by")
            .order_by("-action_time")[:20]
        )

        return render(
            request,
            "tickets/manage_tickets_page_for_specialist.html",
            {
                "ticket": ticket,
                "actions": actions,
                "attachments": attachments,
            },
        )

    if is_program_officer:
        actions.extend(
            ["respond_ticket", "return_to_student", "redirect_ticket", "merge_ticket"]
        )
        specialists = get_specialists(ticket)

        if request.method == "POST":
            action = request.POST.get("action_type")
            if action == "respond_ticket":
                return respond_ticket(request, ticket_id)
            elif action == "merge_ticket":
                potential_ticket_id = request.POST.get("potential_ticket_id")
                return merge_ticket(
                    request,
                    ticket_id=ticket.id,
                    potential_ticket_id=potential_ticket_id,
                )
            elif action == "return_to_student":
                return return_ticket(request, ticket_id=ticket.id)
            elif action == "redirect_ticket":
                return redirect_ticket(request, ticket_id=ticket.id)

        activities = (
            TicketActivity.objects.filter(ticket=ticket)
            .select_related("action_by")
            .order_by("-action_time")[:20]
        )
        potential_tickets = find_potential_tickets_to_merge(ticket)
        merged_ticket = MergedTicket.objects.filter(primary_ticket=ticket).first()
        approved_merged_tickets = (
            merged_ticket.approved_merged_tickets.all() if merged_ticket else []
        )

        return render(
            request,
            "tickets/manage_tickets_page_for_program_officer.html",
            {
                "ticket": ticket,
                "actions": actions,
                "activities": activities,
                "specialists": specialists,
                "potential_tickets": potential_tickets,
                "approved_merged_tickets": approved_merged_tickets,
                "attachments": attachments,
            },
        )

#do not modify this function
def get_specialists(ticket):
    try:
        ai_assigned_department = classify_department(ticket.description)
    except Exception as e:
        ai_assigned_department = ticket.assigned_department or "IT"

    specialists_qs = (
        User.objects.filter(role="specialists")
        .annotate(
            open_tickets=Coalesce(
                Count(
                    "assigned_tickets",
                    filter=Q(assigned_tickets__status="in_progress"),
                    distinct=True,
                ),
                Value(0),
            )
        )
        .select_related("department")
        .order_by("open_tickets")
    )
    specialists_list = list(specialists_qs)

    recommended_list = []
    non_recommended_list = []

    for spec in specialists_list:
        dept_name = spec.department.name if spec.department else ""
        if dept_name.lower().replace(" ", "_") == ai_assigned_department.lower():
            spec.username = f"{spec.username} (recommend)"
            recommended_list.append(spec)
        else:
            non_recommended_list.append(spec)

    if not recommended_list:
        dummy_spec = SimpleNamespace(
            id="ai",
            username=f"---------- {ai_assigned_department} (recommend) ----------",
            department=SimpleNamespace(name=ai_assigned_department),
            open_tickets=0,
            is_ai=True,
        )
        recommended_list = [dummy_spec]

    return [
        {
            "id": spec.id,
            "username": spec.username,
            "department_name": (
                getattr(spec.department, "name", "") if spec.department else ""
            ),
            "open_tickets": getattr(spec, "open_tickets", 0),
            "is_ai": getattr(spec, "is_ai", False),
        }
        for spec in recommended_list + non_recommended_list
    ]
