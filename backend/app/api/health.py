"""
Health Check Endpoints
System health and status endpoints
"""

from fastapi import APIRouter
from app.services import mqtt_manager
from app.utils import logger

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check():
    """Get overall system health"""
    return {
        "status": "healthy",
        "services": {
            "mqtt": "connected" if mqtt_manager.connected else "disconnected",
            "api": "running"
        }
    }


@router.get("/ready")
async def readiness_check():
    """Check if service is ready to handle requests"""
    mqtt_ready = mqtt_manager.connected
    
    return {
        "ready": mqtt_ready,
        "details": {
            "mqtt_connected": mqtt_ready
        }
    }


@router.get("/live")
async def liveness_check():
    """Check if service is still alive"""
    return {
        "alive": True
    }
