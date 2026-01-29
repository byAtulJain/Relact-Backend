from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models import User, Reminder, Contact
from app.schemas import ReminderCreate, ReminderUpdate, ReminderResponse, SuccessResponse, ListResponse
from app.auth import get_current_active_user

router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.get("/reminders")
def get_all_reminders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_completed: bool = Query(False, description="Include completed reminders"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> ListResponse[ReminderResponse]:
    """
    Get all reminders for the current user across all contacts.
    """
    query = db.query(Reminder).join(Contact).filter(
        Contact.user_id == current_user.id
    )
    
    if not include_completed:
        query = query.filter(Reminder.is_completed == False)
        
    reminders = query.order_by(Reminder.remind_at).offset(skip).limit(limit).all()
    
    if not reminders:
        return {"success": True, "message": "No reminders found", "data": [], "count": 0}
    return {"success": True, "message": "Reminders retrieved successfully", "data": reminders, "count": len(reminders)}


@router.post("/contacts/{contact_id}/reminders")
def create_reminder(
    contact_id: int,
    reminder: ReminderCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> SuccessResponse[ReminderResponse]:
    """
    Create a reminder for a specific contact.
    Example: "Follow up in 2 hours" - set remind_at to current time + 2 hours.
    """
    # Verify contact belongs to user
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    db_reminder = Reminder(
        **reminder.model_dump(),
        contact_id=contact_id
    )
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    
    return {"success": True, "message": "Reminder created successfully", "data": db_reminder}


@router.get("/contacts/{contact_id}/reminders")
def get_contact_reminders(
    contact_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_completed: bool = Query(False, description="Include completed reminders"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> ListResponse[ReminderResponse]:
    """
    Get all reminders for a specific contact.
    """
    # Verify contact belongs to user
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    query = db.query(Reminder).filter(Reminder.contact_id == contact_id)
    
    if not include_completed:
        query = query.filter(Reminder.is_completed == False)
    
    reminders = query.order_by(Reminder.remind_at).offset(skip).limit(limit).all()
    
    if not reminders:
        return {"success": True, "message": "No reminders found", "data": [], "count": 0}
    return {"success": True, "message": "Reminders retrieved successfully", "data": reminders, "count": len(reminders)}


@router.get("/upcoming")
def get_upcoming_reminders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> ListResponse[ReminderResponse]:
    """
    Get all upcoming (not completed) reminders for the current user.
    Sorted by reminder time.
    """
    reminders = db.query(Reminder).join(Contact).filter(
        Contact.user_id == current_user.id,
        Reminder.is_completed == False
    ).order_by(Reminder.remind_at).offset(skip).limit(limit).all()
    
    if not reminders:
        return {"success": True, "message": "No reminders found", "data": [], "count": 0}
    return {"success": True, "message": "Reminders retrieved successfully", "data": reminders, "count": len(reminders)}


@router.get("/due")
def get_due_reminders(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> ListResponse[ReminderResponse]:
    """
    Get all reminders that are due (remind_at <= current time) and not completed.
    """
    now = datetime.utcnow()
    
    reminders = db.query(Reminder).join(Contact).filter(
        Contact.user_id == current_user.id,
        Reminder.is_completed == False,
        Reminder.remind_at <= now
    ).order_by(Reminder.remind_at).all()
    
    if not reminders:
        return {"success": True, "message": "No reminders found", "data": [], "count": 0}
    return {"success": True, "message": "Reminders retrieved successfully", "data": reminders, "count": len(reminders)}


@router.get("/reminders/{reminder_id}")
def get_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> SuccessResponse[ReminderResponse]:
    """
    Get a specific reminder by ID.
    """
    reminder = db.query(Reminder).join(Contact).filter(
        Reminder.id == reminder_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    return {"success": True, "message": "Reminder retrieved successfully", "data": reminder}


@router.put("/reminders/{reminder_id}")
def update_reminder(
    reminder_id: int,
    reminder_update: ReminderUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> SuccessResponse[ReminderResponse]:
    """
    Update a reminder's information.
    """
    reminder = db.query(Reminder).join(Contact).filter(
        Reminder.id == reminder_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    # Update reminder fields
    update_data = reminder_update.model_dump(exclude_unset=True)
    
    # If remind_at is being updated, reset notification_sent so the notification
    # will be sent again at the new time
    if "remind_at" in update_data:
        reminder.notification_sent = False
    
    for field, value in update_data.items():
        setattr(reminder, field, value)
    
    db.commit()
    db.refresh(reminder)
    
    return {"success": True, "message": "Reminder updated successfully", "data": reminder}


@router.post("/reminders/{reminder_id}/complete")
def complete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> SuccessResponse[ReminderResponse]:
    """
    Mark a reminder as completed.
    """
    reminder = db.query(Reminder).join(Contact).filter(
        Reminder.id == reminder_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    reminder.is_completed = True
    db.commit()
    db.refresh(reminder)
    
    return {"success": True, "message": "Reminder completed successfully", "data": reminder}


@router.delete("/reminders/{reminder_id}")
def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a reminder.
    """
    reminder = db.query(Reminder).join(Contact).filter(
        Reminder.id == reminder_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    db.delete(reminder)
    db.commit()
    
    return {"success": True, "message": "Reminder deleted successfully"}
