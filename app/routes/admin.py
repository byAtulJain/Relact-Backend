from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AppContent, DeviceToken
from ..services.firebase_admin import firebase_service
from pathlib import Path

router = APIRouter(prefix="/admin", tags=["Admin"])

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/")
async def get_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    # Fetch current content
    privacy = db.query(AppContent).filter(AppContent.key == "privacy").first()
    about = db.query(AppContent).filter(AppContent.key == "about").first()

    # Fetch users for notification selection
    from ..models import User
    users = db.query(User).all()
    users_list = [{"id": u.id, "username": u.username, "email": u.email} for u in users]

    # Default Content (Should match app_info.py)
    default_privacy = """
**1. Information Collection**
• **Personal Data**: We collect your name, email, and phone number to create your account.
• **Contacts**: We store contact details you add to the app securely on our servers.
• **Usage Data**: We may collect anonymous usage statistics to improve the app.

**2. Data Usage**
• **Service Provision**: To allow you to manage and organize your contacts effectively.
• **Syncing**: To ensure your data is available across all your logged-in devices.
• **Communication**: To send important updates regarding your account or security.
"""

    default_about = """
**1. Our Mission**
• **Simplicity**: To make contact management effortless and intuitive.
• **Reliability**: Ensuring you never lose a connection that matters.

**3. App Info**
• **Version**: 1.0.0
• **Developer**: Atul Jain
• **Contact**: projectbyatul@gmail.com
"""

    privacy_content = privacy.content if privacy else default_privacy.strip()
    about_content = about.content if about else default_about.strip()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "privacy_content": privacy_content,
        "about_content": about_content,
        "users": users_list
    })

@router.post("/notifications")
async def send_notification(
    type: str = Form(...),
    title: str = Form(...),
    body: str = Form(...),
    link: str = Form(None),
    user_id: int = Form(None),
    db: Session = Depends(get_db)
):
    try:
        # Prepare data with optional link
        data_payload = {}
        if link:
            data_payload["link"] = link
            
        if type == "broadcast":
            # Broadcast to all users
            tokens = db.query(DeviceToken.device_token).all()
            token_list = [t[0] for t in tokens]
            
            # Send in batches
            batch_size = 500
            for i in range(0, len(token_list), batch_size):
                 firebase_service.send_multicast(
                    tokens=token_list[i:i + batch_size],
                    title=title,
                    body=body,
                    data=data_payload
                )
            return {"message": f"Broadcast sent to {len(token_list)} devices"}
            
        elif type == "specific":
            if not user_id:
                return {"error": "User ID required for specific notification"}
                
            tokens = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
            if not tokens:
                return {"error": "No devices found for this user"}
                
            token_list = [t.device_token for t in tokens]
            firebase_service.send_multicast(
                tokens=token_list,
                title=title,
                body=body,
                data=data_payload
            )
            return {"message": f"Sent to user {user_id}"}
            
        elif type == "update":
            # Update specific logic
            tokens = db.query(DeviceToken.device_token).all()
            token_list = [t[0] for t in tokens]
            
            # Add update type to data
            data_payload["type"] = "update"
             
            for i in range(0, len(token_list), 500):
                 firebase_service.send_multicast(
                    tokens=token_list[i:i + 500],
                    title=title,
                    body=body,
                    data=data_payload
                )
            return {"message": "Update alert sent"}
            
    except Exception as e:
        return {"error": str(e)}

@router.post("/content")
async def update_content(
    key: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        app_content = db.query(AppContent).filter(AppContent.key == key).first()
        if app_content:
            app_content.title = title
            app_content.content = content
        else:
            app_content = AppContent(key=key, title=title, content=content)
            db.add(app_content)
            
        db.commit()
        return {"message": f"{title} updated successfully"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
