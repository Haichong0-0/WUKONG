from django.test import TestCase
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from tickets.models import Ticket, AITicketProcessing, MergedTicket
from tickets.ai_service import (
    classify_department,
    predict_priority,
    generate_ai_answer,
    ai_process_ticket,
    find_potential_tickets_to_merge,
    query_bedrock,
    client,
)
import json
from tickets.models import *
import importlib

class AITicketProcessingTests(TestCase):
    fixtures = [
        "tickets/tests/fixtures/default_user.json",
        "tickets/tests/fixtures/other_users.json",
    ]

    def setUp(self):
        self.student = User.objects.get(username="@johndoe")
        # Create a ticket to test with
        self.ticket = Ticket.objects.create(
            title="Test Ticket",
            description="I need help with my course registration.",
            status="in_progress",
            creator=self.student,
        )
        # Create a ticket in the same department to be fetched later
        self.ticket_2 = Ticket.objects.create(
            title="Second Ticket",
            description="Another issue related to course registration.",
            status="in_progress",
            creator=self.student,
        )
        # Create a ticket in a different department to ensure it's excluded
        self.ticket_3 = Ticket.objects.create(
            title="Third Ticket",
            description="An issue related to IT Support.",
            status="in_progress",
            creator=self.student,
        )
        # Create AITicketProcessing entries for the tickets
        AITicketProcessing.objects.create(ticket=self.ticket, ai_assigned_department="academic_support")
        AITicketProcessing.objects.create(ticket=self.ticket_2, ai_assigned_department="academic_support")
        AITicketProcessing.objects.create(ticket=self.ticket_3, ai_assigned_department="it_support")

    @patch("tickets.ai_service.query_bedrock")
    def test_fetch_open_tickets_with_same_department(self, mock_query_bedrock):
        # Ensure AI processing data exists for the current ticket
        ai_process_ticket(self.ticket)

        # Fetch open tickets in the same department (excluding the current ticket)
        ai_assigned_department = self.ticket.ai_processing.ai_assigned_department

        potential_tickets = Ticket.objects.filter(
            status="in_progress",
            ai_processing__ai_assigned_department=ai_assigned_department,
        ).exclude(id=self.ticket.id)

        self.assertIn(self.ticket_2, potential_tickets)
        self.assertNotIn(self.ticket_3, potential_tickets)

    @patch("tickets.ai_service.query_bedrock")
    def test_predict_priority(self, mock_query_bedrock):
        mock_query_bedrock.return_value = "High"
        
        priority = predict_priority(self.ticket.description)
        self.assertEqual(priority, "High")
        expected_prompt = f"""
    Predict the priority level for the following university student query: 
    {', '.join([d[0] for d in Ticket.PRIORITY_CHOICES])}.
    Return only the priority level.
    
    Query: {self.ticket.description}
    """
        mock_query_bedrock.assert_called_once_with(expected_prompt)

    @patch("tickets.ai_service.query_bedrock")
    def test_find_potential_tickets_to_merge(self, mock_query_bedrock):
        # Create additional tickets
        ticket_2 = Ticket.objects.create(
            title="Course Registration Issue",
            description="I am encountering problems with my course registration.",
            status="in_progress",
            creator=self.student,
        )
        ticket_3 = Ticket.objects.create(
            title="Unrelated Issue",
            description="I need help with my dormitory allocation.",
            status="in_progress",
            creator=self.student, 
        )

        # Mock responses for similarity checks
        mock_query_bedrock.side_effect = ["yes", "no"]

        similar_tickets = find_potential_tickets_to_merge(self.ticket)

        self.assertEqual(len(similar_tickets), 1)
        self.assertEqual(similar_tickets[0].id, self.ticket_2.id)

        merged_ticket = MergedTicket.objects.get(primary_ticket=self.ticket)
        self.assertIn(self.ticket_2, merged_ticket.suggested_merged_tickets.all())
        self.assertNotIn(ticket_3, merged_ticket.suggested_merged_tickets.all())

        mock_query_bedrock.assert_called()

    @patch("tickets.ai_service.client.invoke_model")
    def test_query_bedrock_failure(self, mock_invoke_model):
        """Test that a ClientError is handled gracefully."""
        mock_invoke_model.side_effect = ClientError(
            error_response={"Error": {"Code": "500", "Message": "Internal Server Error"}},
            operation_name="InvokeModel",
        )
        result = query_bedrock("Test input")
        self.assertEqual(result, "")  # Ensure an empty string is returned
        mock_invoke_model.assert_called_once()

    @patch("tickets.ai_service.client.invoke_model")
    def test_query_bedrock_success(self, mock_invoke_model):
        """Test that query_bedrock returns the expected result."""
        mock_response = MagicMock()
        mock_response["body"].read.return_value = json.dumps({"generation": "Success"})
        mock_invoke_model.return_value = mock_response

        result = query_bedrock("Test input")
        self.assertEqual(result, "Success")
        mock_invoke_model.assert_called_once()

    @patch("tickets.ai_service.query_bedrock")
    def test_find_potential_tickets_to_merge_no_similar_tickets(self, mock_query_bedrock):
        mock_query_bedrock.return_value = "No"

        result = find_potential_tickets_to_merge(self.ticket)

        self.assertEqual(result, [])

        merged_ticket = MergedTicket.objects.filter(primary_ticket=self.ticket).first()
        self.assertIsNone(merged_ticket)



