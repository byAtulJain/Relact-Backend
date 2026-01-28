"""
Encryption utilities for sensitive contact data (phone numbers).
Uses Fernet symmetric encryption from cryptography library.
"""

from cryptography.fernet import Fernet
from app.config import get_settings
import base64
import hashlib

settings = get_settings()

def get_cipher():
    """Get Fernet cipher instance using the encryption key from settings."""
    # Derive a proper 32-byte key from the encryption key
    key = settings.encryption_key.encode('utf-8')
    # Use SHA256 to get a 32-byte key, then base64 encode it for Fernet
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
    return Fernet(derived_key)

def encrypt_phone(phone_number: str) -> str:
    """
    Encrypt a phone number.
    
    Args:
        phone_number: Plain text phone number
        
    Returns:
        Encrypted phone number (base64 encoded string)
    """
    if not phone_number:
        return None
    
    cipher = get_cipher()
    encrypted = cipher.encrypt(phone_number.encode('utf-8'))
    return encrypted.decode('utf-8')

def decrypt_phone(encrypted_phone: str) -> str:
    """
    Decrypt a phone number.
    
    Args:
        encrypted_phone: Encrypted phone number (base64 encoded string)
        
    Returns:
        Decrypted plain text phone number
    """
    if not encrypted_phone:
        return None
    
    try:
        cipher = get_cipher()
        decrypted = cipher.decrypt(encrypted_phone.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception as e:
        # If decryption fails, return the original value
        # This handles migration from unencrypted data
        return encrypted_phone

def generate_encryption_key() -> str:
    """Generate a new encryption key for use in .env file."""
    return Fernet.generate_key().decode('utf-8')
