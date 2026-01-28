from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            # Use text() explicitly for raw SQL
            conn.execute(text("ALTER TABLE reminders ADD COLUMN notification_sent BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("✅ Column 'notification_sent' added successfully")
        except Exception as e:
            print(f"⚠️  Error (maybe column exists): {e}")

if __name__ == "__main__":
    migrate()
