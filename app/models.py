from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, Table, event
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ContactType(str, enum.Enum):
    TEMPORARY = "temporary"
    PERMANENT = "permanent"


# Association Table for Many-to-Many relationship between Contacts and Folders
contact_folders = Table(
    'contact_folders',
    Base.metadata,
    Column('contact_id', Integer, ForeignKey('contacts.id'), primary_key=True),
    Column('folder_id', Integer, ForeignKey('folders.id'), primary_key=True)
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    contacts = relationship("Contact", back_populates="owner", cascade="all, delete-orphan")
    folders = relationship("Folder", back_populates="owner", cascade="all, delete-orphan")
    tokens = relationship("TokenBlacklist", back_populates="user", cascade="all, delete-orphan")
    device_tokens = relationship("DeviceToken", back_populates="user", cascade="all, delete-orphan")


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="folders")
    contacts = relationship("Contact", secondary=contact_folders, back_populates="folders")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=True, index=True)
    email = Column(String, nullable=True, index=True)
    profile_photo = Column(String, nullable=True)  # URL or path to profile photo
    contact_type = Column(Enum(ContactType), default=ContactType.PERMANENT, nullable=False)
    is_favorite = Column(Boolean, default=False, nullable=False)
    
    # For temporary contacts - deletion time
    delete_at = Column(DateTime(timezone=True), nullable=True)
    
    # Foreign Keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # folder_id removed for Many-to-Many
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="contacts")
    folders = relationship("Folder", secondary=contact_folders, back_populates="contacts")
    notes = relationship("Note", back_populates="contact", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="contact", cascade="all, delete-orphan")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    contact = relationship("Contact", back_populates="notes")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    remind_at = Column(DateTime(timezone=True), nullable=False)
    is_completed = Column(Boolean, default=False)
    notification_sent = Column(Boolean, default=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    contact = relationship("Contact", back_populates="reminders")


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    blacklisted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="tokens")


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_token = Column(String, unique=True, nullable=False, index=True)
    device_type = Column(String, nullable=False)  # 'android' or 'ios'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="device_tokens")


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)


# Encryption event listeners for Contact model
@event.listens_for(Contact, 'before_insert')
@event.listens_for(Contact, 'before_update')
def encrypt_phone_before_save(mapper, connection, target):
    """Encrypt phone number before saving to database"""
    from app.encryption import encrypt_phone
    if target.phone and not target.phone.startswith('gAAAAA'):  # Check if not already encrypted
        target.phone = encrypt_phone(target.phone)


@event.listens_for(Contact, 'load')
def decrypt_phone_after_load(target, context):
    """Decrypt phone number after loading from database"""
    from app.encryption import decrypt_phone
    if target.phone:
        target.phone = decrypt_phone(target.phone)


class AppContent(Base):
    __tablename__ = "app_content"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)  # 'privacy', 'about'
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
