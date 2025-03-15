"""Forms for the tickets app."""
from django import forms
from django.contrib.auth import authenticate
from django.core.validators import RegexValidator

from .models import Ticket, TicketAttachment, User

"""
Forms for the tickets app.

This module defines several Django forms used for authentication, user management, and ticket handling in the application. 
It includes:

1. **LogInForm** - Handles user authentication via username and password.

2. **UserForm** - Allows users to update their profile information.

3. **PasswordForm** - Enables users to change their password.

4. **PasswordForm** - Enables users to change their password after authentication.

5. **SignUpForm** - Allows new users to sign up with necessary details and password validation.

6. **TicketForm** - Facilitates ticket creation and editing, allowing students to submit requests.

7. **MultipleFileInput & MultipleFileField** - Custom field and widget enabling multiple file uploads.

8. **TicketAttachmentForm** - Handles file attachments for tickets.

9. **ReturnTicketForm** - Allows users to provide reasons when returning a ticket.

10. **SupplementTicketForm** - Enables users to supplement additional information to an existing ticket.
Each form ensures data integrity, user validation, and proper interaction with the models.
"""

class LogInForm(forms.Form):
    
    """Form enabling registered users to log in using their username and password."""


    """Form enabling registered users to log in."""

    username = forms.CharField(label="Username")
    password = forms.CharField(label="Password", widget=forms.PasswordInput())

    def get_user(self):
        """Returns authenticated user if possible."""

        user = None
        if self.is_valid():
            username = self.cleaned_data.get('username')
            password = self.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
        return user


class UserForm(forms.ModelForm):
    """Form to update user profiles."""


    """Form to allow users to update their profile details such as first name, last name, username, and email."""
    
    
    class Meta:
        """Form options."""
        
        """Specify model and fields to be included in the form."""


        model = User
        fields = ['first_name', 'last_name', 'username', 'email']

class NewPasswordMixin(forms.Form):
    """Form mixing for new_password and password_confirmation fields."""

    """Form allowing authenticated users to change their password."""


    new_password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(),
        validators=[RegexValidator(
            regex=r'^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9]).*$',
            message='Password must contain an uppercase character, a lowercase '
                    'character and a number'
            )]
    )
    password_confirmation = forms.CharField(label='Password confirmation', widget=forms.PasswordInput())

    def clean(self):
        """Form mixing for new_password and password_confirmation fields."""

        super().clean()
        new_password = self.cleaned_data.get('new_password')
        password_confirmation = self.cleaned_data.get('password_confirmation')
        if new_password != password_confirmation:
            self.add_error('password_confirmation', 'Confirmation does not match password.')


class PasswordForm(NewPasswordMixin):
    """Form enabling users to change their password."""

    password = forms.CharField(label='Current password', widget=forms.PasswordInput())

    def __init__(self, user=None, **kwargs):
        """Construct new form instance with a user instance."""
        
        super().__init__(**kwargs)
        self.user = user

    def clean(self):
        """Clean the data and generate messages for any errors."""

        super().clean()
        password = self.cleaned_data.get('password')
        if self.user is not None:
            user = authenticate(username=self.user.username, password=password)
        else:
            user = None
        if user is None:
            self.add_error('password', "Password is invalid")

    def save(self):
        """Save the user's new password."""

        new_password = self.cleaned_data['new_password']
        if self.user is not None:
            self.user.set_password(new_password)
            self.user.save()
        return self.user


class SignUpForm(NewPasswordMixin, forms.ModelForm):
    """Form enabling unregistered users to sign up."""

    """Form enabling new users to sign up and create an account."""
    class Meta:
        """Form options."""

        model = User
        fields = ['first_name', 'last_name', 'username', 'email']

    def save(self):
        """Create a new user."""

        super().save(commit=False)
        user = User.objects.create_user(
            self.cleaned_data.get('username'),
            first_name=self.cleaned_data.get('first_name'),
            last_name=self.cleaned_data.get('last_name'),
            email=self.cleaned_data.get('email'),
            password=self.cleaned_data.get('new_password'),
        )
        return user

# tickets/forms.py

class TicketForm(forms.ModelForm):
    """Form allowing users to create and update tickets."""
     
     
     
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'priority']  
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, user=None, **kwargs):

        super().__init__(*args, **kwargs)
        if user and user.is_student():

            self.fields.pop('priority', None)



class MultipleFileInput(forms.ClearableFileInput):
    
    """Custom file input widget that allows multiple file uploads."""
    
    
    allow_multiple_selected = True

##
class MultipleFileField(forms.FileField):
    """Custom file field allowing multiple file uploads."""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

## MultipleFileField is a custom field that allows multiple files to be uploaded at once.

class TicketAttachmentForm(forms.ModelForm):
    """Form for handling ticket attachments."""
     
     
    
    file = MultipleFileField()
    
    ## The Meta class is used to define the model and fields that the form will use.
    class Meta:
        model = TicketAttachment
        fields = ['file']


# The ReturnTicketForm form is used to create a form for returning a ticket.
class ReturnTicketForm(forms.Form):
    return_reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter reason for returning'}),
        label="Reason for Returning",
        required=True
    )

# The SupplementTicketForm form is used to create a form for supplementing a ticket.
class SupplementTicketForm(forms.Form):
    supplement_info = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter additional information'}),
        label="Supplement Information",
        required=True
    )