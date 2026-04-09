import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
from app.logger import logger


def send_otp_email(to_email: str, otp: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Verification OTP"
        msg["From"]    = settings.EMAIL_ADDRESS
        msg["To"]      = to_email

        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
          <div style="background:#1e40af;padding:20px;text-align:center;border-radius:8px 8px 0 0">
            <h2 style="color:white;margin:0">Verification Code</h2>
          </div>
          <div style="padding:32px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
            <p style="color:#374151">Your one-time verification code is:</p>
            <div style="font-size:36px;font-weight:bold;letter-spacing:8px;
                        text-align:center;color:#1e40af;padding:16px;
                        background:#eff6ff;border-radius:8px">{otp}</div>
            <p style="color:#6b7280;font-size:13px;margin-top:20px">
              This code expires in <strong>10 minutes</strong>.<br>
              If you did not request this, please ignore this email.
            </p>
          </div>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.EMAIL_ADDRESS, settings.EMAIL_PASSWORD)
            server.sendmail(settings.EMAIL_ADDRESS, to_email, msg.as_string())

        logger.info(f"OTP email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send OTP email to {to_email}: {e}")
        return False
