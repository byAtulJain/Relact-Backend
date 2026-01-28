from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from ..database import get_db
from ..models import DeviceToken, User
from ..auth import get_current_user

router = APIRouter(prefix="/device-tokens", tags=["Device Tokens"])


# Pydantic schemas
class DeviceTokenCreate(BaseModel):
    device_token: str
    device_type: str  # 'android' or 'ios'


class DeviceTokenResponse(BaseModel):
    id: int
    device_token: str
    device_type: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("/", status_code=status.HTTP_201_CREATED)
def register_device_token(
    token_data: DeviceTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Register or update device token for the current user
    """
    # Check if token already exists for this user
    existing_token = db.query(DeviceToken).filter(
        DeviceToken.user_id == current_user.id,
        DeviceToken.device_token == token_data.device_token
    ).first()

    if existing_token:
        # Update existing token
        existing_token.device_type = token_data.device_type
        db.commit()
        db.refresh(existing_token)
        
        return {
            "success": True,
            "message": "Device token updated successfully",
            "data": {
                "id": existing_token.id,
                "device_token": existing_token.device_token,
                "device_type": existing_token.device_type,
                "created_at": existing_token.created_at.isoformat()
            }
        }

    # Create new token
    new_token = DeviceToken(
        user_id=current_user.id,
        device_token=token_data.device_token,
        device_type=token_data.device_type
    )
    
    db.add(new_token)
    db.commit()
    db.refresh(new_token)

    return {
        "success": True,
        "message": "Device token registered successfully",
        "data": {
            "id": new_token.id,
            "device_token": new_token.device_token,
            "device_type": new_token.device_type,
            "created_at": new_token.created_at.isoformat()
        }
    }


@router.delete("/{token}")
def delete_device_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a device token for the current user
    """
    device_token = db.query(DeviceToken).filter(
        DeviceToken.user_id == current_user.id,
        DeviceToken.device_token == token
    ).first()

    if not device_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device token not found"
        )

    db.delete(device_token)
    db.commit()

    return {
        "success": True,
        "message": "Device token deleted successfully"
    }


@router.get("/me")
def get_my_device_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all device tokens for the current user
    """
    tokens = db.query(DeviceToken).filter(
        DeviceToken.user_id == current_user.id
    ).all()

    return {
        "success": True,
        "message": "Device tokens retrieved successfully",
        "data": [
            {
                "id": token.id,
                "device_token": token.device_token,
                "device_type": token.device_type,
                "created_at": token.created_at.isoformat()
            }
            for token in tokens
        ]
    }
