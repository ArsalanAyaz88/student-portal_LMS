# File location: src/app/utils/email.py

import os
import smtplib
import logging
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env at module import 
load_dotenv()

# Read SMTP settings directly from environment
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Temporary debug prints - REMOVE AFTER DEBUGGING
print(f"DEBUG: SMTP_USER loaded: {SMTP_USER}")
print(f"DEBUG: SMTP_PASSWORD loaded: {'*' * len(SMTP_PASSWORD) if SMTP_PASSWORD else None}")




def send_enrollment_approved_email(to_email: str, course_title: str, expiration_date: str, days_remaining: int):
    """
    Send an enrollment approval notification email using Gmail SMTP server.
    Args:
        to_email (str): Recipient's email address
        course_title (str): Title of the course
        expiration_date (str): Date when access expires
        days_remaining (int): Number of days access is valid
    """
    try:
        subject = f"✅ Enrollment Approved - {course_title}"
        body = f"""
        <html>
        <body style='font-family: Arial, sans-serif; color: #333;'>
            <div style='max-width: 650px; margin: 0 auto; padding: 20px; background-color: #f4f7fc; border-radius: 8px; border: 1px solid #e1e5eb;'>
                <div style='text-align: center; padding: 30px 0;'>
                    <img src="https://res.cloudinary.com/imagesahsan/image/upload/v1748352569/sabri_logo_ki5jkg.png" alt="Logo" style="max-width: 150px;">
                </div>
                <h2 style='color: #2c3e50; text-align: center;'>Congratulations! Your Enrollment is Approved</h2>
                <p style='font-size: 16px; text-align: center; color: #555;'>Hello,</p>
                <p style='font-size: 16px; color: #555;'>We are pleased to inform you that your enrollment for the course <strong>{course_title}</strong> has been <span style='color: green; font-weight: bold;'>approved</span>.</p>
                <p style='font-size: 16px; color: #555;'>You now have full access to the course content and resources.</p>

                <div style='background-color: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05); margin: 20px 0;'>
                    <p style='font-size: 18px; color: #333; font-weight: bold; text-align: center;'>Important Access Information</p>
                    <p style='font-size: 16px; text-align: center; color: #555;'>
                        <strong>Access valid until:</strong> <span style='color: #e74c3c;'>{expiration_date}</span><br>
                        <strong>Days remaining:</strong> <span style='color: #e74c3c;'>{days_remaining} days</span>
                    </p>
                </div>

                <p style='font-size: 16px; color: #555; text-align: center;'>We wish you a successful and enriching learning experience!</p>
                
                <hr style='border: none; border-top: 1px solid #ccc; margin: 30px 0;'>

                <p style='font-size: 14px; color: #999; text-align: center;'>
                    This is an automated message, please do not reply to this email.<br>
                    If you need any assistance, feel free to contact our support team.
                </p>

                <div style='text-align: center; margin-top: 30px;'>
                    <p style='font-size: 14px; color: #2c3e50;'>Powered by <strong>Sabiry Ultrasound Training Institute</strong></p>
                </div>
            </div>
        </body>
        </html>
        """
        msg = MIMEText(body, 'html')
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        logger.info(f"Attempting to send enrollment approval email to {to_email}")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        logger.info(f"Successfully sent enrollment approval email to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication Error: Invalid credentials")
        raise
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while sending enrollment approval email: {str(e)}")
        raise

def send_application_approved_email(to_email: str, course_title: str):
    """
    Send an email notifying the user that their application has been approved
    and they can now proceed with payment.

    Args:
        to_email (str): Recipient's email address
        course_title (str): Title of the course
    """
    try:
        subject = f"✅ Your Enrollement Application for {course_title} is Approved!"
        body = f"""
        <html>
        <body style='font-family: Arial, sans-serif; color: #333;'>
            <div style='max-width: 650px; margin: 0 auto; padding: 20px; background-color: #f4f7fc; border-radius: 8px; border: 1px solid #e1e5eb;'>
                <div style='text-align: center; padding: 30px 0;'>
                    <img src="https://res.cloudinary.com/imagesahsan/image/upload/v1748352569/sabri_logo_ki5jkg.png" alt="Logo" style="max-width: 150px;">
                </div>
                <h2 style='color: #2c3e50; text-align: center;'>Congratulations! You are Eligible to Enroll</h2>
                <p style='font-size: 16px; text-align: center; color: #555;'>Hello,</p>
                <p style='font-size: 16px; color: #555;'>We are pleased to inform you that your application for the course <strong>{course_title}</strong> has been <span style='color: green; font-weight: bold;'>approved</span>.</p>
                <p style='font-size: 16px; color: #555;'>To finalize your enrollment, please follow these steps:</p>
                <ol style='font-size: 16px; color: #555; text-align: left; max-width: 80%; margin: 20px auto;'>
                    <li>Log in to your student portal.</li>
                    <li>Navigate to the <strong>{course_title}</strong> courses page and select the course.</li>
                    <li>Submit your payment to gain full access.</li>
                </ol>

                <div style='text-align: center; margin: 30px 0;'>
                    <a href="https://www.sabiryultrasound.com/login" style='background-color: #007bff; color: #ffffff; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px;'>Login and Pay Now</a>
                </div>

                <p style='font-size: 16px; color: #555; text-align: center;'>We look forward to welcoming you to the course!</p>
                
                <hr style='border: none; border-top: 1px solid #ccc; margin: 30px 0;'>

                <p style='font-size: 14px; color: #999; text-align: center;'>
                    This is an automated message, please do not reply to this email.<br>
                    If you need any assistance, feel free to contact our support team.
                </p>

                <div style='text-align: center; margin-top: 30px;'>
                    <p style='font-size: 14px; color: #2c3e50;'>Powered by <strong>Sabiry Ultrasound Training Institute</strong></p>
                </div>
            </div>
        </body>
        </html>
        """
        msg = MIMEText(body, 'html')
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        logger.info(f"Attempting to send application approval email to {to_email}")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        logger.info(f"Successfully sent application approval email to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication Error: Invalid credentials")
        raise
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while sending application approval email: {str(e)}")
        raise

