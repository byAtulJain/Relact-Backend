from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Folder, Contact
from app.schemas import FolderCreate, FolderUpdate, FolderResponse, SuccessResponse, ListResponse
from app.auth import get_current_active_user

router = APIRouter(prefix="/folders", tags=["Folders"])


@router.post("/")
def create_folder(
    folder: FolderCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new folder to organize contacts.
    """
    # Check if folder with same name already exists for this user
    existing_folder = db.query(Folder).filter(
        Folder.user_id == current_user.id,
        Folder.name == folder.name
    ).first()
    
    if existing_folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder with this name already exists"
        )
    
    db_folder = Folder(
        **folder.model_dump(),
        user_id=current_user.id
    )
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    
    return {"success": True, "message": "Folder created successfully", "data": db_folder}


@router.get("/")
def get_folders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all folders for the current user with contact counts.
    """
    folders = db.query(Folder).filter(
        Folder.user_id == current_user.id
    ).order_by(Folder.name).offset(skip).limit(limit).all()
    
    if not folders:
        return {"success": True, "message": "No folders found", "data": [], "count": 0}
    
    # Add contact count to each folder
    folders_with_count = []
    for folder in folders:
        folder_dict = {
            "id": folder.id,
            "user_id": folder.user_id,
            "name": folder.name,
            "description": folder.description,
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
            "contact_count": db.query(Contact).filter(Contact.folders.any(Folder.id == folder.id)).count()
        }
        folders_with_count.append(folder_dict)
    
    return {"success": True, "message": "Folders retrieved successfully", "data": folders_with_count, "count": len(folders_with_count)}


@router.get("/{folder_id}")
def get_folder(
    folder_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific folder by ID.
    """
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    return {"success": True, "message": "Folder retrieved successfully", "data": folder}


@router.put("/{folder_id}")
def update_folder(
    folder_id: int,
    folder_update: FolderUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update a folder's information.
    """
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    # Check if new name conflicts with existing folder
    if folder_update.name:
        existing_folder = db.query(Folder).filter(
            Folder.user_id == current_user.id,
            Folder.name == folder_update.name,
            Folder.id != folder_id
        ).first()
        
        if existing_folder:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Folder with this name already exists"
            )
    
    # Update folder fields
    update_data = folder_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(folder, field, value)
    
    db.commit()
    db.refresh(folder)
    
    return {"success": True, "message": "Folder updated successfully", "data": folder}


@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    remove_contacts: bool = Query(False, description="If true, delete all contacts in the folder. If false, just remove contacts from this folder."),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a folder. 
    By default, contacts are just removed from this folder (association removed).
    Set remove_contacts=true to delete the actual contacts.
    """
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    if remove_contacts:
        # Delete all contacts in the folder
        # Find contacts that are ONLY in this folder? Or in this folder at all?
        # Typically "delete contacts within" implies delete contacts associated with it.
        # But for M2M, this might be dangerous if they are in other folders.
        # Let's assume user wants to delete contacts found in this folder.
        contacts = db.query(Contact).filter(Contact.folders.any(Folder.id == folder_id)).all()
        for contact in contacts:
            db.delete(contact)
    else:
        # Just deleting the folder will automatically remove associations due to secondary table cascade or SQLAlchemy handling,
        # but let's be explicit if needed. Actually SQLAlchemy handles M2M cleanup on delete usually.
        # We don't need to manually update Contact.folder_id = None anymore.
        pass
    
    db.delete(folder)
    db.commit()
    
    return {"success": True, "message": "Folder deleted successfully"}


@router.put("/{folder_id}/contacts/{contact_id}")
def add_contact_to_folder(
    folder_id: int,
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Add an existing contact to a folder.
    """
    # Verify folder exists and belongs to current user
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    # Verify contact exists and belongs to current user
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    # Check if already in folder
    if folder in contact.folders:
        return {
            "success": True, 
            "message": "Contact is already in this folder",
            "data": contact
        }
    
    # Add contact to folder
    contact.folders.append(folder)
    db.commit()
    db.refresh(contact)
    
    # Manually decrypt phone before returning
    from app.encryption import decrypt_phone
    if contact.phone:
        contact.phone = decrypt_phone(contact.phone)
    
    return {
        "success": True,
        "message": f"Contact '{contact.name}' added to folder '{folder.name}' successfully",
        "data": contact
    }


@router.delete("/{folder_id}/contacts/{contact_id}")
def remove_contact_from_folder(
    folder_id: int,
    contact_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Remove a contact from a folder.
    """
    # Verify folder exists and belongs to current user
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    # Verify contact exists and belongs to current user
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    # Check if contact is in this folder
    if folder not in contact.folders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact is not in this folder"
        )
    
    # Remove contact from folder
    contact.folders.remove(folder)
    db.commit()
    
    return {
        "success": True,
        "message": "Contact removed from folder successfully",
        "data": {
            "folder_id": folder_id,
            "contact_id": contact_id
        }
    }


@router.post("/{folder_id}/contacts/bulk")
async def bulk_add_contacts_to_folder(
    folder_id: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Add multiple contacts to a folder at once.
    """
    # Parse JSON body
    try:
        body = await request.json()
        contact_ids = body.get('contact_ids', [])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {str(e)}")
    
    if not contact_ids or not isinstance(contact_ids, list):
        raise HTTPException(status_code=400, detail="contact_ids must be a non-empty list")
    
    # Verify folder exists and belongs to user
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Add contacts to folder
    success_count = 0
    failed_count = 0
    
    for contact_id in contact_ids:
        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        ).first()
        
        if contact:
            if folder not in contact.folders:
                contact.folders.append(folder)
                success_count += 1
        else:
            failed_count += 1
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Added {success_count} contacts to folder '{folder.name}'",
        "data": {
            "folder_id": folder_id,
            "folder_name": folder.name,
            "total_requested": len(contact_ids),
            "successfully_added": success_count,
            "failed_count": failed_count
        }
    }


@router.get("/{folder_id}/contacts")
def get_folder_contacts(
    folder_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all contacts in a specific folder.
    """
    # Verify folder exists and belongs to current user
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    # Get all contacts in the folder
    contacts = db.query(Contact).filter(
        Contact.folders.any(Folder.id == folder_id),
        Contact.user_id == current_user.id
    ).order_by(Contact.created_at.desc()).offset(skip).limit(limit).all()
    
    # Decrypt phones
    from app.encryption import decrypt_phone
    for contact in contacts:
        if contact.phone:
            contact.phone = decrypt_phone(contact.phone)
            
    if not contacts:
        return {
            "success": True,
            "message": f"No contacts found in folder '{folder.name}'",
            "data": [],
            "count": 0,
            "folder": {
                "id": folder.id,
                "name": folder.name,
                "description": folder.description
            }
        }
    
    return {
        "success": True,
        "message": f"Contacts retrieved from folder '{folder.name}' successfully",
        "data": contacts,
        "count": len(contacts),
        "folder": {
            "id": folder.id,
            "name": folder.name,
            "description": folder.description
        }
    }


@router.get("/{folder_id}/contacts-count")
def get_folder_contacts_count(
    folder_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the number of contacts in a folder.
    """
    folder = db.query(Folder).filter(
        Folder.id == folder_id,
        Folder.user_id == current_user.id
    ).first()
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    count = db.query(Contact).filter(Contact.folders.any(Folder.id == folder_id)).count()
    
    return {
        "folder_id": folder_id,
        "folder_name": folder.name,
        "contacts_count": count
    }
