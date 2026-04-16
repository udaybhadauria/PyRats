"""
RATS Backend - Main FastAPI Application
Replaces the C-based RATS_Server implementation
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
import sys

from app.settings import settings
from app.utils import logger
from app.services import mqtt_manager
from app.api import devices_router, tests_router, health_router, system_router


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Connect to MQTT broker
    mqtt_connected = await mqtt_manager.connect()
    if mqtt_connected:
        logger.info("MQTT broker connected successfully")
    else:
        logger.warning("Failed to connect to MQTT broker - continuing with degraded mode")
    
    # Subscribe to device data topic
    mqtt_manager.subscribe(
        settings.MQTT_DEVICE_DATA_TOPIC,
        lambda topic, payload: logger.debug(f"Received device data on {topic}")
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down RATS backend")
    await mqtt_manager.disconnect()
    logger.info("MQTT broker disconnected")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Robust Automated Test System - Python Backend",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueErrors"""
    logger.error(f"ValueError: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(health_router)
app.include_router(devices_router)
app.include_router(tests_router)
app.include_router(system_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/api/docs",
        "health": "/api/health"
    }


@app.get("/api")
async def api_info():
    """API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "endpoints": {
            "health": "/api/health",
            "devices": "/api/devices",
            "tests": "/api/tests",
            "docs": "/api/docs",
            "redoc": "/api/redoc"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )
