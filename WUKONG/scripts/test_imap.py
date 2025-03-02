import imaplib

EMAIL_HOST = "imap.gmail.com"
EMAIL_PORT = 993
EMAIL_USER = "wukonghelpdesk@gmail.com"
EMAIL_PASS = "bynw apnb vmuu nmun"  # App Password

try:
    mail = imaplib.IMAP4_SSL(EMAIL_HOST, EMAIL_PORT)
    mail.login(EMAIL_USER, EMAIL_PASS)
    print("✅ IMAP Login Successful!")
    mail.logout()
except Exception as e:
    print(f"❌ IMAP Login Failed: {e}")
