# Relact - Smart Contact Manager API

A FastAPI backend for the Relact Smart Contact Manager application with JWT authentication, PostgreSQL database, and comprehensive contact management features.

## Features

- **User Authentication**: JWT token-based authentication with 1-year token expiration
- **Contact Management**: 
  - Create, read, update, delete contacts
  - Temporary and permanent contact types
  - Auto-deletion for temporary contacts
  - Duplicate detection
- **Folder Organization**: Group contacts into folders
- **Notes**: Add notes to contacts (burner notes)
- **Reminders**: Set time-based reminders for follow-ups
- **Privacy-First**: Local database storage with optional cloud sync

## Tech Stack

- **Framework**: FastAPI 0.109.0
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT (JSON Web Tokens) with 365-day expiration
- **Password Hashing**: bcrypt via passlib
- **Validation**: Pydantic v2

## Project Structure

```
Relact – Smart Contact Manager/
├── app/
│   ├── __init__.py
│   ├── config.py           # Application configuration
│   ├── database.py         # Database connection setup
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   ├── auth.py             # Authentication utilities
│   └── routes/
│       ├── __init__.py
│       ├── auth.py         # Authentication endpoints
│       ├── contacts.py     # Contact management endpoints
│       ├── folders.py      # Folder management endpoints
│       ├── notes.py        # Notes management endpoints
│       └── reminders.py    # Reminders management endpoints
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## Setup Instructions

### 1. Prerequisites

- Python 3.8+
- PostgreSQL 12+

### 2. Clone and Install

```bash
cd "d:\API Project\Relact – Smart Contact Manager"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Setup

Create a PostgreSQL database:

```sql
CREATE DATABASE relact_db;
```

### 4. Environment Configuration

Create a `.env` file from the example:

```bash
copy .env.example .env
```

Edit `.env` with your configuration:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/relact_db
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=365
```

**Important**: Generate a secure SECRET_KEY:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 5. Run the Application

```bash
# Development mode with auto-reload
uvicorn main:app --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login with username or email and get JWT token
- `POST /auth/logout` - Logout and blacklist token
- `GET /auth/me` - Get current user info

### Contacts
- `POST /contacts/` - Create new contact (with automatic duplicate checking)
- `GET /contacts/` - List all contacts (with filters)
- `GET /contacts/without-folder` - List contacts without folder
- `GET /contacts/{contact_id}` - Get contact details
- `PUT /contacts/{contact_id}` - Update contact (with automatic duplicate checking)
- `DELETE /contacts/{contact_id}` - Delete contact
- `POST /contacts/cleanup-expired` - Delete expired temporary contacts

### Folders
- `POST /folders/` - Create folder
- `GET /folders/` - List all folders
- `GET /folders/{folder_id}` - Get folder details
- `PUT /folders/{folder_id}` - Update folder
- `DELETE /folders/{folder_id}` - Delete folder
- `PUT /folders/{folder_id}/contacts/{contact_id}` - Add contact to folder
- `GET /folders/{folder_id}/contacts` - Get all contacts in folder
- `GET /folders/{folder_id}/contacts-count` - Get contact count

### Notes
- `POST /notes/contacts/{contact_id}/notes` - Add note to contact
- `GET /notes/contacts/{contact_id}/notes` - Get contact notes
- `GET /notes/notes/{note_id}` - Get specific note
- `PUT /notes/notes/{note_id}` - Update note
- `DELETE /notes/notes/{note_id}` - Delete note

### Reminders
- `POST /reminders/contacts/{contact_id}/reminders` - Create reminder
- `GET /reminders/contacts/{contact_id}/reminders` - Get contact reminders
- `GET /reminders/upcoming` - Get all upcoming reminders
- `GET /reminders/due` - Get due reminders
- `GET /reminders/reminders/{reminder_id}` - Get specific reminder
- `PUT /reminders/reminders/{reminder_id}` - Update reminder
- `POST /reminders/reminders/{reminder_id}/complete` - Mark as completed
- `DELETE /reminders/reminders/{reminder_id}` - Delete reminder

## Usage Examples

### 1. Register a User

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "john_doe",
    "password": "secure_password123"
  }'
```

### 2. Login

**Login with username:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "secure_password123"
  }'
```

**Login with email:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "secure_password123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. Create a Temporary Contact

```bash
curl -X POST "http://localhost:8000/contacts/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "phone": "+1234567890",
    "email": "john@example.com",
    "profile_photo": "https://example.com/photos/john.jpg",
    "contact_type": "temporary",
    "delete_at_display": "25/12/2026 02:30 PM"
  }'
```

**Note**: For temporary contacts, use `delete_at_display` in format: `dd/mm/yyyy hh:mm AM/PM`

### 4. Add Contact to Folder

```bash
curl -X PUT "http://localhost:8000/folders/1/contacts/5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Get All Contacts in a Folder

```bash
curl -X GET "http://localhost:8000/folders/1/contacts?skip=0&limit=100" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 6. Create a Reminder

```bash
curl -X POST "http://localhost:8000/reminders/contacts/1/reminders" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Follow up call",
    "description": "Discuss project proposal",
    "remind_at": "2026-01-12T14:00:00Z"
  }'
```

## Database Models

### User
- Email, username, password (hashed)
- Relationships: contacts, folders, tokens

### Contact
- Name, phone, email, company, position, address
- Contact type: temporary/permanent
- Delete timestamp for temporary contacts
- Relationships: folder, notes, reminders

### Folder
- Name, description
- Organizes multiple contacts

### Note
- Content
- Linked to contact

### Reminder
- Title, description, remind_at timestamp
- Completion status
- Linked to contact

## Security Features

- **Password Hashing**: bcrypt with salt
- **JWT Tokens**: 365-day expiration (configurable)
- **Token Blacklisting**: Logout invalidates tokens
- **CORS Protection**: Configurable origins
- **SQL Injection Protection**: SQLAlchemy ORM
- **Input Validation**: Pydantic schemas

## Development

### Database Migrations (Optional)

If you want to use Alembic for migrations:

```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

## Production Deployment

1. **Set strong SECRET_KEY**
2. **Configure PostgreSQL** with proper credentials
3. **Update CORS origins** to your frontend domain
4. **Use HTTPS** in production
5. **Set up reverse proxy** (nginx/Caddy)
6. **Enable database backups**
7. **Set up logging and monitoring**

## License

This project is part of the Relact Smart Contact Manager application.

## Support

For issues and questions, please refer to the project documentation or contact the development team.
