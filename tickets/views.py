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
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, FormView, UpdateView
from tickets.forms import (LogInForm, PasswordForm, ReturnTicketForm,
                           SignUpForm, SupplementTicketForm,
                           TicketAttachmentForm, TicketForm, UserForm)
from tickets.helpers import login_prohibited
from tickets.models import (AITicketProcessing, Ticket, TicketActivity,
                            TicketAttachment, User)

from .ai_service import ai_process_ticket
from .models import Ticket, TicketActivity
from django.utils.decorators import method_decorator


def handle_uploaded_file_in_chunks(ticket, file_obj):
    
    attachment = TicketAttachment(ticket=ticket)
      
    attachment.file.save(file_obj.name, file_obj, save=True)
    
    attachment.save()
        
    

@login_required
def dashboard(request):
    current_user = request.user


    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    sort_option = request.GET.get('sort', '')


    priority_case = Case(
        When(priority='urgent', then=4),
        When(priority='high', then=3),
        When(priority='medium', then=2),
        When(priority='low', then=1),
        output_field=IntegerField()
    )


    if current_user.is_program_officer():

        if request.method == 'POST' and 'respond_ticket' in request.POST:
            ticket_id = request.POST.get("ticket_id")
            response_message = request.POST.get("response_message")
            ticket = get_object_or_404(Ticket, id=ticket_id)

 
            if ticket.answers:
                ticket.answers += "\n"
            else:
                ticket.answers = ""
            ticket.answers += f"Response by {current_user.username}: {response_message}"

            ticket.latest_action = 'responded'
            ticket.save()


            TicketActivity.objects.create(
                ticket=ticket,
                action='responded',
                action_by=current_user,
                comment=response_message
            )

            return redirect('dashboard')


        if request.method == 'POST' and 'redirect_ticket' in request.POST:
            ticket_id = request.POST.get('ticket_id')
            new_assignee_id = request.POST.get('new_assignee_id')
            ticket = get_object_or_404(Ticket, id=ticket_id)
            new_assignee = get_object_or_404(User, id=new_assignee_id)

            ticket.assigned_user = new_assignee
            ticket.latest_action = 'redirected'
            ticket.status = 'in_progress'  
            ticket.save()

            TicketActivity.objects.create(
                ticket=ticket,
                action='redirected',
                action_by=current_user,
                comment=f"Redirected to {new_assignee.username}"
            )

            return redirect('dashboard')

        
        tickets = Ticket.objects.all()


        if search_query:
            tickets = tickets.filter(
                Q(title__icontains=search_query) | Q(description__icontains=search_query)
            )


        if status_filter:
            tickets = tickets.filter(status=status_filter)


        if sort_option == 'date_asc':
            tickets = tickets.order_by('created_at')
        elif sort_option == 'date_desc':
            tickets = tickets.order_by('-created_at')
        elif sort_option == 'priority_asc':
            tickets = tickets.order_by(priority_case)
        elif sort_option == 'priority_desc':
            tickets = tickets.order_by(-priority_case)

        ticket_stats = User.objects.filter(role='specialists').annotate(
            ticket_count=Count('assigned_tickets')
        )

        return render(request, 'dashboard.html', {
            'user': current_user,
            'all_tickets': tickets,
            'ticket_stats': ticket_stats,
        })


    elif current_user.is_student():


        tickets = Ticket.objects.filter(creator=current_user)


        if search_query:
            tickets = tickets.filter(
                Q(title__icontains=search_query) | Q(description__icontains=search_query)
            )

        if status_filter:
            tickets = tickets.filter(status=status_filter)

        if sort_option == 'date_asc':
            tickets = tickets.order_by('created_at')
        elif sort_option == 'date_desc':
            tickets = tickets.order_by('-created_at')
        elif sort_option == 'priority_asc':
            tickets = tickets.order_by(priority_case)
        elif sort_option == 'priority_desc':
            tickets = tickets.order_by(-priority_case)

        return render(request, 'dashboard.html', {
            'user': current_user,
            'student_tickets': tickets,
        })


    elif current_user.is_specialist():

        if request.method == 'POST' and 'respond_ticket' in request.POST:
            ticket_id = request.POST.get("ticket_id")
            response_message = request.POST.get("response_message")
            ticket = get_object_or_404(Ticket, id=ticket_id)

            if ticket.answers:
                ticket.answers += "\n"
            else:
                ticket.answers = ""
            ticket.answers += f"Response by {current_user.username}: {response_message}"

            ticket.latest_action = 'responded'
            ticket.save()

            TicketActivity.objects.create(
                ticket=ticket,
                action='responded',
                action_by=current_user,
                comment=response_message
            )

            return redirect('dashboard')

        tickets = Ticket.objects.filter(assigned_user=current_user)


        if search_query:
            tickets = tickets.filter(
                Q(title__icontains=search_query) | Q(description__icontains=search_query)
            )

        if status_filter:
            tickets = tickets.filter(status=status_filter)

        if sort_option == 'date_asc':
            tickets = tickets.order_by('created_at')
        elif sort_option == 'date_desc':
            tickets = tickets.order_by('-created_at')
        elif sort_option == 'priority_asc':
            tickets = tickets.order_by(priority_case)
        elif sort_option == 'priority_desc':
            tickets = tickets.order_by(-priority_case)

        responded_tickets_list = []
        assigned_tickets_list = []
        for ticket in tickets:
            if ticket.answers:
                responded_tickets_list.append(ticket)
            else:
                assigned_tickets_list.append(ticket)
        return render(request, 'dashboard.html', {
            'user': current_user,
            'assigned_tickets': assigned_tickets_list,
            'responded_tickets': responded_tickets_list,
        })

    else:
        return render(request, 'dashboard.html', {
            'user': current_user,
            'message': "You do not have permission to view this page."
        })
        