class TicketMergingTests(TestCase):
    fixtures = [
        "tickets/tests/fixtures/default_user.json",
        "tickets/tests/fixtures/other_users.json",
    ]

    def setUp(self):
        self.student = User.objects.get(username="@johndoe")
        # Create tickets for testing
        self.ticket = Ticket.objects.create(
            title="Test Ticket 1",
            description="Issue with course registration.",
            status="in_progress",
            creator=self.student,
        )
        self.ticket_2 = Ticket.objects.create(
            title="Test Ticket 2",
            description="Similar issue with course registration.",
            status="in_progress",
            creator=self.student,
        )
        self.ticket_3 = Ticket.objects.create(
            title="Test Ticket 3",
            description="Unrelated issue with IT support.",
            status="in_progress",
            creator=self.student,
        )

        # Create AI processing data for these tickets
        ai_process_ticket(self.ticket)
        ai_process_ticket(self.ticket_2)
        ai_process_ticket(self.ticket_3)

    @patch("tickets.ai_service.query_bedrock")
    def test_compare_and_merge_tickets(self, mock_query_bedrock):
        mock_query_bedrock.side_effect = lambda prompt: "Yes" if "course registration" in prompt else "No"

        # Fetch open tickets in the same department and exclude the current ticket
        ai_assigned_department = self.ticket.ai_processing.ai_assigned_department
        potential_tickets = Ticket.objects.filter(
            status="in_progress",
            ai_processing__ai_assigned_department=ai_assigned_department,
        ).exclude(id=self.ticket.id)

        similar_tickets = []

        # Compare tickets
        for potential_ticket in potential_tickets:
            prompt = f"""
            Determine whether the following tickets should be merged. Consider their similarity.
            The current ticket: '{self.ticket.title}' - {self.ticket.description}
            The potential ticket: '{potential_ticket.title}' - {potential_ticket.description}
            Should these tickets be merged? Return "Yes" or "No".
            """

            result = mock_query_bedrock(prompt)

            if result.lower() == "yes":
                similar_tickets.append(potential_ticket)

        # Test if the correct tickets are identified for merging
        self.assertIn(self.ticket_2, similar_tickets)  
        self.assertNotIn(self.ticket_3, similar_tickets)

        # Check if a merged ticket entry is created for the primary ticket
        if similar_tickets:
            merged_ticket, created = MergedTicket.objects.get_or_create(primary_ticket=self.ticket)
            self.assertTrue(created, "MergedTicket should be created")
            self.assertEqual(merged_ticket.primary_ticket, self.ticket)

        # Check that no unnecessary merged tickets are created for non-similar tickets
        merged_ticket_non_similar = MergedTicket.objects.filter(primary_ticket=self.ticket_3)
        self.assertFalse(merged_ticket_non_similar.exists())

    @patch("tickets.ai_service.query_bedrock")
    def test_no_merge_for_dissimilar_tickets(self, mock_query_bedrock):
        mock_query_bedrock.return_value = "No"

        # Test when no tickets are similar
        ai_assigned_department = self.ticket.ai_processing.ai_assigned_department
        potential_tickets = Ticket.objects.filter(
            status="in_progress",
            ai_processing__ai_assigned_department=ai_assigned_department,
        ).exclude(id=self.ticket.id)

        similar_tickets = []

        # Compare tickets
        for potential_ticket in potential_tickets:
            prompt = f"""
            Determine whether the following tickets should be merged. Consider their similarity.
            The current ticket: '{self.ticket.title}' - {self.ticket.description}
            The potential ticket: '{potential_ticket.title}' - {potential_ticket.description}
            Should these tickets be merged? Return "Yes" or "No".
            """
            result = mock_query_bedrock(prompt)

            if result.lower() == "yes":
                similar_tickets.append(potential_ticket)

        self.assertEqual(len(similar_tickets), 0)

        merged_ticket = MergedTicket.objects.filter(primary_ticket=self.ticket)
        self.assertFalse(merged_ticket.exists())


class QueryBedrockTests(TestCase):

    @patch("tickets.ai_service.client.invoke_model")
    def test_query_bedrock_success(self, mock_invoke_model):
        # Mock a successful response from AWS Bedrock
        mock_response = MagicMock()
        mock_response["body"].read.return_value = json.dumps({"generation": "This is a test response."})
        mock_invoke_model.return_value = mock_response

        prompt = "Test prompt"
        response = query_bedrock(prompt)

        self.assertEqual(response, "This is a test response.")
        mock_invoke_model.assert_called_once()

    @patch("tickets.ai_service.client.invoke_model")
    def test_query_bedrock_client_error(self, mock_invoke_model):
        # Mock a ClientError from AWS Bedrock
        mock_invoke_model.side_effect = ClientError(
            error_response={"Error": {"Code": "500", "Message": "Internal Server Error"}},
            operation_name="InvokeModel"
        )

        prompt = "Test prompt"
        response = query_bedrock(prompt)

        self.assertEqual(response, "")
        mock_invoke_model.assert_called_once()

    @patch("tickets.ai_service.client.invoke_model")
    def test_query_bedrock_unexpected_error(self, mock_invoke_model):
        # Mock an unexpected error from AWS Bedrock
        mock_invoke_model.side_effect = Exception("Unexpected error")

        prompt = "Test prompt"
        response = query_bedrock(prompt)

        self.assertEqual(response, "")
        mock_invoke_model.assert_called_once()


class AWSClientInitializationTests(TestCase):
    @patch("tickets.ai_service.boto3.client")
    def test_aws_client_initialization_failure(self, mock_boto_client):
        # Simulate an exception being raised during client initialization
        mock_boto_client.side_effect = Exception("Initialization error")

        with self.assertRaises(RuntimeError) as context:
            import tickets.ai_service
            importlib.reload(tickets.ai_service)

        self.assertIn("Error initializing AWS Bedrock client: Initialization error", str(context.exception))
