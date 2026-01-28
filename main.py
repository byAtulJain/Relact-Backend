from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.routes import auth, contacts, folders, notes, reminders, device_tokens, notifications, app_info, admin
from app.logger import logger
from app.services.contact_scheduler import contact_scheduler
import traceback

# Create database tables
try:
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")
    logger.error(traceback.format_exc())

app = FastAPI(
    title="Relact - Smart Contact Manager API",
    description="Backend API for Relact Smart Contact Manager with tiered contact storage, reminders, and folder organization",
    version="1.0.0"
)

# Startup event - Start contact scheduler
@app.on_event("startup")
async def startup_event():
    contact_scheduler.start()
    logger.info("Application started with contact scheduler")

# Shutdown event - Stop contact scheduler
@app.on_event("shutdown")
async def shutdown_event():
    contact_scheduler.shutdown()
    logger.info("Application shutdown complete")

logger.info("Starting Relact Smart Contact Manager API...")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}")
    logger.error(f"Request: {request.method} {request.url}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "type": type(exc).__name__
        }
    )

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
logger.info("Registering routes...")
app.include_router(auth.router)
app.include_router(contacts.router)
app.include_router(folders.router)
app.include_router(notes.router)
app.include_router(reminders.router)
app.include_router(device_tokens.router)
app.include_router(notifications.router)
app.include_router(app_info.router)
app.include_router(admin.router)
logger.info("All routes registered successfully")

# Mount static files for serving uploaded images
import os
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)
    logger.info(f"Created uploads directory: {uploads_dir}")

app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
logger.info("Static files mounted for /uploads")


@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    return {
        "success": True,
        "message": "Welcome to Relact - Smart Contact Manager API",
        "data": {
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/health")
def health_check():
    logger.info("Health check endpoint accessed")
    return {"success": True, "message": "API is healthy", "data": {"status": "healthy"}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
