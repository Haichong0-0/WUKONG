"""Forms for the tickets app."""

from django import forms
from django.contrib.auth import authenticate
from django.core.validators import RegexValidator

from .models import Ticket, TicketAttachment, User


class LogInForm(forms.Form):


    username = forms.CharField(label="Username")
    password = forms.CharField(label="Password", widget=forms.PasswordInput())

    def get_user(self):
        ## The get_user method is used to authenticate the user based on the username and password provided.

        user = None
        if self.is_valid():
            username = self.cleaned_data.get("username")
            password = self.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
        return user


class UserForm(forms.ModelForm):


    class Meta:


        model = User
        fields = ["first_name", "last_name", "username", "email"]


class NewPasswordMixin(forms.Form):
    ## The NewPasswordMixin class is a mixin that contains the new_password and password_confirmation fields.
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(),
        validators=[
            RegexValidator(
                regex=r"^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9]).*$",
                message="Password must contain an uppercase character, a lowercase "
                "character and a number",
            )
        ],
    )
    password_confirmation = forms.CharField(
        label="New Password confirmation", widget=forms.PasswordInput()
    )

    def clean(self):


        super().clean()
        new_password = self.cleaned_data.get("new_password")
        password_confirmation = self.cleaned_data.get("password_confirmation")
        if new_password != password_confirmation:
            self.add_error(
                "password_confirmation", "Confirmation does not match password."
            )


class PasswordForm(NewPasswordMixin):
    ## The PasswordForm form is used to create a form for changing a user's password.
    password = forms.CharField(label="Previous password", widget=forms.PasswordInput())

    def __init__(self, user=None, **kwargs):


        super().__init__(**kwargs)
        self.user = user

    def clean(self):


        super().clean()
        password = self.cleaned_data.get("password")
        if self.user is not None:
            user = authenticate(username=self.user.username, password=password)
        else:
            user = None
        if user is None:
            self.add_error("password", "Password is invalid")

    def save(self):


        new_password = self.cleaned_data["new_password"]
        if self.user is not None:
            self.user.set_password(new_password)
            self.user.save()
        return self.user




class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "priority"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "priority": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):

        super().__init__(*args, **kwargs)
        if user and user.is_student():   

            self.fields.pop("priority", None)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


##
class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)


## MultipleFileField is a custom field that allows multiple files to be uploaded at once.


class TicketAttachmentForm(forms.ModelForm):
    file = MultipleFileField()

    ## The Meta class is used to define the model and fields that the form will use.
    class Meta:
        model = TicketAttachment
        fields = ["file"]


# The ReturnTicketForm form is used to create a form for returning a ticket.
class ReturnTicketForm(forms.Form):
    return_reason = forms.CharField(
        widget=forms.Textarea(
            attrs={"class": "form-control", "placeholder": "Enter reason for returning"}
        ),
        label="Reason for Returning",
        required=True,
    )


# The SupplementTicketForm form is used to create a form for supplementing a ticket.
class SupplementTicketForm(forms.Form):
    supplement_info = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "placeholder": "Enter additional information",
            }
        ),
        label="Supplement Information",
        required=True,
    )