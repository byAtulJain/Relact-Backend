from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional
from datetime import datetime
import os
import shutil
import json
from pathlib import Path
from app.database import get_db
from app.models import User, Contact, Folder
from app.schemas import (
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    ContactListResponse,
    ListResponse,
    SuccessResponse,
    ContactFolderStatus
)
from app.encryption import encrypt_phone, decrypt_phone
from app.auth import get_current_active_user

router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.post("/")
async def create_contact(
    name: str = Form(..., min_length=1, max_length=100),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    contact_type: str = Form("permanent"),
    folder_ids_str: Optional[str] = Form(None, alias="folder_ids"),
    delete_at_display: Optional[str] = Form(None, description="Format: dd/mm/yyyy hh:mm AM/PM"),
    profile_photo: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new contact using form-data (supports file upload for profile photo).
    Automatically checks for duplicates based on name and phone number.
    For temporary contacts, provide delete_at_display in format: dd/mm/yyyy hh:mm AM/PM
    """
    # Parse folder_ids
    folder_ids = []
    if folder_ids_str:
        try:
            parsed = json.loads(folder_ids_str)
            if isinstance(parsed, list):
                folder_ids = parsed
            elif isinstance(parsed, int):
                folder_ids = [parsed]
        except:
            pass
            
    # Handle profile photo upload
    profile_photo_path = None
    if profile_photo and profile_photo.filename:
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads/profile_photos")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = Path(profile_photo.filename).suffix
        unique_filename = f"{current_user.id}_{datetime.now().timestamp()}{file_extension}"
        file_path = upload_dir / unique_filename
        
        # Save file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(profile_photo.file, buffer)
        
        # Convert path to use forward slashes for URL compatibility and add leading slash
        profile_photo_path = '/' + str(file_path).replace('\\', '/')
    
    # Parse delete_at_display if provided
    # Parse delete_at_display if provided
    delete_at = None
    if delete_at_display:
        try:
            from datetime import datetime as dt, timedelta, timezone
            IST = timezone(timedelta(hours=5, minutes=30))
            
            # Parse as naive (which implies IST in user's mind)
            naive_dt = dt.strptime(delete_at_display, "%d/%m/%Y %I:%M %p")
            
            # Set to IST
            ist_dt = naive_dt.replace(tzinfo=IST)
            
            # Convert to UTC for storage
            delete_at = ist_dt.astimezone(timezone.utc)
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid delete_at_display format. Use: dd/mm/yyyy hh:mm AM/PM (e.g., 25/12/2026 02:30 PM). Error: {str(e)}"
            )
    
    # Check for duplicate contact
    existing_contacts = db.query(Contact).filter(
        Contact.user_id == current_user.id
    ).all()
    
    for existing in existing_contacts:
        is_duplicate = False
        match_reasons = []
        
        if name and existing.name == name:
            is_duplicate = True
            match_reasons.append(f"name '{name}'")
        
        if phone and existing.phone:
            decrypted_existing = decrypt_phone(existing.phone)
            if decrypted_existing == phone:
                is_duplicate = True
                match_reasons.append(f"phone '{phone}'")
        
        if is_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contact already exists with same {' and '.join(match_reasons)}"
            )
            
    # Create contact without folders first
    db_contact = Contact(
        name=name,
        phone=phone,
        email=email,
        profile_photo=profile_photo_path,
        contact_type=contact_type,
        delete_at=delete_at,
        user_id=current_user.id
    )
    
    # Associate folders if provided
    if folder_ids:
        folders = db.query(Folder).filter(
            Folder.id.in_(folder_ids),
            Folder.user_id == current_user.id
        ).all()
        
        if len(folders) != len(folder_ids):
            # Some folders not found or don't belong to user
            # We can either error or just add valid ones.
            # Let's error for stricter consistency if needed, or just add found.
            # For robust API, just add valid ones.
            pass
            
        db_contact.folders = folders

    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    
    # Manually decrypt phone after refresh
    if db_contact.phone:
        db_contact.phone = decrypt_phone(db_contact.phone)
    
    return {"success": True, "message": "Contact created successfully", "data": db_contact}


@router.get("/")
def get_contacts(
    folder_id: Optional[int] = Query(None, description="Filter by folder ID"),
    contact_type: Optional[str] = Query(None, description="Filter by contact type (temporary/permanent)"),
    search: Optional[str] = Query(None, description="Search by name, phone, email, or company"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all contacts for the current user with optional filters.
    """
    query = db.query(Contact).filter(Contact.user_id == current_user.id)
    
    # Apply filters
    if folder_id is not None:
        query = query.filter(Contact.folders.any(Folder.id == folder_id))
    
    if contact_type:
        query = query.filter(Contact.contact_type == contact_type)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Contact.name.ilike(search_pattern),
                Contact.phone.ilike(search_pattern),
                Contact.email.ilike(search_pattern),
            )
        )
    
    # Order by creation date (newest first)
    query = query.order_by(Contact.created_at.desc())
    
    # Apply pagination
    contacts = query.offset(skip).limit(limit).all()
    
    # Decrypt phones
    for contact in contacts:
        if contact.phone:
            contact.phone = decrypt_phone(contact.phone)
            
    if not contacts:
        return {"success": True, "message": "No contacts found", "data": [], "count": 0}
    
    return {"success": True, "message": "Contacts retrieved successfully", "data": contacts, "count": len(contacts)}


