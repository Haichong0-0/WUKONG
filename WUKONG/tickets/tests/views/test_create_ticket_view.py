import os
from django.test import TestCase
from django.urls import reverse
from django.contrib import messages
from django.core.files.uploadedfile import SimpleUploadedFile
from tickets.models import User, Ticket, TicketAttachment
from tickets.forms import TicketForm

class CreateTicketViewTestCase(TestCase):
    """Tests for the CreateTicketView."""

    fixtures = [
        'tickets/tests/fixtures/default_user.json',
        # 'tickets/tests/fixtures/other_users.json'
    ]

    def setUp(self):
        """Set up test data for each test."""
        self.user = User.objects.get(username='@johndoe')

        self.url = reverse('create_ticket')

        self.form_input = {
            'title': 'My Test Ticket',
            'description': 'Hello, I have an issue with my coursework.',
            'priority': 'medium',
            'assigned_department': 'academic_support'
        }

    def test_create_ticket_url(self):
        """Check that the URL name matches the correct path."""
        self.assertEqual(self.url, '/tickets/create/')

    def test_redirect_if_not_logged_in(self):
        """
        If a user is not logged in, accessing the create ticket page
        should redirect them to the login screen.
        """
        response = self.client.get(self.url)
        login_url = reverse('log_in')
        self.assertRedirects(
            response,
            f'{login_url}?next={self.url}',
            status_code=302,
            target_status_code=200
        )

    def test_get_create_ticket_view_when_logged_in(self):
        """Logged-in user should be able to see the create ticket form."""
        self.client.login(username=self.user.username, password='Password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tickets/create_ticket.html')
        form = response.context['form']
        self.assertTrue(isinstance(form, TicketForm))
        self.assertFalse(form.is_bound) 

    def test_post_create_ticket_valid_data(self):
        """
        Submitting valid data should create a new ticket,
        and redirect to the ticket detail page.
        """
        self.client.login(username=self.user.username, password='Password123')
        before_count = Ticket.objects.count()

        response = self.client.post(self.url, self.form_input, follow=True)
        after_count = Ticket.objects.count()
        self.assertEqual(after_count, before_count + 1)


        ticket = Ticket.objects.latest('created_at')
        self.assertEqual(ticket.title, self.form_input['title'])
        self.assertEqual(ticket.description, self.form_input['description'])
        self.assertEqual(ticket.priority, self.form_input['priority'])
        self.assertEqual(ticket.assigned_department, self.form_input['assigned_department'])
        self.assertEqual(ticket.creator, self.user)


        expected_redirect_url = reverse('ticket_detail', kwargs={'pk': ticket.pk})
        self.assertRedirects(response, expected_redirect_url, status_code=302, target_status_code=200)


        messages_list = list(response.context['messages'])
        self.assertEqual(len(messages_list), 1)  # "Query submitted successfully!"
        self.assertEqual(messages_list[0].level, messages.SUCCESS)

    def test_post_create_ticket_with_attachments(self):
        """
        If the user uploads one or more attachments,
        they should be saved and linked to the newly created ticket.
        """
        self.client.login(username=self.user.username, password='Password123')

        file1 = SimpleUploadedFile("test1.txt", b"file1 content", content_type='text/plain')
        file2 = SimpleUploadedFile("test2.txt", b"file2 content", content_type='text/plain')

        data = {
            'title': 'My Test Ticket',
            'description': 'Hello, I have an issue with my coursework.',
            'priority': 'medium',
            'assigned_department': 'academic_support',
            'file': [file1, file2]
        }

        response = self.client.post(self.url, data, follow=True)

        ticket = Ticket.objects.latest('created_at')
        attachments = TicketAttachment.objects.filter(ticket=ticket)
        self.assertEqual(attachments.count(), 2)

        filenames = [attachment.file.name for attachment in attachments]
        base_names = [os.path.basename(name) for name in filenames]

        self.assertTrue(any('test1' in bn for bn in base_names))
        self.assertTrue(any('test2' in bn for bn in base_names))

        expected_redirect_url = reverse('ticket_detail', kwargs={'pk': ticket.pk})
        self.assertRedirects(response, expected_redirect_url, status_code=302, target_status_code=200)
        messages_list = list(response.context['messages'])
        self.assertEqual(len(messages_list), 1)
        self.assertEqual(messages_list[0].level, messages.SUCCESS)

    def test_post_create_ticket_invalid_data(self):
        """
        If the form data is invalid, stay on the same page
        and do not create a new ticket.
        """
        self.client.login(username=self.user.username, password='Password123')


        invalid_input = {
            'title': '',
            'description': 'No Title Provided',
            'priority': 'medium',
            'assigned_department': 'academic_support'
        }
        before_count = Ticket.objects.count()
        response = self.client.post(self.url, invalid_input)
        after_count = Ticket.objects.count()
        self.assertEqual(after_count, before_count)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tickets/create_ticket.html')
        form = response.context['form']
        self.assertTrue(isinstance(form, TicketForm))
        self.assertTrue(form.is_bound)
        self.assertFalse(form.is_valid())

        messages_list = list(response.context['messages'])
        self.assertEqual(len(messages_list), 0)