@login_prohibited
def home(request):
    """Display the application's start/home screen."""

    return render(request, 'home.html')


class LoginProhibitedMixin:
    """Mixin that redirects when a user is logged in."""

    redirect_when_logged_in_url = None

    def dispatch(self, *args, **kwargs):
        """Redirect when logged in, or dispatch as normal otherwise."""
        if self.request.user.is_authenticated:
            return self.handle_already_logged_in(*args, **kwargs)
        return super().dispatch(*args, **kwargs)

    def handle_already_logged_in(self, *args, **kwargs):
        url = self.get_redirect_when_logged_in_url()
        return redirect(url)

    def get_redirect_when_logged_in_url(self):
        """Returns the url to redirect to when not logged in."""
        if self.redirect_when_logged_in_url is None:
            raise ImproperlyConfigured(
                "LoginProhibitedMixin requires either a value for "
                "'redirect_when_logged_in_url', or an implementation for "
                "'get_redirect_when_logged_in_url()'."
            )
        else:
            return self.redirect_when_logged_in_url


class LogInView(LoginProhibitedMixin, View):
    """Display login screen and handle user login."""

    http_method_names = ['get', 'post']
    redirect_when_logged_in_url = settings.REDIRECT_URL_WHEN_LOGGED_IN

    def get(self, request):
        """Display log in template."""

        self.next = request.GET.get('next') or ''
        return self.render()

    def post(self, request):
        """Handle log in attempt."""

        form = LogInForm(request.POST)
        self.next = request.POST.get('next') or settings.REDIRECT_URL_WHEN_LOGGED_IN
        user = form.get_user()
        if user is not None:
            login(request, user)
            return self.redirect_based_on_role(user)
        messages.add_message(request, messages.ERROR, "The credentials provided were invalid!")
        return self.render()

    def redirect_based_on_role(self, user):
        """Redirect user based on their role."""
        role_redirects = {
            'students': '/dashboard/students/',
            'program_officers': '/dashboard/officers/',
            'specialists': '/dashboard/specialists/',
        }
        if user.role in role_redirects:
            return redirect(role_redirects[user.role])
        messages.error(self.request, "Your account does not have a valid role.")
        return redirect('log_in')

    def render(self):
        """Render log in template with blank log in form."""

        form = LogInForm()
        return render(self.request, 'log_in.html', {'form': form, 'next': self.next})

@method_decorator(login_required, name='dispatch')
class StudentDashboardView(View):
    """Dashboard for students."""
    def get(self, request):
        return render(request, 'dashboard_students.html')