@router.get("/without-folder")
def get_contacts_without_folder(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all contacts that are not in any folder.
    """
    contacts = db.query(Contact).filter(
        Contact.user_id == current_user.id,
        ~Contact.folders.any()
    ).order_by(Contact.created_at.desc()).offset(skip).limit(limit).all()
    
    # Decrypt phones
    for contact in contacts:
        if contact.phone:
            contact.phone = decrypt_phone(contact.phone)
            
    if not contacts:
        return {"success": True, "message": "No contacts without folder", "data": [], "count": 0}
    
    return {"success": True, "message": "Contacts retrieved successfully", "data": contacts, "count": len(contacts)}


@router.get("/favorites")
def get_favorite_contacts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all favorite contacts for the current user."""
    contacts = db.query(Contact).filter(
        Contact.user_id == current_user.id,
        Contact.is_favorite == True
    ).order_by(Contact.name).all()
    
    from app.encryption import decrypt_phone
    for contact in contacts:
        if contact.phone:
            contact.phone = decrypt_phone(contact.phone)
    
    return {
        "success": True,
        "message": "Favorite contacts retrieved successfully",
        "data": contacts
    }


@router.put("/{contact_id}/favorite")
def toggle_favorite(
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Toggle favorite status for a contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    contact.is_favorite = not contact.is_favorite
    db.commit()
    db.refresh(contact)
    
    message = "Contact marked as favorite" if contact.is_favorite else "Contact removed from favorites"
    
    return {
        "success": True,
        "message": message,
        "data": {
            "id": contact.id,
            "is_favorite": contact.is_favorite
        }
    }


@router.put("/{contact_id}/make-permanent")
def make_contact_permanent(
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Convert a temporary contact to permanent by removing delete_at."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    if contact.contact_type != "temporary":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact is already permanent"
        )
    
    # Convert to permanent
    contact.contact_type = "permanent"
    contact.delete_at = None
    db.commit()
    db.refresh(contact)
    
    # Prepare response
    contact_data = {
        "id": contact.id,
        "name": contact.name,
        "phone": decrypt_phone(contact.phone),
        "email": contact.email,
        "profile_photo": contact.profile_photo,
        "contact_type": contact.contact_type,
        "delete_at": None,
        "is_favorite": contact.is_favorite,
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
        "folders": [
            {
                "id": folder.id,
                "name": folder.name,
                "color": folder.color,
                "icon": folder.icon
            }
            for folder in contact.folders
        ]
    }
    
    return {
        "success": True,
        "message": "Contact converted to permanent successfully",
        "data": contact_data
    }


@router.get("/{contact_id}")
def get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific contact by ID with all details (notes and reminders).
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    return {"success": True, "message": "Contact retrieved successfully", "data": contact}


@router.put("/{contact_id}")
async def update_contact(
    contact_id: int,
    name: Optional[str] = Form(None, min_length=1, max_length=100),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    contact_type: Optional[str] = Form(None),
    folder_ids_str: Optional[str] = Form(None, alias="folder_ids"),
    delete_at_display: Optional[str] = Form(None, description="Format: dd/mm/yyyy hh:mm AM/PM"),
    profile_photo: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update a contact's details.
    """
    # Parse folder_ids
    folder_ids = None
    if folder_ids_str is not None:
        try:
            parsed = json.loads(folder_ids_str)
            if isinstance(parsed, list):
                folder_ids = parsed
            elif isinstance(parsed, int):
                folder_ids = [parsed]
            else:
                 folder_ids = []
        except:
            folder_ids = []
            
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    # Handle profile photo upload
    if profile_photo and profile_photo.filename:
        # Delete old photo if exists
        if contact.profile_photo and os.path.exists(contact.profile_photo):
            os.remove(contact.profile_photo)
        
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads/profile_photos")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = Path(profile_photo.filename).suffix
        unique_filename = f"{current_user.id}_{datetime.now().timestamp()}{file_extension}"
        file_path = upload_dir / unique_filename
        
        # Save file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(profile_photo.file, buffer)
        
        # Convert path to use forward slashes for URL compatibility and add leading slash
        contact.profile_photo = '/' + str(file_path).replace('\\', '/')
    
    # Parse delete_at_display if provided
    # Parse delete_at_display if provided
    if delete_at_display:
        try:
            from datetime import datetime as dt, timedelta, timezone
            IST = timezone(timedelta(hours=5, minutes=30))
            
            # Parse as naive
            naive_dt = dt.strptime(delete_at_display, "%d/%m/%Y %I:%M %p")
            
            # Set to IST
            ist_dt = naive_dt.replace(tzinfo=IST)
            
            # Convert to UTC for storage
            contact.delete_at = ist_dt.astimezone(timezone.utc)
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid delete_at_display format. Use: dd/mm/yyyy hh:mm AM/PM (e.g., 25/12/2026 02:30 PM). Error: {str(e)}"
            )
    
    # Check for duplicate contact if name or phone is being updated
    if name or phone:
        existing_contacts = db.query(Contact).filter(
            Contact.user_id == current_user.id,
            Contact.id != contact_id
        ).all()
        
        for existing in existing_contacts:
            is_duplicate = False
            match_reasons = []
            
            if name and existing.name == name:
                is_duplicate = True
                match_reasons.append(f"name '{name}'")
            
            if phone and existing.phone:
                decrypted_existing = decrypt_phone(existing.phone)
                if decrypted_existing == phone:
                    is_duplicate = True
                    match_reasons.append(f"phone '{phone}'")
            
            if is_duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Contact already exists with same {' and '.join(match_reasons)}"
                )
    
    # Update contact fields
    if name is not None:
        contact.name = name
    if phone is not None:
        contact.phone = phone
    if email is not None:
        contact.email = email
    if contact_type is not None:
        contact.contact_type = contact_type
        
    # Update foldersM2M
    if folder_ids is not None:
        # Validate folders
        folders = db.query(Folder).filter(
            Folder.id.in_(folder_ids),
            Folder.user_id == current_user.id
        ).all()
        # Update relationship
        contact.folders = folders
    
    db.commit()
    db.refresh(contact)
    
    # Manually decrypt phone after refresh
    if contact.phone:
        contact.phone = decrypt_phone(contact.phone)
    
    return {"success": True, "message": "Contact updated successfully", "data": contact}



@router.delete("/{contact_id}")
def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a contact. This will also delete all associated notes and reminders.
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    db.delete(contact)
    db.commit()
    
    return {"success": True, "message": "Contact deleted successfully"}


@router.post("/cleanup-expired")
def cleanup_expired_contacts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete all temporary contacts that have passed their deletion time.
    """
    now = datetime.utcnow()
    
    expired_contacts = db.query(Contact).filter(
        Contact.user_id == current_user.id,
        Contact.delete_at != None,
        Contact.delete_at <= now
    ).all()
    
    count = len(expired_contacts)
    
    for contact in expired_contacts:
        db.delete(contact)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Deleted {count} expired contact(s)" if count > 0 else "No expired contacts found",
        "data": {"count": count}
    }


@router.get("/{contact_id}/folders", response_model=List[ContactFolderStatus])
def get_contact_folders(
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all folders with assignment status for a specific contact.
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    all_folders = db.query(Folder).filter(Folder.user_id == current_user.id).all()
    
    # Get assigned folders
    # Accessing contact.folders triggers the lazy load within session
    assigned_folders = contact.folders
    assigned_ids = {f.id for f in assigned_folders}
    
    result = []
    for folder in all_folders:
        result.append({
            "folder": folder,
            "is_assigned": folder.id in assigned_ids
        })
        
    return result
