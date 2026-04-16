"""
Device API Endpoints
REST API for device operations
Replaces device management endpoints from RATS.c
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List, Optional
from app.schemas import Device, DeviceCreate, DeviceUpdate, DeviceList
from app.services import device_manager
from app.utils import logger

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=DeviceList)
async def list_devices(status: Optional[str] = None):
    """
    Get list of all devices
    
    Query Parameters:
        status: Optional status filter (online, offline, unknown)
    """
    try:
        devices = device_manager.list_devices(status=status)
        return DeviceList(devices=devices, total=len(devices))
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list devices"
        )


@router.get("/{device_id}", response_model=Device)
async def get_device(device_id: str):
    """Get device by ID"""
    device = device_manager.get_device(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )
    return device


@router.post("", response_model=Device, status_code=status.HTTP_201_CREATED)
async def create_device(device: DeviceCreate):
    """Create a new device"""
    try:
        new_device = device_manager.add_device(
            name=device.name,
            mac=device.mac_address,
            ip=device.ip_address,
            device_type=device.device_type,
            location=device.location
        )
        return new_device
    except Exception as e:
        logger.error(f"Error creating device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create device"
        )


@router.put("/{device_id}", response_model=Device)
async def update_device(device_id: str, device_update: DeviceUpdate):
    """Update device information"""
    try:
        existing = device_manager.get_device(device_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device {device_id} not found"
            )
        
        updated = device_manager.update_device(
            device_id,
            **device_update.dict(exclude_unset=True)
        )
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update device"
        )


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: str):
    """Delete a device"""
    try:
        if not device_manager.delete_device(device_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device {device_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete device"
        )


@router.get("/count", response_model=dict)
async def get_device_count():
    """Get total device count"""
    try:
        count = device_manager.get_device_count()
        online = len(device_manager.get_online_devices())
        return {
            "total": count,
            "online": online,
            "offline": count - online
        }
    except Exception as e:
        logger.error(f"Error getting device count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get device count"
        )
