import random
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings
from app.logger import logger


def generate_otp() -> str:
    """Generate a 6-digit OTP code"""
    return str(random.randint(100000, 999999))


async def send_otp_email(email: str, otp: str, is_reset: bool = False) -> bool:
    """
    Send OTP verification email via Gmail SMTP
    
    Args:
        email: Recipient email address
        otp: 6-digit OTP code
        is_reset: Whether this is for password reset (True) or registration (False)
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    settings = get_settings()
    
    # Customize content based on type
    if is_reset:
        subject = "Password Reset Code - Relact"
        title = "Password Reset"
        message_text = "You requested a password reset. Use the code below to reset your password:"
    else:
        subject = "Email Verification Code - Relact"
        title = "Email Verification"
        message_text = "Thank you for registering with Relact! Please use the following verification code to complete your registration:"

    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = email
        
        # HTML email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #000; color: #fff; padding: 20px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; margin-top: 20px; }}
                .otp-code {{ font-size: 32px; font-weight: bold; color: #000; text-align: center; letter-spacing: 5px; padding: 20px; background-color: #fff; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Relact</h1>
                    <p>Smart Contact Manager</p>
                </div>
                <div class="content">
                    <h2>{title}</h2>
                    <p>{message_text}</p>
                    <div class="otp-code">{otp}</div>
                    <p><strong>This code will expire in 5 minutes.</strong></p>
                    <p>If you didn't request this code, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© 2026 Relact - Smart Contact Manager. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""
        Relact - {title}
        
        {message_text}
        
        Your code is: {otp}
        
        This code will expire in 5 minutes.
        
        If you didn't request this code, please ignore this email.
        
        © 2026 Relact - Smart Contact Manager
        """
        
        # Attach both HTML and plain text versions
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        message.attach(part1)
        message.attach(part2)
        
        # Send email via Gmail SMTP
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=True,
        )
        
        logger.info(f"OTP email sent successfully to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {e}")
        return False


async def send_welcome_email(email: str, username: str) -> bool:
    """
    Send welcome email after successful account creation
    
    Args:
        email: Recipient email address
        username: User's username
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    settings = get_settings()
    
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = "Welcome to Relact - Account Created Successfully!"
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = email
        
        # HTML email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #000; color: #fff; padding: 20px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; margin-top: 20px; }}
                .welcome-text {{ font-size: 24px; font-weight: bold; color: #000; text-align: center; margin-bottom: 20px; }}
                .features {{ background-color: #fff; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .feature-item {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
                .feature-item:last-child {{ border-bottom: none; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                .cta-button {{ display: inline-block; background-color: #000; color: #fff; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Relact</h1>
                    <p>Smart Contact Manager</p>
                </div>
                <div class="content">
                    <div class="welcome-text">Welcome, {username}! 🎉</div>
                    <p>Your account has been created successfully. You're now part of the Relact community!</p>
                    
                    <div class="features">
                        <h3>What you can do with Relact:</h3>
                        <div class="feature-item">📱 <strong>Manage Contacts</strong> - Organize all your contacts in one place</div>
                        <div class="feature-item">⏰ <strong>Set Reminders</strong> - Never forget to follow up with important contacts</div>
                        <div class="feature-item">📁 <strong>Create Folders</strong> - Group your contacts for easy access</div>
                        <div class="feature-item">📝 <strong>Add Notes</strong> - Keep important notes for each contact</div>
                        <div class="feature-item">🔒 <strong>Secure & Private</strong> - Your data is encrypted and safe</div>
                    </div>
                    
                    <p style="text-align: center;">Start managing your contacts smarter today!</p>
                </div>
                <div class="footer">
                    <p>Thank you for choosing Relact!</p>
                    <p>© 2026 Relact - Smart Contact Manager. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""
        Welcome to Relact - Smart Contact Manager!
        
        Hi {username},
        
        Your account has been created successfully. You're now part of the Relact community!
        
        What you can do with Relact:
        - Manage Contacts - Organize all your contacts in one place
        - Set Reminders - Never forget to follow up with important contacts
        - Create Folders - Group your contacts for easy access
        - Add Notes - Keep important notes for each contact
        - Secure & Private - Your data is encrypted and safe
        
        Start managing your contacts smarter today!
        
        Thank you for choosing Relact!
        
        © 2026 Relact - Smart Contact Manager
        """
        
        # Attach both HTML and plain text versions
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        message.attach(part1)
        message.attach(part2)
        
        # Send email via Gmail SMTP
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=True,
        )
        
        logger.info(f"Welcome email sent successfully to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email}: {e}")
        return False