@method_decorator(login_required, name='dispatch')
class OfficerDashboardView(View):
    """Dashboard for program officers."""
    def get(self, request):
        return render(request, 'dashboard_officers.html')

@method_decorator(login_required, name='dispatch')
class SpecialistDashboardView(View):
    """Dashboard for specialists."""
    def get(self, request):
        return render(request, 'dashboard_specialists.html')

def log_out(request):
    """Log out the current user"""

    logout(request)
    return redirect('home')


class PasswordView(LoginRequiredMixin, FormView):
    """Display password change screen and handle password change requests."""

    template_name = 'password.html'
    form_class = PasswordForm

    def get_form_kwargs(self, **kwargs):
        """Pass the current user to the password change form."""

        kwargs = super().get_form_kwargs(**kwargs)
        kwargs.update({'user': self.request.user})
        return kwargs

    def form_valid(self, form):
        """Handle valid form by saving the new password."""

        form.save()
        login(self.request, self.request.user)
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect the user after successful password change."""

        messages.add_message(self.request, messages.SUCCESS, "Password updated!")
        return reverse('dashboard')


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Display user profile editing screen, and handle profile modifications."""

    model = UserForm
    template_name = "profile.html"
    form_class = UserForm

    def get_object(self):
        """Return the object (user) to be updated."""
        user = self.request.user
        return user

    def get_success_url(self):
        """Return redirect URL after successful update."""
        messages.add_message(self.request, messages.SUCCESS, "Profile updated!")
        return reverse(settings.REDIRECT_URL_WHEN_LOGGED_IN)


class SignUpView(LoginProhibitedMixin, FormView):
    form_class = SignUpForm
    template_name = "sign_up.html"
    redirect_when_logged_in_url = settings.REDIRECT_URL_WHEN_LOGGED_IN

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(settings.REDIRECT_URL_WHEN_LOGGED_IN)

class TicketListView(ListView):
    model = Ticket
    template_name = 'tickets/ticket_list.html'  
    context_object_name = 'tickets'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_student():
            messages.error(request, 'You do not have permission to view the ticket list.')
            return redirect('dashboard')  
        return super().dispatch(request, *args, **kwargs)

class TicketsTableView(View):
    def get(self, request):
        tickets = Ticket.objects.select_related('ai_processing', 'creator')
        return render(request, 'tickets_table.html', {'tickets': tickets})

