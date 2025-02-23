from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import FormView, UpdateView, CreateView
from django.views.generic.detail import DetailView
from django.urls import reverse
from tickets.forms import LogInForm, PasswordForm, UserForm, SignUpForm,TicketForm, TicketAttachmentForm, CustomLoginForm
from tickets.helpers import login_prohibited
from tickets.models import Ticket, TicketActivity, TicketAttachment, User
from django.http import HttpResponseForbidden

@login_required
def dashboard(request):
    user = request.user
    context = {
        'open_tickets': Ticket.objects.filter(creator=user, status='open'),
        'assigned_tickets': Ticket.objects.filter(assigned_user=user) if user.is_specialist() else None,
        'recent_activities': TicketActivity.objects.filter(
            Q(ticket__creator=user) | Q(ticket__assigned_user=user)
        ).order_by('-action_time')[:5]
    }

    if user.role == 'students':
        return redirect('student_dashboard')
    elif user.role == 'program_officers':
        return redirect('program_officer_dashboard')
    elif user.role == 'specialists':
        return redirect('specialist_dashboard')

    messages.error(request, "Your role is not recognized.")
    return redirect('log_in') 

@login_required
def student_dashboard_view(request):
    return render(request, 'students_dashboard.html', {'role': 'students'})

@login_required
def program_officer_dashboard_view(request):
    return render(request, 'program_officer_dashboard.html', {'role': 'program_officers'})

@login_required
def specialist_dashboard_view(request):
    return render(request, 'specialist_dashboard.html', {'role': 'specialists'})


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



class LogInView(View):
    """Display login screen and handle user login."""

    http_method_names = ['get', 'post']

    def get(self, request):
        """Display log in template."""
        return render(request, 'log_in.html', {'form': LogInForm(), 'next': request.GET.get('next', '')})

    def post(self, request):
        """Handle log in attempt."""
        form = LogInForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome, {user.get_full_name()}!")

                return redirect('dashboard')
            
            messages.error(request,"Invalid username or password.")

        return render(request, 'log_in.html', {'form': form})


def log_out(request):
    """Log out the current user"""

    logout(request)
    return redirect('log_in')


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
        return reverse('dashboard')


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

## This is the view for the ticket creation page
class CreateTicketView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/create_ticket.html'
    success_url = '/tickets/'

    def form_valid(self, form):
        ticket = form.save(commit=False)
        ticket.creator = self.request.user
        ticket.status = 'open'
        ticket.save()
        
        ## Upload multiple files
        files = self.request.FILES.getlist('file')
        for file in files:
            TicketAttachment.objects.create(ticket=ticket, file=file)
        
        TicketActivity.objects.create(
            ticket=ticket,
            action='created',
            action_by=self.request.user
        )
        
        # Here is your success message + redirect
        messages.success(self.request, 'Query submitted successfully!')
        return redirect('ticket_detail', pk=ticket.pk)


## This is the view for the ticket detail page
class TicketDetailView(DetailView):
    model = Ticket
    template_name = 'tickets/ticket_detail.html'
    context_object_name = 'ticket'
