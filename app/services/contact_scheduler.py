from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Contact, ContactType, DeviceToken, Reminder
from app.services.firebase_admin import firebase_service
import logging

logger = logging.getLogger(__name__)


class ContactScheduler:
    _instance = None
    _scheduler = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ContactScheduler, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._scheduler is None:
            self._scheduler = BackgroundScheduler()
            self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs"""
        # Check for expiring contacts every minute
        self._scheduler.add_job(
            self.check_expiring_contacts,
            'interval',
            minutes=1,
            id='check_expiring_contacts',
            replace_existing=True
        )
        
        # Delete expired contacts every minute
        self._scheduler.add_job(
            self.delete_expired_contacts,
            'interval',
            minutes=1,
            id='delete_expired_contacts',
            replace_existing=True
        )

        # Check for due reminders every minute
        self._scheduler.add_job(
            self.check_due_reminders,
            'interval',
            minutes=1,
            id='check_due_reminders',
            replace_existing=True
        )

    def start(self):
        """Start the scheduler"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("✅ Contact scheduler started")

    def shutdown(self):
        """Shutdown the scheduler"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("🛑 Contact scheduler stopped")

    def check_expiring_contacts(self):
        """Check for contacts expiring in 1 minute and send warning notifications"""
        db: Session = SessionLocal()
        try:
            # Use timezone-aware datetime (UTC)
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            # Get contacts expiring in the next 1-2 minutes
            warning_time_start = now + timedelta(minutes=1)
            warning_time_end = now + timedelta(minutes=2)
            
            logger.info(f"Checking for expiring contacts. Current time (UTC): {now}")
            
            expiring_contacts = db.query(Contact).filter(
                Contact.contact_type == ContactType.TEMPORARY,
                Contact.delete_at.isnot(None),
                Contact.delete_at >= warning_time_start,
                Contact.delete_at < warning_time_end
            ).all()

            if expiring_contacts:
                logger.info(f"Found {len(expiring_contacts)} contacts expiring soon")

            for contact in expiring_contacts:
                logger.info(f"Contact '{contact.name}' expires at: {contact.delete_at}")
                
                # Get user's device tokens
                device_tokens = db.query(DeviceToken).filter(
                    DeviceToken.user_id == contact.user_id
                ).all()

                if device_tokens:
                    tokens = [dt.device_token for dt in device_tokens]
                    
                    # Calculate time until deletion
                    time_left = contact.delete_at - now
                    minutes_left = int(time_left.total_seconds() / 60)
                    
                    # Send warning notification
                    result = firebase_service.send_multicast(
                        tokens=tokens,
                        title=f"Contact Expiring Soon",
                        body=f"{contact.name} will be deleted in {minutes_left} minute(s)",
                        data={
                            "type": "contact_expiring_warning",
                            "contact_id": str(contact.id),
                            "contact_name": contact.name,
                            "delete_at": contact.delete_at.isoformat(),
                            "minutes_left": str(minutes_left)
                        }
                    )
                    
                    logger.info(f"Sent expiration warning for '{contact.name}' - Success: {result['success_count']}, Failed: {result['failure_count']}")
                else:
                    logger.warning(f"No device tokens found for user {contact.user_id}")

        except Exception as e:
            logger.error(f"Error checking expiring contacts: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            db.close()

    def delete_expired_contacts(self):
        """Delete contacts that have passed their deletion time"""
        db: Session = SessionLocal()
        try:
            # Use timezone-aware datetime (UTC)
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            logger.info(f"Checking for expired contacts. Current time (UTC): {now}")
            
            # Get contacts that should be deleted
            expired_contacts = db.query(Contact).filter(
                Contact.contact_type == ContactType.TEMPORARY,
                Contact.delete_at.isnot(None),
                Contact.delete_at <= now
            ).all()

            if expired_contacts:
                logger.info(f"Found {len(expired_contacts)} expired contacts to delete")

            for contact in expired_contacts:
                contact_name = contact.name
                contact_id = contact.id
                user_id = contact.user_id
                
                logger.info(f"Deleting contact '{contact_name}' (ID: {contact_id}, delete_at: {contact.delete_at})")
                
                # Delete the contact
                db.delete(contact)
                db.commit()
                
                logger.info(f"Deleted expired contact: {contact_name} (ID: {contact_id})")
                
                # Send deletion notification
                device_tokens = db.query(DeviceToken).filter(
                    DeviceToken.user_id == user_id
                ).all()

                if device_tokens:
                    tokens = [dt.device_token for dt in device_tokens]
                    
                    result = firebase_service.send_multicast(
                        tokens=tokens,
                        title=f"Contact Deleted",
                        body=f"{contact_name} has been automatically deleted",
                        data={
                            "type": "contact_deleted",
                            "contact_id": str(contact_id),
                            "contact_name": contact_name
                        }
                    )
                    
                    logger.info(f"Sent deletion notification for '{contact_name}' - Success: {result['success_count']}")

        except Exception as e:
            logger.error(f"Error deleting expired contacts: {e}")
            import traceback
            logger.error(traceback.format_exc())
            db.rollback()
        finally:
            db.close()

    def check_due_reminders(self):
        """Check for reminders that are due and send notifications"""
        db: Session = SessionLocal()
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            logger.info(f"Checking for due reminders. Current time (UTC): {now}")
            
            # Get due reminders that have not been notified
            # We join with Contact to ensure we can get the user owner
            due_reminders = db.query(Reminder).join(Contact).filter(
                Reminder.notification_sent == False,
                Reminder.is_completed == False,
                Reminder.remind_at <= now
            ).all()

            if due_reminders:
                logger.info(f"Found {len(due_reminders)} due reminders")

            for reminder in due_reminders:
                contact = reminder.contact
                if not contact:
                    logger.warning(f"Reminder {reminder.id} has no associated contact")
                    continue
                    
                user_id = contact.user_id
                
                logger.info(f"Processing reminder '{reminder.title}' for Contact '{contact.name}' (User ID: {user_id})")
                
                # Send notification
                device_tokens = db.query(DeviceToken).filter(
                    DeviceToken.user_id == user_id
                ).all()

                if device_tokens:
                    tokens = [dt.device_token for dt in device_tokens]
                    
                    result = firebase_service.send_multicast(
                        tokens=tokens,
                        title=f"Reminder: {reminder.title}",
                        body=f"{reminder.description or 'Reminder for ' + contact.name}",
                        data={
                            "type": "reminder",
                            "reminder_id": str(reminder.id),
                            "contact_id": str(contact.id),
                            "contact_name": contact.name
                        }
                    )
                    
                    logger.info(f"Sent reminder notification - Success: {result['success_count']}")
                
                # Mark as notified (BUT NOT COMPLETED, so it stays in UI)
                reminder.notification_sent = True
                db.commit()
                
        except Exception as e:
            logger.error(f"Error checking due reminders: {e}")
            import traceback
            logger.error(traceback.format_exc())
            db.rollback()
        finally:
            db.close()


# Singleton instance
contact_scheduler = ContactScheduler()