class CreateTicketView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/create_ticket.html'
    success_url = '/tickets/'

    def dispatch(self, request, *args, **kwargs):

        if request.user.is_authenticated and not request.user.is_student():
            messages.error(request, 'Only students can create tickets.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):

        ticket = form.save(commit=False)
        ticket.creator = self.request.user
        ticket.status = 'open'

        if self.request.user.is_student():
            ticket.priority = 'low'


        ticket.save()
        


        existing_ticket = Ticket.objects.filter(title=ticket.title, status='open').exclude(id=ticket.id).first()

        if existing_ticket:
            
            existing_ticket.description += (
                f"\n\nMerged with ticket ID: {ticket.id}. "
                f"New description: {ticket.description}"
            )
            existing_ticket.save()


            files = self.request.FILES.getlist('file')
            for f in files:
                handle_uploaded_file_in_chunks(existing_ticket, f)


            TicketActivity.objects.create(
                ticket=existing_ticket,
                action='merged',
                action_by=self.request.user,
                comment=f'Merged with ticket {ticket.id}'
            )


            ticket.delete()

            messages.success(self.request, f'Ticket merged with existing ticket {existing_ticket.id} successfully!')
            return redirect('ticket_detail', pk=existing_ticket.pk)

        else:
            files = self.request.FILES.getlist('file')
            for f in files:
                handle_uploaded_file_in_chunks(ticket, f)

            TicketActivity.objects.create(
                ticket=ticket,
                action='created',
                action_by=self.request.user
            )

            ai_process_ticket(ticket)

            messages.success(self.request, 'Query submitted successfully!')
            return redirect('ticket_detail', pk=ticket.pk)


class TicketDetailView(DetailView):
    model = Ticket
    template_name = 'tickets/ticket_detail.html'
    context_object_name = 'ticket'


@login_required
def close_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.user.is_student() and request.user == ticket.creator:
        ticket.status = 'closed'
        ticket.save()
        messages.success(request, 'Ticket closed successfully.')
    else:
        messages.error(request, 'You do not have permission to close this ticket.')
    return redirect('dashboard')

@login_required
def return_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not request.user.is_program_officer() or ticket.status != 'open':
        return redirect('ticket_list')

    if request.method == 'POST':
        form = ReturnTicketForm(request.POST)
        if form.is_valid():
            ticket.status = 'returned'
            ticket.return_reason = form.cleaned_data['return_reason']
            ticket.save()
            return redirect('ticket_list')
    else:
        form = ReturnTicketForm()

    return render(request, 'tickets/return_ticket.html', {'form': form, 'ticket': ticket})


@login_required
def supplement_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not request.user.is_student() or ticket.status != 'returned':
        return redirect('ticket_list')

    if request.user != ticket.creator:
        messages.error(request, "You do not have permission to modify this ticket.")
        return redirect("ticket_list")

    if request.method == 'POST':
        form = SupplementTicketForm(request.POST)
        if form.is_valid():
            ticket.description += "\n\nSupplement: " + form.cleaned_data['supplement_info']
            ticket.status = 'open'
            ticket.save()
            return redirect('ticket_list')
    else:
        form = SupplementTicketForm()

    return render(request, 'tickets/supplement_ticket.html', {'form': form, 'ticket': ticket})


@login_required
def respond_ticket_page(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.user != ticket.assigned_user and not request.user.is_program_officer():
        return redirect('dashboard')
    
    activities = TicketActivity.objects.filter(ticket=ticket).order_by('-action_time')
    formatted_activities = []
    for activity in activities:
        formatted_activities.append({
            'username': activity.action_by.username,
            'action': activity.get_action_display(),
            'action_time': date_format(activity.action_time, 'F j, Y, g:i a'),
            'comment': activity.comment or "No comments."
        })
    return render(request, 'respond_ticket_page.html', {
        'ticket': ticket,
        'activities': formatted_activities,
    })


@login_required
def respond_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    if request.user != ticket.assigned_user and not request.user.is_program_officer():
        return redirect('dashboard')
    
    activities = TicketActivity.objects.filter(ticket=ticket).order_by('-action_time')
    formatted_activities = []
    for activity in activities:
        formatted_activities.append({
            'username': activity.action_by.username,
            'action': activity.get_action_display(),
            'action_time': date_format(activity.action_time, 'F j, Y, g:i a'),
            'comment': activity.comment or "No comments."
        })
    if request.method == "POST" and "response_message" in request.POST:
        response_message = request.POST.get("response_message")
        if ticket.answers:
            ticket.answers += "\n"
        else:
            ticket.answers = ""
        ticket.answers += f"Response by {request.user.username}: {response_message}"
        
        ticket.status = 'in_progress'
        ticket.save()
        ticket_activity = TicketActivity.objects.create(
            ticket=ticket,
            action='responded',
            action_by=request.user,
            comment=response_message
        )
        ticket_activity.save()
        activities = TicketActivity.objects.filter(ticket=ticket).order_by('-action_time')
        formatted_activities = [{
            'username': activity.action_by.username,
            'action': activity.get_action_display(),
            'action_time': date_format(activity.action_time, 'F j, Y, g:i a'),
            'comment': activity.comment or "No comments."
        } for activity in activities]

        return JsonResponse({
            'success': True,
            'activities': formatted_activities,
            'answers': ticket.answers
        })
    return render(request, 'respond_ticket_page.html', {
        'ticket': ticket,
        'activities': formatted_activities,
    })
    
    

@login_required
def redirect_ticket_page(request, ticket_id):
    ticket = Ticket.objects.get(id=ticket_id)

    specialists = User.objects.filter(role='specialists') \
    .annotate(ticket_count=Count('assigned_tickets')) \
    .order_by('ticket_count')
    
    returned_specialist_list = []
    ticket_activity = TicketActivity.objects.filter(ticket=ticket, action='returned')
    for activity in ticket_activity:
        returned_specialist_list.append(activity.action_by) 
    specialists = [specialist for specialist in specialists if specialist not in returned_specialist_list]
    return render(request, 'redirect_ticket_page.html', {
        'ticket': ticket,
        'specialists': specialists,
    })


@login_required
@require_POST
def redirect_ticket(request, ticket_id):
    if not request.user.is_program_officer():
        return redirect('redirect_ticket_page', ticket_id=ticket_id)
    ticket = Ticket.objects.get(id=ticket_id)
    new_assignee_id = request.POST.get('new_assignee_id')
    if new_assignee_id:
        new_assignee = User.objects.get(id=new_assignee_id)
        ticket.assigned_user = new_assignee
        ticket.status = 'in_progress'  
        ticket.latest_action = 'redirected'
        ticket.save()

        ticket_activity = TicketActivity(
            ticket=ticket,
            action='redirected',
            action_by=request.user,
            action_time=timezone.now(),
            comment=f'Redirected to {new_assignee.full_name()}'
        )
        ticket_activity.save()

        updated_ticket_info = {
            'assigned_user': ticket.assigned_user.username if ticket.assigned_user else 'Unassigned',
            'status': ticket.status,
            'priority': ticket.priority,
            'assigned_department': ticket.assigned_department,
        }

        specialists = User.objects.filter(role='specialists') \
        .annotate(ticket_count=Count('assigned_tickets')) \
        .order_by('ticket_count')
        
        returned_specialist_list = []
        ticket_activity = TicketActivity.objects.filter(ticket=ticket, action='returned')
        for activity in ticket_activity:
            returned_specialist_list.append(activity.action_by) 

        specialists_info = [
            {
                'id': specialist.id,
                'full_name': specialist.full_name(),
                'ticket_count': specialist.ticket_count,
                'department_name': specialist.department.name if specialist.department else 'N/A'
            }
            for specialist in specialists if specialist not in returned_specialist_list
        ]
        return JsonResponse({'ticket_info': updated_ticket_info, 'specialists': specialists_info})

    return redirect('redirect_ticket_page', ticket_id=ticket_id)

@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.user != ticket.creator and request.user != ticket.assigned_user and not request.user.is_program_officer():
        return redirect('dashboard')
    activities = TicketActivity.objects.filter(ticket=ticket).order_by('-action_time')
    formatted_activities = []
    for activity in activities:
        formatted_activities.append({
            'username': activity.action_by.username,
            'action': activity.get_action_display(),
            'action_time': date_format(activity.action_time, 'F j, Y, g:i a'),
            'comment': activity.comment or "No comments."
        })
    return render(request, 'ticket_detail.html', {
        'ticket': ticket,
        'activities': formatted_activities,
    })

@login_required
def return_ticket_page(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.user != ticket.creator and request.user != ticket.assigned_user and not request.user.is_program_officer():
        return redirect('dashboard')
    activities = TicketActivity.objects.filter(ticket=ticket).order_by('-action_time')
    formatted_activities = []
    for activity in activities:
        formatted_activities.append({
            'username': activity.action_by.username,
            'action': activity.get_action_display(),
            'action_time': date_format(activity.action_time, 'F j, Y, g:i a'),
            'comment': activity.comment or "No comments."
        })
    return render(request, 'return_ticket_page.html', {
        'ticket': ticket,
        'activities': formatted_activities,
    })
    
@login_required
def return_ticket_specailist(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.user != ticket.creator and request.user != ticket.assigned_user and not request.user.is_program_officer():
        return redirect('dashboard')

    if request.method == 'POST' and 'return_reason' in request.POST:
        return_reason = request.POST.get('return_reason')
        ticket.status = 'returned'
        ticket.assigned_user = None
        ticket.return_reason = return_reason
        ticket_activity = TicketActivity(
            ticket=ticket,
            action='returned',
            action_by=request.user,
            action_time=timezone.now(),
            comment=return_reason
        )
        ticket_activity.save()
        ticket.save()
        return redirect('dashboard')
    return redirect('return_ticket_page', ticket_id=ticket_id)