"""Unit tests for the Deaprtment model."""
from django.core.exceptions import ValidationError
from django.test import TestCase
from tickets.models import Ticket, User, Department

class DepartmentModelTest(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="welfare",
            description="txt",
            responsible_roles="specialist"
        )
        return super().setUp()

    def test_ticket_creation(self):
        self.assertEqual(self.department.name, "welfare")
        self.assertEqual(self.department.description, "txt")
        self.assertEqual(self.department.responsible_roles, "specialist")

    def test_ticket_str(self):
        self.assertEqual(str(self.department), self.department.name)
