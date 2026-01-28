"""
Script to initialize the database and create all tables
"""
from app.database import engine, Base
from app.models import User, Contact, Folder, Note, Reminder, TokenBlacklist

print("Creating database tables...")

try:
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully!")
    
    # List all tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n📋 Tables created: {', '.join(tables)}")
    
except Exception as e:
    print(f"❌ Error creating tables: {e}")
