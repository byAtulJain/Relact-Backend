import sys
import os
import logging

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.contact_scheduler import contact_scheduler
from app.database import SessionLocal
from app.models import DeviceToken

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_daily_reminder():
    logger.info("Starting manual verification of daily app reminder...")
    
    # Check if there are any device tokens
    db = SessionLocal()
    count = db.query(DeviceToken).count()
    db.close()
    
    logger.info(f"Found {count} device tokens in database.")
    
    try:
        logger.info("Triggering send_daily_app_reminder()...")
        contact_scheduler.send_daily_app_reminder()
        logger.info("✅ send_daily_app_reminder() executed successfully.")
    except Exception as e:
        logger.error(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_daily_reminder()
