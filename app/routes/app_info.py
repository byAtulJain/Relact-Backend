from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AppContent
from pydantic import BaseModel
from typing import Optional

router = APIRouter(
    prefix="/app-info",
    tags=["App Info"]
)

class AppInfoResponse(BaseModel):
    title: str
    content: str
    version: Optional[str] = None

@router.get("/{info_type}", response_model=AppInfoResponse)
async def get_app_info(
    info_type: str,
    db: Session = Depends(get_db)
):
    """
    Get application information based on type (privacy, help, about).
    Fetches from database, falls back to default if not set.
    """
    # Fetch from DB
    content_record = db.query(AppContent).filter(AppContent.key == info_type).first()
    
    if content_record:
        return AppInfoResponse(
            title=content_record.title,
            content=content_record.content,
            version="1.0.0" if info_type == "about" else None
        )

    # Fallback Defaults (if DB is empty)
    if info_type == "privacy":
        default_content = """
**1. Information Collection**
• **Personal Data**: We collect your name, email, and phone number to create your account.
• **Contacts**: We store contact details you add to the app securely on our servers.
• **Usage Data**: We may collect anonymous usage statistics to improve the app.

**2. Data Usage**
• **Service Provision**: To allow you to manage and organize your contacts effectively.
• **Syncing**: To ensure your data is available across all your logged-in devices.
• **Communication**: To send important updates regarding your account or security.
"""
        return AppInfoResponse(title="Privacy Policy", content=default_content)
        
    elif info_type == "help":
         return AppInfoResponse(
            title="Help & Support",
            content="""
**1. Contact Support**
• Email: projectbyatul@gmail.com
            """
        )
    elif info_type == "about":
        default_content = """
**1. Our Mission**
• **Simplicity**: To make contact management effortless and intuitive.
• **Reliability**: Ensuring you never lose a connection that matters.

**3. App Info**
• **Version**: 1.0.0
• **Developer**: Atul Jain
• **Contact**: projectbyatul@gmail.com
"""
        return AppInfoResponse(title="About Relact", content=default_content, version="1.0.0")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Info type '{info_type}' not found"
        )
