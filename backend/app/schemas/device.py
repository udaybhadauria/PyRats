"""
Pydantic schemas for device operations
Data validation and serialization
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DeviceBase(BaseModel):
    """Base device information"""
    name: str = Field(..., min_length=1, description="Device name")
    mac_address: str = Field(..., description="MAC address")
    ip_address: Optional[str] = Field(None, description="IP address")
    device_type: str = Field(default="gateway", description="Device type")
    location: Optional[str] = Field(None, description="Device location")


class DeviceCreate(DeviceBase):
    """Schema for creating a device"""
    pass


class DeviceUpdate(BaseModel):
    """Schema for updating a device"""
    name: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    ip_address: Optional[str] = None


class DeviceInfo(BaseModel):
    """Complete device information"""
    device_name: str
    device_type: str
    interface: str
    mac_address: str
    ip_address: str
    ipv6_address: Optional[str] = None
    software_version: Optional[str] = None
    hardware_version: Optional[str] = None
    uptime: Optional[int] = None  # seconds


class Device(DeviceBase):
    """Device response model"""
    id: str = Field(..., description="Device ID")
    status: str = Field(default="unknown", description="Device status")
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceList(BaseModel):
    """List of devices"""
    devices: List[Device]
    total: int
