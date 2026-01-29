from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models import User, EmailVerification
from app.schemas import (
    UserCreate, UserResponse, Token, UserLogin, SuccessResponse, UsernameCheck,
    SendVerificationCode, VerifyEmail, VerificationResponse, UserCreateWithVerification,
    ForgotPassword, VerifyResetCode, ResetPassword, ResetTokenResponse, GoogleLoginRequest,
    GoogleRegisterRequest
)
import firebase_admin
from firebase_admin import auth as firebase_auth
from app.auth import (
    get_password_hash,
    authenticate_user,
    create_access_token,
    get_current_user,
    blacklist_token,
    security
)
from app.services.email_service import send_otp_email, generate_otp, send_welcome_email
from app.logger import logger
import traceback
import secrets

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/send-verification-code")
async def send_verification_code(
    request: SendVerificationCode,
    db: Session = Depends(get_db)
):
    """
    Send OTP verification code to email.
    Generates 6-digit code, stores in database, and sends via email.
    """
    try:
        logger.info(f"Sending verification code to: {request.email}")
        
        # Check if email already registered
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Delete any existing unverified codes for this email
        db.query(EmailVerification).filter(
            EmailVerification.email == request.email,
            EmailVerification.is_verified == False
        ).delete()
        db.commit()
        
        # Generate OTP and create verification record
        otp = generate_otp()
        from datetime import timezone
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        verification = EmailVerification(
            email=request.email,
            otp_code=otp,
            expires_at=expires_at
        )
        db.add(verification)
        db.commit()
        
        # Send OTP email
        email_sent = await send_otp_email(request.email, otp)
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email"
            )
        
        logger.info(f"Verification code sent successfully to {request.email}")
        return {
            "success": True,
            "message": "Verification code sent to email",
            "data": {
                "email": request.email,
                "expires_in": 300  # 5 minutes in seconds
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending verification code: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification code: {str(e)}"
        )


@router.post("/verify-email")
def verify_email(
    request: VerifyEmail,
    db: Session = Depends(get_db)
):
    """
    Verify email with OTP code.
    Returns verification token for registration.
    """
    try:
        logger.info(f"Verifying email: {request.email}")
        
        # Find verification record
        verification = db.query(EmailVerification).filter(
            EmailVerification.email == request.email,
            EmailVerification.is_verified == False
        ).order_by(EmailVerification.created_at.desc()).first()
        
        if not verification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No verification code found for this email"
            )
        
        # Check expiration (use timezone-aware datetime)
        from datetime import timezone
        current_time = datetime.now(timezone.utc)
        if current_time > verification.expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired"
            )
        
        # Check attempts
        if verification.attempts >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. Please request a new code"
            )
        
        # Verify OTP
        if verification.otp_code != request.otp:
            verification.attempts += 1
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification code. {3 - verification.attempts} attempts remaining"
            )
        
        # Mark as verified and generate token
        verification.is_verified = True
        verification_token = secrets.token_urlsafe(32)
        db.commit()
        
        logger.info(f"Email verified successfully: {request.email}")
        return {
            "success": True,
            "message": "Email verified successfully",
            "data": {
                "verified": True,
                "verification_token": verification_token,
                "email": request.email
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying email: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email verification failed: {str(e)}"
        )


@router.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.
    """
    try:
        logger.info(f"Registration attempt for username: {user.username}, email: {user.email}")
        logger.debug(f"Password length: {len(user.password)} chars, {len(user.password.encode('utf-8'))} bytes")
        
        # Check if username already exists
        db_user = db.query(User).filter(User.username == user.username).first()
        if db_user:
            logger.warning(f"Registration failed: Username already exists - {user.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            logger.warning(f"Registration failed: Email already exists - {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        logger.debug("Hashing password...")
        hashed_password = get_password_hash(user.password)
        logger.debug("Password hashed successfully")
        
        db_user = User(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"User registered successfully: {user.username} (ID: {db_user.id})")
        
        # Send welcome email (don't fail registration if email fails)
        try:
            await send_welcome_email(user.email, user.username)
        except Exception as email_error:
            logger.warning(f"Failed to send welcome email to {user.email}: {email_error}")
        
        return {"success": True, "message": "User registered successfully", "data": db_user}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error for {user.username}: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login")
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login to get access token. Token expires in 1 year.
    You can login with either username or email.
    Send username/email and password in request body as JSON.
    """
    try:
        logger.info(f"Login attempt for: {credentials.username}")
        
        user = authenticate_user(db, credentials.username, credentials.password)
        if not user:
            logger.warning(f"Login failed: Invalid credentials for {credentials.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username/email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(data={"sub": user.username})
        logger.info(f"User logged in successfully: {user.username} (ID: {user.id})")
        return {"success": True, "message": "Login successful", "data": {"access_token": access_token, "token_type": "bearer"}}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {credentials.username}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout and blacklist the current token.
    """
    token = credentials.credentials
    blacklist_token(db, token, current_user.id)
    return {"success": True, "message": "Successfully logged out"}


@router.post("/check-username")
def check_username_availability(
    username_check: UsernameCheck,
    db: Session = Depends(get_db)
):
    """
    Check if a username is available for registration.
    Returns availability status without requiring authentication.
    """
    try:
        logger.info(f"Username availability check for: {username_check.username}")
        
        # Check if username exists
        existing_user = db.query(User).filter(
            User.username == username_check.username
        ).first()
        
        if existing_user:
            logger.info(f"Username not available: {username_check.username}")
            return {
                "success": True,
                "message": "Username check completed",
                "data": {
                    "available": False,
                    "message": "Username is already taken"
                }
            }
        
        logger.info(f"Username available: {username_check.username}")
        return {
            "success": True,
            "message": "Username check completed",
            "data": {
                "available": True,
                "message": "Username is available"
            }
        }
        
    except Exception as e:
        logger.error(f"Username check error for {username_check.username}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Username check failed: {str(e)}"
        )


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPassword,
    db: Session = Depends(get_db)
):
    """
    Send password reset code to email.
    Checks if email exists and sends OTP.
    """
    try:
        logger.info(f"Password reset requested for: {request.email}")
        
        # Check if user exists
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No account found with this email"
            )
        
        # Delete any existing unverified codes for this email
        db.query(EmailVerification).filter(
            EmailVerification.email == request.email,
            EmailVerification.is_verified == False
        ).delete()
        db.commit()
        
        # Generate OTP and create verification record
        otp = generate_otp()
        from datetime import timezone
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        verification = EmailVerification(
            email=request.email,
            otp_code=otp,
            expires_at=expires_at
        )
        db.add(verification)
        db.commit()
        
        # Send OTP email
        email_sent = await send_otp_email(request.email, otp, is_reset=True)
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send reset code email"
            )
        
        logger.info(f"Password reset code sent to {request.email}")
        return {
            "success": True,
            "message": "Password reset code sent to email",
            "data": {
                "email": request.email,
                "expires_in": 300
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending password reset code: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send reset code: {str(e)}"
        )


@router.post("/verify-reset-code")
def verify_reset_code(
    request: VerifyResetCode,
    db: Session = Depends(get_db)
):
    """
    Verify password reset OTP code.
    Returns reset token for password change.
    """
    try:
        logger.info(f"Verifying reset code for: {request.email}")
        
        # Find verification record
        verification = db.query(EmailVerification).filter(
            EmailVerification.email == request.email,
            EmailVerification.is_verified == False
        ).order_by(EmailVerification.created_at.desc()).first()
        
        if not verification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No reset code found for this email"
            )
        
        # Check expiration
        from datetime import timezone
        current_time = datetime.now(timezone.utc)
        if current_time > verification.expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code has expired"
            )
        
        # Check attempts
        if verification.attempts >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. Please request a new code"
            )
        
        # Verify OTP
        if verification.otp_code != request.otp:
            verification.attempts += 1
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid reset code. {3 - verification.attempts} attempts remaining"
            )
        
        # Mark as verified and generate reset token
        verification.is_verified = True
        reset_token = secrets.token_urlsafe(32)
        db.commit()
        
        logger.info(f"Reset code verified for: {request.email}")
        return {
            "success": True,
            "message": "Reset code verified successfully",
            "data": {
                "verified": True,
                "reset_token": reset_token,
                "email": request.email
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying reset code: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reset code verification failed: {str(e)}"
        )


@router.post("/reset-password")
def reset_password(
    request: ResetPassword,
    db: Session = Depends(get_db)
):
    """
    Reset user password with verified token.
    Updates password and deletes verification record.
    """
    try:
        logger.info(f"Password reset for: {request.email}")
        
        # Find user
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found"
            )
        
        # Verify that a verified code exists (token validation)
        verification = db.query(EmailVerification).filter(
            EmailVerification.email == request.email,
            EmailVerification.is_verified == True
        ).order_by(EmailVerification.created_at.desc()).first()
        
        if not verification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Update password
        user.hashed_password = get_password_hash(request.new_password)
        
        # Delete verification record
        db.delete(verification)
        db.commit()
        
        logger.info(f"Password reset successfully for: {request.email}")
        return {
            "success": True,
            "message": "Password reset successfully",
            "data": {
                "email": request.email
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password reset failed: {str(e)}"
        )


@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information.
    """
    return {"success": True, "message": "User data retrieved", "data": current_user}


@router.post("/google-login", response_model=SuccessResponse[Token])
async def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    """
    Login with Google ID Token.
    Returns 404 if user does not exist (needs registration).
    """
    try:
        # Verify token
        try:
            decoded_token = firebase_auth.verify_id_token(request.token)
        except Exception as e:
             logger.error(f"Token verification failed: {e}")
             raise ValueError(f"Invalid Google Token: {e}")

        email = decoded_token['email']
        
        # Check if user exists
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            # User does not exist - return 404
            logger.info(f"Google login attempted for non-existent user: {email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please complete registration."
            )
        
        # User exists - create token
        access_token = create_access_token(data={"sub": user.username})
        logger.info(f"User logged in via Google: {user.username}")
        
        return {
            "success": True, 
            "message": "Google Login Successful", 
            "data": {"access_token": access_token, "token_type": "bearer"}
        }
        
    except HTTPException:
        raise
    except ValueError as e:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Google Login Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/google-register", response_model=SuccessResponse[Token])
async def google_register(request: GoogleRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user with Google authentication.
    Verifies Google token, then creates user with provided username and password.
    """
    try:
        # Verify Google token
        try:
            decoded_token = firebase_auth.verify_id_token(request.token)
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise ValueError(f"Invalid Google Token: {e}")

        email = decoded_token['email']
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists. Please login instead."
            )
        
        # Check if username is taken
        username_exists = db.query(User).filter(User.username == request.username).first()
        if username_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Create new user
        hashed_password = get_password_hash(request.password)
        user = User(
            email=email,
            username=request.username,
            hashed_password=hashed_password,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"User registered via Google: {user.username} (ID: {user.id})")
        
        # Send welcome email (don't fail registration if email fails)
        try:
            await send_welcome_email(email, request.username)
        except Exception as email_error:
            logger.warning(f"Failed to send welcome email to {email}: {email_error}")
        
        # Create access token
        access_token = create_access_token(data={"sub": user.username})
        
        return {
            "success": True,
            "message": "Registration successful",
            "data": {"access_token": access_token, "token_type": "bearer"}
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Google Registration Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
