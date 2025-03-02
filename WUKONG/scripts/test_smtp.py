import smtplib

smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_user = "wukonghelpdesk@gmail.com"
smtp_pass = "bynw apnb vmuu nmun"

try:
    server = smtplib.SMTP(smtp_host, smtp_port)
    server.starttls()
    server.login(smtp_user, smtp_pass)
    print("✅ SMTP Connection Successful!")
    server.quit()
except Exception as e:
    print(f"❌ SMTP Connection Failed: {e}")