def send_enrollment_rejected_email(to_email: str, course_title: str, rejection_reason: str):
    """
    Send an enrollment rejection notification email using Gmail SMTP server.

    Args:
        to_email (str): Recipient's email address
        course_title (str): Title of the course
        rejection_reason (str): Reason for rejection
    """
    try:
        subject = f"❌ Enrollment Rejected - {course_title}"
        body = f"""
        <html>
        <body style='font-family: Arial, sans-serif; color: #333;'>
            <div style='max-width: 650px; margin: 0 auto; padding: 20px; background-color: #f4f7fc; border-radius: 8px; border: 1px solid #e1e5eb;'>
                <div style='text-align: center; padding: 30px 0;'>
                    <img src="https://res.cloudinary.com/imagesahsan/image/upload/v1748352569/sabri_logo_ki5jkg.png" alt="Logo" style="max-width: 150px;">
                </div>
                <h2 style='color: #2c3e50; text-align: center;'>Enrollment Status Update</h2>
                <p style='font-size: 16px; text-align: center; color: #555;'>Hello,</p>
                <p style='font-size: 16px; color: #555;'>We regret to inform you that your enrollment for the course <strong>{course_title}</strong> has been <span style='color: red; font-weight: bold;'>rejected</span>.</p>
                <div style='background-color: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05); margin: 20px 0;'>
                    <p style='font-size: 18px; color: #333; font-weight: bold; text-align: center;'>Reason for Rejection</p>
                    <p style='font-size: 16px; text-align: center; color: #555;'>
                        {rejection_reason}
                    </p>
                </div>
                <p style='font-size: 16px; color: #555; text-align: center;'>If you believe this is a mistake or have any questions, please contact our support team.</p>
                
                <hr style='border: none; border-top: 1px solid #ccc; margin: 30px 0;'>

                <p style='font-size: 14px; color: #999; text-align: center;'>
                    This is an automated message, please do not reply to this email.
                </p>

                <div style='text-align: center; margin-top: 30px;'>
                    <p style='font-size: 14px; color: #2c3e50;'>Powered by <strong>Sabiry Ultrasound Training Institute</strong></p>
                </div>
            </div>
        </body>
        </html>
        """
        msg = MIMEText(body, 'html')
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        logger.info(f"Attempting to send enrollment rejection email to {to_email}")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        logger.info(f"Successfully sent enrollment rejection email to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication Error: Invalid credentials")
        raise
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while sending enrollment rejection email: {str(e)}")
        raise

def send_reset_pin_email(to_email: str, pin: str):
    """
    Send a password reset PIN email using Gmail SMTP server.
    
    Args:
        to_email (str): Recipient's email address
        pin (str): The reset PIN to send
    """
    try:
        subject = "🔐 Your Password Reset PIN - Sabiry Ultrasound Training Institute"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7fc; margin: 0; padding: 20px;">
            <div style="max-width: 650px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 8px; border: 1px solid #e1e5eb; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);">
                <div style='text-align: center; padding: 20px 0;'>
                    <img src="https://res.cloudinary.com/imagesahsan/image/upload/v1748352569/sabri_logo_ki5jkg.png" alt="Logo" style="max-width: 150px;">
                </div>
                <h2 style="color: #2c3e50; text-align: center; margin-top: 20px;">Password Reset Request</h2>

                <p style="font-size: 16px; color: #555;">Hello,</p>

                <p style="font-size: 16px; color: #555;">We received a request to reset your password for the Sabiry Ultrasound Training Institute account.</p>

                <div style="background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px auto; text-align: center; width: fit-content;">
                    <p style="margin: 0; font-size: 28px; font-weight: bold; color: #343a40; letter-spacing: 5px;">
                        {pin}
                    </p>
                </div>

                <p style="font-size: 16px; color: #555; text-align: center;">This PIN will expire in <strong>15 minutes</strong>.</p>

                <p style="font-size: 16px; color: #555; margin-top: 20px;">If you did not request this password reset, please ignore this email or contact support if you have concerns.</p>

                <hr style='border: none; border-top: 1px solid #ccc; margin: 30px 0;'>

                <p style='font-size: 14px; color: #999; text-align: center;'>
                    This is an automated message, please do not reply to this email.<br>
                    For any assistance, please contact our support team.
                </p>

                <div style='text-align: center; margin-top: 20px;'>
                    <p style='font-size: 14px; color: #2c3e50;'>Powered by <strong>Sabiry Ultrasound Training Institute</strong></p>
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEText(body, 'html')
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email

        logger.info(f"Attempting to send email to {to_email}")
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()                      # identify ourselves
            server.starttls()                  # upgrade to TLS
            server.ehlo()                      # re-identify after TLS
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
            
        logger.info(f"Successfully sent email to {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication Error: Invalid credentials")
        raise
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while sending email: {str(e)}")
        raise
