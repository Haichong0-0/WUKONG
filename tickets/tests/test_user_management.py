from django.test import TestCase, Client
from django.urls import reverse
from tickets.models import User
from django.contrib.messages import get_messages
from django.contrib import messages
from django.test import TestCase
from django.urls import reverse
from tickets.forms import UserForm
from tickets.models import User
from tickets.tests.helpers import reverse_with_next


class ProfileUpdateViewTests(TestCase):
    """Test suite for the profile view."""

    fixtures = [
        "tickets/tests/fixtures/default_user.json",
        "tickets/tests/fixtures/other_users.json",
    ]

    def setUp(self):
        self.user = User.objects.get(username="@johndoe")
        self.url = reverse("profile")
        self.form_input = {
            "first_name": "John2",
            "last_name": "Doe2",
            "username": "@johndoe2",
            "email": "johndoe2@wukong.ac.uk",
        }

    def test_profile_url(self):
        self.assertEqual(self.url, "/profile/")

    def test_get_profile(self):
        self.client.login(username=self.user.username, password="Password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile.html")
        form = response.context["form"]
        self.assertTrue(isinstance(form, UserForm))
        self.assertEqual(form.instance, self.user)

    def test_get_profile_redirects_when_not_logged_in(self):
        redirect_url = reverse_with_next("log_in", self.url)
        response = self.client.get(self.url)
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_unsuccesful_profile_update(self):
        self.client.login(username=self.user.username, password="Password123")
        self.form_input["username"] = "BAD_USERNAME"
        before_count = User.objects.count()
        response = self.client.post(self.url, self.form_input)
        after_count = User.objects.count()
        self.assertEqual(after_count, before_count)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile.html")
        form = response.context["form"]
        self.assertTrue(isinstance(form, UserForm))
        self.assertTrue(form.is_bound)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "@johndoe")
        self.assertEqual(self.user.first_name, "John")
        self.assertEqual(self.user.last_name, "Doe")
        self.assertEqual(self.user.email, "johndoe@wukong.ac.uk")

    def test_unsuccessful_profile_update_due_to_duplicate_username(self):
        self.client.login(username=self.user.username, password="Password123")
        self.form_input["username"] = "@janedoe"
        before_count = User.objects.count()
        response = self.client.post(self.url, self.form_input)
        after_count = User.objects.count()
        self.assertEqual(after_count, before_count)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profile.html")
        form = response.context["form"]
        self.assertTrue(isinstance(form, UserForm))
        self.assertTrue(form.is_bound)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "@johndoe")
        self.assertEqual(self.user.first_name, "John")
        self.assertEqual(self.user.last_name, "Doe")
        self.assertEqual(self.user.email, "johndoe@wukong.ac.uk")

    def test_succesful_profile_update(self):
        self.client.login(username=self.user.username, password="Password123")
        before_count = User.objects.count()
        response = self.client.post(self.url, self.form_input, follow=True)
        after_count = User.objects.count()
        self.assertEqual(after_count, before_count)
        response_url = reverse("dashboard_student")
        self.assertRedirects(
            response, response_url, status_code=302, target_status_code=200
        )
        self.assertTemplateUsed(response, "dashboard/dashboard_student.html")
        messages_list = list(response.context["messages"])
        self.assertEqual(len(messages_list), 1)
        self.assertEqual(messages_list[0].level, messages.SUCCESS)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "@johndoe2")
        self.assertEqual(self.user.first_name, "John2")
        self.assertEqual(self.user.last_name, "Doe2")
        self.assertEqual(self.user.email, "johndoe2@wukong.ac.uk")

    def test_post_profile_redirects_when_not_logged_in(self):
        redirect_url = reverse_with_next("log_in", self.url)
        response = self.client.post(self.url, self.form_input)
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )


class GetUserRoleTests(TestCase):
    fixtures = [
        "tickets/tests/fixtures/default_user.json",
        "tickets/tests/fixtures/other_users.json",
    ]

    def setUp(self):
        self.program_officer = User.objects.get(username="@janedoe")  
        self.student = User.objects.get(username="@petrapickles")  
        self.specialist = User.objects.get(username="@peterpickles")  
        self.url = reverse("get_user_role")

    def test_get_user_role_program_officer(self):
        """Test that the role is correctly identified for a program officer."""
        self.client.login(
            username=self.program_officer.username, password="Password123"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"role": "program_officer"})

    def test_get_user_role_specialist(self):
        """Test that the role is correctly identified for a specialist."""
        self.client.login(username=self.specialist.username, password="Password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"role": "specialist"})

    def test_get_user_role_student(self):
        """Test that the role is correctly identified for a student."""
        self.client.login(username=self.student.username, password="Password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"role": "student"})

    def test_get_user_role_anonymous(self):
        """Test that anonymous users cannot access the role endpoint."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn(reverse("log_in"), response.url)

    def test_get_user_role_unknown(self):
        unknown_user = User.objects.create_user(
            username="@someone",
            password="Password123",
            role="random_role",  # not program_officer, specialist or student
        )
        self.client.login(username=unknown_user.username, password="Password123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"role": "unknown"})
