from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from tickets.helpers import get_filtered_tickets
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from tickets.models import Ticket, DailyTicketClosureReport,Department
from django.utils import timezone
from django.db.models import Min
from datetime import timedelta


@login_required
def dashboard_redirect(request):
    """Redirect user to the appropriate dashboard based on their role."""
    user = request.user

    if user.is_program_officer():
        return redirect("dashboard_program_officer")
    elif user.is_student():
        return redirect("dashboard_student")
    elif user.is_specialist():
        return redirect("dashboard_specialist")

    return redirect("home")  # 如果没有角色，回到首页或者显示错误信息


@login_required
def student_dashboard(request):

    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    sort_option = request.GET.get("sort", "")

    tickets = get_filtered_tickets(
        request.user,
        Ticket.objects.filter(creator=request.user),
        search_query,
        status_filter,
        sort_option,
    )
    return render(
        request, "dashboard/dashboard_student.html", {"student_tickets": tickets}
    )


@login_required
def program_officer_dashboard(request):
    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    sort_option = request.GET.get("sort", "")

    tickets = get_filtered_tickets(
        request.user,
        Ticket.objects.exclude(status="closed")
        .exclude(answers__isnull=False)
        .exclude(answers=""),
        search_query,
        status_filter,
        sort_option,
    )

    return render(
        request, "dashboard/dashboard_program_officer.html", {"all_tickets": tickets}
    )


@login_required
def specialist_dashboard(request):

    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    sort_option = request.GET.get("sort", "")

    tickets = get_filtered_tickets(
        request.user,
        Ticket.objects.filter(assigned_user=request.user),
        search_query,
        status_filter,
        sort_option,
    )
    return render(
        request, "dashboard/dashboard_specialist.html", {"assigned_tickets": tickets}
    )


@login_required
def visualize_ticket_data(request):
    today = timezone.now().date()
    first_day = DailyTicketClosureReport.objects.aggregate(Min('date'))['date__min']
    start_date = min(today - timedelta(days=7), first_day)

    # Ensure reports exist for each day in the past week
    for single_date in (start_date + timedelta(n) for n in range((today - start_date).days + 1)):
        for department in Department.objects.all():
            DailyTicketClosureReport.objects.get_or_create(
                date=single_date,
                department=department.name,
                defaults={"closed_by_inactivity": 0, "closed_manually": 0, "in_progress": 0},
            )

    reports = DailyTicketClosureReport.objects.filter(date__gte=start_date).order_by('-date')

    # Fill empty fields with 0
    for report in reports:
        if report.closed_by_inactivity is None:
            report.closed_by_inactivity = 0
        if report.closed_manually is None:
            report.closed_manually = 0
        if report.in_progress is None:
            report.in_progress = 0

    return render(request, 'visualize_ticket_data.html', {'reports': reports})