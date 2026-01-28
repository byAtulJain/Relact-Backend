from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel
from ..database import get_db
from ..models import DeviceToken, User
from ..auth import get_current_user
from ..services.firebase_admin import firebase_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# Pydantic schemas
class SendNotificationRequest(BaseModel):
    user_id: int
    title: str
    body: str
    data: Optional[Dict[str, str]] = None


class BroadcastNotificationRequest(BaseModel):
    title: str
    body: str
    data: Optional[Dict[str, str]] = None


class TestNotificationRequest(BaseModel):
    device_token: str
    title: str = "Test Notification"
    body: str = "This is a test notification from Relact"
    data: Optional[Dict[str, str]] = None


@router.post("/send")
def send_notification_to_user(
    notification: SendNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send notification to a specific user
    Admin only or user can send to themselves
    """
    # Get all device tokens for the target user
    device_tokens = db.query(DeviceToken).filter(
        DeviceToken.user_id == notification.user_id
    ).all()

    if not device_tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No device tokens found for this user"
        )

    # Extract token strings
    tokens = [dt.device_token for dt in device_tokens]

    # Send multicast notification
    result = firebase_service.send_multicast(
        tokens=tokens,
        title=notification.title,
        body=notification.body,
        data=notification.data
    )

    return {
        "success": True,
        "message": "Notification sent successfully",
        "data": {
            "user_id": notification.user_id,
            "devices_targeted": len(tokens),
            "success_count": result.get("success_count", 0),
            "failure_count": result.get("failure_count", 0)
        }
    }


@router.post("/broadcast")
def broadcast_notification(
    notification: BroadcastNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send notification to all users
    Admin only
    """
    # Get all device tokens
    all_tokens = db.query(DeviceToken).all()

    if not all_tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No device tokens found"
        )

    # Extract token strings
    tokens = [dt.device_token for dt in all_tokens]

    # Send in batches of 500 (FCM limit)
    batch_size = 500
    total_success = 0
    total_failure = 0

    for i in range(0, len(tokens), batch_size):
        batch = tokens[i:i + batch_size]
        result = firebase_service.send_multicast(
            tokens=batch,
            title=notification.title,
            body=notification.body,
            data=notification.data
        )
        total_success += result.get("success_count", 0)
        total_failure += result.get("failure_count", 0)

    return {
        "success": True,
        "message": "Broadcast notification sent successfully",
        "data": {
            "total_devices": len(tokens),
            "success_count": total_success,
            "failure_count": total_failure
        }
    }


@router.post("/test")
def send_test_notification(
    test_request: TestNotificationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Send a test notification to a specific device token
    """
    success = firebase_service.send_notification(
        token=test_request.device_token,
        title=test_request.title,
        body=test_request.body,
        data=test_request.data
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test notification"
        )

    return {
        "success": True,
        "message": "Test notification sent successfully",
        "data": {
            "device_token": test_request.device_token,
            "title": test_request.title,
            "body": test_request.body
        }
    }
