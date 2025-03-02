from django.urls import reverse
from with_asserts.mixin import AssertHTMLMixin

def reverse_with_next(url_name, next_url):
    """Extended version of reverse to generate URLs with redirects"""
    url = reverse(url_name)
    url += f"?next={next_url}"
    return url


class LogInTester:
    """Class support login in tests."""
 
    def _is_logged_in(self):
        """Returns True if a user is logged in.  False otherwise."""

        return '_auth_user_id' in self.client.session.keys()

class MenuTesterMixin(AssertHTMLMixin):
    """Class to extend tests with tools to check the presents of menu items."""

    menu_urls = [
        reverse('password'), reverse('profile'), reverse('log_out')
    ]

    def assert_menu(self, response):
        """Check that menu is present."""

        for url in self.menu_urls:
            with self.assertHTML(response, f'a[href="{url}"]'):
                pass

    def assert_no_menu(self, response):
        """Check that no menu is present."""
        
        for url in self.menu_urls:
            self.assertNotHTML(response, f'a[href="{url}"]')