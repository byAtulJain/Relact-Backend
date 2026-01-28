from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import User, TokenBlacklist
from app.schemas import TokenData

settings = get_settings()

security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hashed password using bcrypt directly."""
    try:
        # Truncate password to 72 bytes (bcrypt's hard limit)
        password_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt directly, with proper 72-byte handling."""
    # Truncate to 72 bytes if needed (bcrypt's hard limit)
    password_bytes = password.encode('utf-8')[:72]
    
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Default to 365 days (1 year)
        expire = datetime.utcnow() + timedelta(days=settings.access_token_expire_days)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenData(username=username)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, username_or_email: str, password: str) -> Optional[User]:
    """
    Authenticate user by username or email.
    Checks both username and email fields to find the user.
    """
    # Try to find user by username first
    user = get_user_by_username(db, username_or_email)
    
    # If not found by username, try email
    if not user:
        user = get_user_by_email(db, username_or_email)
    
    # If still not found, return None
    if not user:
        return None
    
    # Verify password
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


def is_token_blacklisted(db: Session, token: str) -> bool:
    return db.query(TokenBlacklist).filter(TokenBlacklist.token == token).first() is not None


def blacklist_token(db: Session, token: str, user_id: int):
    db_token = TokenBlacklist(token=token, user_id=user_id)
    db.add(db_token)
    db.commit()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    
    # Check if token is blacklisted
    if is_token_blacklisted(db, token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = decode_access_token(token)
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
