"""Unit tests for the User model."""
from django.core.exceptions import ValidationError
from django.test import TestCase
from tickets.models import User,Department

class UserModelTestCase(TestCase):
    """Unit tests for the User model."""

    fixtures = [
        'tickets/tests/fixtures/default_user.json',
        'tickets/tests/fixtures/other_users.json'
    ]

    GRAVATAR_URL = "https://www.gravatar.com/avatar/363c1b0cd64dadffb867236a00e62986"

    def setUp(self):
        self.user = User.objects.get(username='@johndoe')
        self.departmentS = Department.objects.create(
            name="welfare",
            description="txt",
            responsible_roles="specialist"
        )
        self.user_with_department = User.objects.create_user(
            username="@userwithdepartment",
            first_name="User",
            last_name="WithDepartment",
            email="userwithdepartment@example.com",
            role="students",
            department=self.departmentS
        )
        self.user_without_department = User.objects.create_user(
            username="@userwithoutdepartment",
            first_name="User",
            last_name="WithoutDepartment",
            email="userwithoutdepartment@example.com",
            role="students",
            department=None
        )

    def test_valid_user(self):
        self._assert_user_is_valid()

    def test_username_cannot_be_blank(self):
        self.user.username = ''
        self._assert_user_is_invalid()

    def test_username_can_be_30_characters_long(self):
        self.user.username = '@' + 'x' * 29
        self._assert_user_is_valid()

    def test_username_cannot_be_over_30_characters_long(self):
        self.user.username = '@' + 'x' * 30
        self._assert_user_is_invalid()

    def test_username_must_be_unique(self):
        second_user = User.objects.get(username='@janedoe')
        self.user.username = second_user.username
        self._assert_user_is_invalid()

    def test_username_must_start_with_at_symbol(self):
        self.user.username = 'johndoe'
        self._assert_user_is_invalid()

    def test_username_must_contain_only_alphanumericals_after_at(self):
        self.user.username = '@john!doe'
        self._assert_user_is_invalid()

    def test_username_must_contain_at_least_3_alphanumericals_after_at(self):
        self.user.username = '@jo'
        self._assert_user_is_invalid()

    def test_username_may_contain_numbers(self):
        self.user.username = '@j0hndoe2'
        self._assert_user_is_valid()

    def test_username_must_contain_only_one_at(self):
        self.user.username = '@@johndoe'
        self._assert_user_is_invalid()


    def test_first_name_must_not_be_blank(self):
        self.user.first_name = ''
        self._assert_user_is_invalid()

    def test_first_name_need_not_be_unique(self):
        second_user = User.objects.get(username='@janedoe')
        self.user.first_name = second_user.first_name
        self._assert_user_is_valid()

    def test_first_name_may_contain_50_characters(self):
        self.user.first_name = 'x' * 50
        self._assert_user_is_valid()

    def test_first_name_must_not_contain_more_than_50_characters(self):
        self.user.first_name = 'x' * 51
        self._assert_user_is_invalid()


    def test_last_name_must_not_be_blank(self):
        self.user.last_name = ''
        self._assert_user_is_invalid()

    def test_last_name_need_not_be_unique(self):
        second_user = User.objects.get(username='@janedoe')
        self.user.last_name = second_user.last_name
        self._assert_user_is_valid()

    def test_last_name_may_contain_50_characters(self):
        self.user.last_name = 'x' * 50
        self._assert_user_is_valid()

    def test_last_name_must_not_contain_more_than_50_characters(self):
        self.user.last_name = 'x' * 51
        self._assert_user_is_invalid()


    def test_email_must_not_be_blank(self):
        self.user.email = ''
        self._assert_user_is_invalid()

    def test_email_must_be_unique(self):
        second_user = User.objects.get(username='@janedoe')
        self.user.email = second_user.email
        self._assert_user_is_invalid()

    def test_email_must_contain_username(self):
        self.user.email = '@example.org'
        self._assert_user_is_invalid()

    def test_email_must_contain_at_symbol(self):
        self.user.email = 'johndoe.example.org'
        self._assert_user_is_invalid()

    def test_email_must_contain_domain_name(self):
        self.user.email = 'johndoe@.org'
        self._assert_user_is_invalid()

    def test_email_must_contain_domain(self):
        self.user.email = 'johndoe@example'
        self._assert_user_is_invalid()

    def test_email_must_not_contain_more_than_one_at(self):
        self.user.email = 'johndoe@@example.org'
        self._assert_user_is_invalid()


    def test_full_name_must_be_correct(self):
        full_name = self.user.full_name()
        self.assertEqual(full_name, "John Doe")


    def test_default_gravatar(self):
        actual_gravatar_url = self.user.gravatar()
        expected_gravatar_url = self._gravatar_url(size=120)
        self.assertEqual(actual_gravatar_url, expected_gravatar_url)

    def test_custom_gravatar(self):
        actual_gravatar_url = self.user.gravatar(size=100)
        expected_gravatar_url = self._gravatar_url(size=100)
        self.assertEqual(actual_gravatar_url, expected_gravatar_url)

    def test_mini_gravatar(self):
        actual_gravatar_url = self.user.mini_gravatar()
        expected_gravatar_url = self._gravatar_url(size=60)
        self.assertEqual(actual_gravatar_url, expected_gravatar_url)

    def test_user_is_student(self):
        self.assertTrue(self.user.is_student())
    
    def test_user_is_program_officer(self):
        self.assertFalse(self.user.is_program_officer())
    
    def test_user_is_specialist(self):
        self.assertFalse(self.user.is_specialist())

    def test_user_str(self):
        self.assertTrue(str(self.user), f"{self.user.username} ({self.user.role}) - {self.user.department}" )

    def test_specialist_without_department(self):
        user = User.objects.create(
            username="@specialistuser",
            first_name="Specialist",
            last_name="User",
            email="specialistuser@example.com",
            role="specialists",
            department=None  # No department assigned
        )
        with self.assertRaises(ValidationError) as context:
            user.clean()  # This should raise a ValidationError
        self.assertIn("Specialists must have a department.", str(context.exception))

    def test_specialist_with_department(self):
        user = User.objects.create(
            username="@specialistuser",
            first_name="Specialist",
            last_name="User",
            email="specialistuser@example.com",
            role="specialists",
            department=self.departmentS# Department assigned
        )
        try:
            user.clean()  # This should not raise a ValidationError
        except ValidationError:
            self.fail("ValidationError raised unexpectedly!")

    def test_user_str_with_department(self):
        expected_str = f"{self.user_with_department.username} ({self.user_with_department.role}) - {self.user_with_department.department}"
        self.assertEqual(str(self.user_with_department), expected_str)

    def test_user_str_without_department(self):
        expected_str = f"{self.user_without_department.username} ({self.user_without_department.role})"
        self.assertEqual(str(self.user_without_department), expected_str)
    
    def _gravatar_url(self, size):
        gravatar_url = f"{UserModelTestCase.GRAVATAR_URL}?size={size}&default=mp"
        return gravatar_url


    def _assert_user_is_valid(self):
        try:
            self.user.full_clean()
        except (ValidationError):
            self.fail('Test user should be valid')

    def _assert_user_is_invalid(self):
        with self.assertRaises(ValidationError):
            self.user.full_clean()

    