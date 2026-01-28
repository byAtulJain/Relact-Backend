from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app.models import User, Note, Contact
from app.schemas import NoteCreate, NoteUpdate, NoteResponse, SuccessResponse, ListResponse
from app.auth import get_current_active_user

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.get("/notes")
def get_all_notes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all notes for the current user across all contacts.
    """
    notes = db.query(Note).join(Contact).filter(
        Contact.user_id == current_user.id
    ).order_by(Note.created_at.desc()).offset(skip).limit(limit).all()
    
    if not notes:
        return {"success": True, "message": "No notes found", "data": [], "count": 0}
    return {"success": True, "message": "Notes retrieved successfully", "data": notes, "count": len(notes)}


@router.post("/contacts/{contact_id}/notes")
def create_note(
    contact_id: int,
    note: NoteCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a note for a specific contact.
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
    
    db_note = Note(
        **note.model_dump(),
        contact_id=contact_id
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    
    return {"success": True, "message": "Note created successfully", "data": db_note}


@router.get("/contacts/{contact_id}/notes")
def get_contact_notes(
    contact_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all notes for a specific contact.
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
    
    notes = db.query(Note).filter(
        Note.contact_id == contact_id
    ).order_by(Note.created_at.desc()).offset(skip).limit(limit).all()
    
    if not notes:
        return {"success": True, "message": "No notes found for this contact", "data": [], "count": 0}
    return {"success": True, "message": "Notes retrieved successfully", "data": notes, "count": len(notes)}


@router.get("/notes/{note_id}")
def get_note(
    note_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific note by ID.
    """
    note = db.query(Note).join(Contact).filter(
        Note.id == note_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    return {"success": True, "message": "Note retrieved successfully", "data": note}


@router.put("/notes/{note_id}")
def update_note(
    note_id: int,
    note_update: NoteUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update a note's content.
    """
    note = db.query(Note).join(Contact).filter(
        Note.id == note_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    note.content = note_update.content
    db.commit()
    db.refresh(note)
    
    return {"success": True, "message": "Note updated successfully", "data": note}


@router.delete("/notes/{note_id}")
def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a note.
    """
    note = db.query(Note).join(Contact).filter(
        Note.id == note_id,
        Contact.user_id == current_user.id
    ).first()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    db.delete(note)
    db.commit()
    
    return {"success": True, "message": "Note deleted successfully"}
