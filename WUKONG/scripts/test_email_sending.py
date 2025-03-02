import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Moves one level up
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Moves two levels up

# Manually set up Django settings before using them
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "query_hub.settings") 
django.setup()


from django.core.mail import send_mail
from django.conf import settings

send_mail(
    "Test Email",
    "This is a test email from Django.",
    settings.EMAIL_HOST_USER,
    ["wukonghelpdesk@gmail.com"],  
)

print("✅ Email sent successfully!")