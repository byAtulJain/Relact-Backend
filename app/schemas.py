from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, computed_field
from typing import Optional, List, Generic, TypeVar, Any
from datetime import datetime, timezone, timedelta
from app.models import ContactType

# IST timezone offset (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


# Generic Response Wrappers
T = TypeVar('T')

class SuccessResponse(BaseModel, Generic[T]):
    """Generic success response wrapper"""
    success: bool = True
    message: Optional[str] = None
    data: T

class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    message: str
    detail: Optional[Any] = None

class ListResponse(BaseModel, Generic[T]):
    """Generic list response wrapper"""
    success: bool = True
    message: Optional[str] = None
    data: List[T]
    count: int

    @classmethod
    def create(cls, data: List[T], message: Optional[str] = None):
        """Create a list response with automatic count"""
        if not data:
            return cls(
                success=True,
                message=message or "No data found",
                data=[],
                count=0
            )
        return cls(
            success=True,
            message=message or "Data retrieved successfully",
            data=data,
            count=len(data)
        )


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Password must be 6-70 characters")


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="User password")
    
    @field_validator('password')
    @classmethod
    def validate_password_bytes(cls, v: str) -> str:
        """Validate password doesn't exceed 72 bytes (bcrypt limitation)"""
        if len(v) > 70:
            # Be more conservative - 70 chars should be safe
            raise ValueError(
                'Password is too long. Maximum is 70 characters. '
                'Please use a shorter password.'
            )
        
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 72:
            raise ValueError(
                f'Password is too long ({len(password_bytes)} bytes). '
                f'Maximum is 72 bytes. Please use a shorter password with fewer special characters.'
            )
        return v



class GoogleLoginRequest(BaseModel):
    token: str


class GoogleRegisterRequest(BaseModel):
    token: str
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Username Availability Check Schemas
class UsernameCheck(BaseModel):
    """Schema for checking username availability"""
    username: str = Field(..., min_length=3, max_length=20, description="Username to check")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format"""
        if not v.replace('_', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, and underscores')
        if v[0].isdigit():
            raise ValueError('Username cannot start with a number')
        return v.lower()


class UsernameAvailabilityResponse(BaseModel):
    """Response for username availability check"""
    available: bool
    message: str


# Email Verification Schemas
class SendVerificationCode(BaseModel):
    """Schema for sending verification code"""
    email: EmailStr


class VerifyEmail(BaseModel):
    """Schema for verifying email with OTP"""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


class VerificationResponse(BaseModel):
    """Response for email verification"""
    verified: bool
    verification_token: Optional[str] = None


class UserCreateWithVerification(UserBase):
    """Schema for user registration with verification token"""
    password: str = Field(..., min_length=6, description="Password must be 6-70 characters")
    verification_token: str = Field(..., description="Email verification token")


# Password Reset Schemas
class ForgotPassword(BaseModel):
    """Schema for forgot password request"""
    email: EmailStr


class VerifyResetCode(BaseModel):
    """Schema for verifying password reset code"""
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit reset code")


class ResetPassword(BaseModel):
    """Schema for resetting password"""
    email: EmailStr
    reset_token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")


class ResetTokenResponse(BaseModel):
    """Response for reset code verification"""
    verified: bool
    reset_token: str
    email: str


# Folder Schemas
class FolderBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class FolderCreate(FolderBase):
    pass


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class FolderResponse(FolderBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# Note Schemas
class NoteBase(BaseModel):
    content: str = Field(..., min_length=1)


class NoteCreate(NoteBase):
    pass


class NoteUpdate(NoteBase):
    pass


class NoteResponse(NoteBase):
    id: int
    contact_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# Reminder Schemas
class ReminderBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    remind_at: datetime


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    remind_at: Optional[datetime] = None
    is_completed: Optional[bool] = None


class ReminderResponse(ReminderBase):
    id: int
    contact_id: int
    is_completed: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def remind_at_ist(self) -> str:
        """Return remind_at in IST format"""
        if self.remind_at:
            # Convert to IST
            if self.remind_at.tzinfo is None:
                # Assume UTC if no timezone
                utc_time = self.remind_at.replace(tzinfo=timezone.utc)
            else:
                utc_time = self.remind_at
            ist_time = utc_time.astimezone(IST)
            return ist_time.strftime("%d/%m/%Y %I:%M %p IST")
        return None

    @computed_field
    @property
    def created_at_ist(self) -> str:
        """Return created_at in IST format"""
        if self.created_at:
            if self.created_at.tzinfo is None:
                utc_time = self.created_at.replace(tzinfo=timezone.utc)
            else:
                utc_time = self.created_at
            ist_time = utc_time.astimezone(IST)
            return ist_time.strftime("%d/%m/%Y %I:%M %p IST")
        return None


# Contact Schemas
class ContactBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None
    email: Optional[str] = None  # Changed from EmailStr to allow more flexibility
    profile_photo: Optional[str] = Field(None, description="URL or path to profile photo")
    contact_type: ContactType = ContactType.PERMANENT
    is_favorite: bool = False
    # folder_id removed


class ContactCreate(ContactBase):
    folder_ids: List[int] = []  # Changed to list of IDs
    delete_at_display: Optional[str] = Field(None, description="Delete date/time in format: dd/mm/yyyy hh:mm AM/PM")
    delete_at: Optional[datetime] = Field(None, description="Auto-calculated from delete_at_display")


class ContactUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = None
    email: Optional[str] = None
    profile_photo: Optional[str] = None
    contact_type: Optional[ContactType] = None
    folder_ids: Optional[List[int]] = None  # Changed to list of IDs
    delete_at_display: Optional[str] = Field(None, description="Delete date/time in format: dd/mm/yyyy hh:mm AM/PM")
    delete_at: Optional[datetime] = None


class ContactResponse(ContactBase):
    id: int
    user_id: int
    delete_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    folders: List[FolderResponse] = []  # Changed to list of FolderResponse
    notes: List[NoteResponse] = []
    reminders: List[ReminderResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ContactListResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    email: Optional[str]
    profile_photo: Optional[str]
    contact_type: ContactType
    folders: List[FolderResponse] = []  # Changed to list
    delete_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Duplicate Contact Check Response
class DuplicateContactResponse(BaseModel):
    is_duplicate: bool
    message: str
    existing_contact: Optional[ContactResponse] = None


class ContactFolderStatus(BaseModel):
    folder: FolderResponse
    is_assigned: bool
