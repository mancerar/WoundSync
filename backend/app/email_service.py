"""
Email service for sending password reset and notification emails.
Uses SendGrid for reliable email delivery.
"""

import os
import datetime
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import logging

logger = logging.getLogger("woundsync-backend")


class EmailService:
    """Handle email sending via SendGrid."""
    
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY", "").strip()
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@woundsync.com").strip()
        self.from_name = os.getenv("SENDGRID_FROM_NAME", "WoundSync").strip()
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            logger.warning("SendGrid not configured - emails will not be sent")
        else:
            logger.info(f"SendGrid email service initialized (from: {self.from_email})")
    
    def send_password_reset_email(
        self,
        to_email: str,
        reset_link: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send a password reset email.
        
        Args:
            to_email: Recipient email address
            reset_link: Password reset URL
            user_name: Optional user name for personalization
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Email not sent to {to_email} - SendGrid not configured")
            return False
        
        subject = "Reset Your WoundSync Password"
        
        # HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reset Your Password</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td align="center" style="padding: 40px 0;">
                        <table role="presentation" style="width: 600px; max-width: 100%; border-collapse: collapse; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                            <!-- Header -->
                            <tr>
                                <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px 12px 0 0;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">WoundSync</h1>
                                </td>
                            </tr>
                            
                            <!-- Content -->
                            <tr>
                                <td style="padding: 40px;">
                                    <h2 style="margin: 0 0 20px; color: #1f2937; font-size: 24px; font-weight: 600;">Reset Your Password</h2>
                                    
                                    <p style="margin: 0 0 20px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                        {"Hi " + user_name + "," if user_name else "Hello,"}
                                    </p>
                                    
                                    <p style="margin: 0 0 20px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                        We received a request to reset your password for your WoundSync account. Click the button below to create a new password:
                                    </p>
                                    
                                    <!-- Button -->
                                    <table role="presentation" style="margin: 30px 0;">
                                        <tr>
                                            <td style="border-radius: 8px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                                <a href="{reset_link}" target="_blank" style="display: inline-block; padding: 16px 32px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 8px;">
                                                    Reset Password
                                                </a>
                                            </td>
                                        </tr>
                                    </table>
                                    
                                    <p style="margin: 20px 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                        Or copy and paste this link into your browser:
                                    </p>
                                    
                                    <p style="margin: 0 0 20px; padding: 12px; background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; color: #4b5563; font-size: 14px; word-break: break-all;">
                                        {reset_link}
                                    </p>
                                    
                                    <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                        <strong>This link will expire in 1 hour.</strong>
                                    </p>
                                    
                                    <p style="margin: 20px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                        If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
                                    </p>
                                </td>
                            </tr>
                            
                            <!-- Footer -->
                            <tr>
                                <td style="padding: 30px 40px; background-color: #f9fafb; border-radius: 0 0 12px 12px; border-top: 1px solid #e5e7eb;">
                                    <p style="margin: 0; color: #9ca3af; font-size: 12px; line-height: 1.6; text-align: center;">
                                        This email was sent by WoundSync. If you have questions, please contact support.
                                    </p>
                                    <p style="margin: 10px 0 0; color: #9ca3af; font-size: 12px; text-align: center;">
                                        © {datetime.datetime.now().year} WoundSync. All rights reserved.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_content = f"""
        Reset Your WoundSync Password
        
        {"Hi " + user_name + "," if user_name else "Hello,"}
        
        We received a request to reset your password for your WoundSync account.
        
        Click this link to create a new password:
        {reset_link}
        
        This link will expire in 1 hour.
        
        If you didn't request a password reset, you can safely ignore this email.
        
        ---
        WoundSync Team
        """
        
        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )
            
            logger.info(f"Sending email via SendGrid to {to_email}")
            logger.info(f"From: {self.from_email} ({self.from_name})")
            logger.info(f"Subject: {subject}")
            
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            # Log response details with safe string conversion
            try:
                status = getattr(response, 'status_code', 'unknown')
                logger.info(f"SendGrid response status: {status}")
                
                body = getattr(response, 'body', b'')
                if isinstance(body, bytes):
                    body = body.decode('utf-8', errors='replace')
                logger.info(f"SendGrid response body: {body}")
                
                headers = getattr(response, 'headers', {})
                logger.info(f"SendGrid response headers: {dict(headers) if headers else 'none'}")
            except Exception as log_err:
                logger.warning(f"Could not log SendGrid response details: {log_err}")
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Password reset email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"SendGrid returned unexpected status {response.status_code} for {to_email}")
                logger.error(f"Response body: {response.body}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send password reset email to {to_email}: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def send_welcome_email(self, to_email: str, user_name: Optional[str] = None) -> bool:
        """
        Send a welcome email to new users.
        
        Args:
            to_email: Recipient email address
            user_name: Optional user name for personalization
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Email not sent to {to_email} - SendGrid not configured")
            return False
        
        subject = "Welcome to WoundSync!"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Welcome to WoundSync</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6;">
            <table role="presentation" style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td align="center" style="padding: 40px 0;">
                        <table role="presentation" style="width: 600px; max-width: 100%; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                            <tr>
                                <td style="padding: 40px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px 12px 0 0;">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 28px;">Welcome to WoundSync!</h1>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 40px;">
                                    <p style="margin: 0 0 20px; color: #4b5563; font-size: 16px;">
                                        {"Hi " + user_name + "," if user_name else "Hello,"}
                                    </p>
                                    <p style="margin: 0 0 20px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                        Thank you for joining WoundSync! We're excited to help you track and manage wound healing with AI-powered insights.
                                    </p>
                                    <p style="margin: 0 0 20px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                        Get started by uploading your first wound photo and receive instant analysis and care recommendations.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            return response.status_code in [200, 201, 202]
                
        except Exception as e:
            logger.error(f"Failed to send welcome email to {to_email}: {e}")
            return False


# Global instance
email_service = EmailService()
