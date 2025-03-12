from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import unittest

class DjangoSeleniumTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize WebDriver"""
        cls.driver = webdriver.Chrome()
        cls.driver.implicitly_wait(10)
        cls.driver.maximize_window()

    def test_home_page_loads(self):
        """Test if the Home page loads correctly"""
        driver = self.driver
        driver.get("http://127.0.0.1:8000/")

        # Check the page title
        new_title = driver.title
        print(f"New page title: {new_title}")

        # Ensure "WUKONG" is in the page title (case insensitive)
        self.assertIn("wukong", new_title.lower())

        # Ensure LOG IN button exists
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "LOG IN"))
        )
        login_button = driver.find_element(By.LINK_TEXT, "LOG IN")
        self.assertTrue(login_button.is_displayed(), "LOG IN button is missing")

    def test_css_loaded(self):
        """Test if CSS is loaded correctly"""
        driver = self.driver
        driver.get("http://127.0.0.1:8000/")

        # Ensure custom CSS is applied (check an element styled by custom.css)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "container-box"))
        )
        content_element = driver.find_element(By.CLASS_NAME, "container-box")
        self.assertTrue(content_element.is_displayed(), "CSS may not be applied correctly")

        # Get and print the color of the LOG IN button (check CSS styles)
        login_button = driver.find_element(By.LINK_TEXT, "LOG IN")
        color = login_button.value_of_css_property("color")
        print("LOG IN button color:", color)

    def test_login_page_loads(self):
        """Test if the Login page loads correctly"""
        driver = self.driver
        driver.get("http://127.0.0.1:8000/log_in/")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "login-btn"))
        )

        heading = driver.find_element(By.CLASS_NAME, "ticket-system")
        self.assertTrue(heading.is_displayed(), "Login page heading missing")

        print("✅ Login page loaded successfully!")


    def test_base_template_renders(self):
        """Test if base_login.html template renders correctly"""
        driver = self.driver
        driver.get("http://127.0.0.1:8000/log_in/")

        # Check if Bootstrap is loaded
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//link[contains(@href, 'bootstrap')]"))
        )
        bootstrap_css = driver.find_element(By.XPATH, "//link[contains(@href, 'bootstrap')]")
        self.assertTrue(bootstrap_css, "Bootstrap CSS is not loaded correctly")

    def test_login_button_redirects(self):
        """Test if clicking LOG IN button redirects to the login page"""
        driver = self.driver
        driver.get("http://127.0.0.1:8000/")

        # Click the LOG IN button
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "LOG IN"))
        )
        login_button.click()

        # Wait for the login page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )

        # Verify the URL is correct
        current_url = driver.current_url
        print(f"Redirected to: {current_url}")
        self.assertIn("log_in", current_url)

    @classmethod
    def tearDownClass(cls):
        """Close the browser after tests are completed"""
        cls.driver.quit()

if __name__ == "__main__":
    unittest.main()