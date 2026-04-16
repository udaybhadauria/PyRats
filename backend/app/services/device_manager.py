"""
Device Manager Service - Handles device operations
Replaces Networking.c functionality
"""

import asyncio
import json
from uuid import uuid4
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.models import ConfigManager
from app.utils import logger


class DeviceManager:
    """Manages device registry and operations"""

    def __init__(self):
        self.devices: Dict[str, Dict[str, Any]] = {}
        self._load_devices()

    def _load_devices(self):
        """Load devices from configuration file"""
        try:
            config = ConfigManager.load_devices()
            if isinstance(config, dict) and 'devices' in config:
                self.devices = {
                    d['id']: d for d in config['devices']
                }
                logger.info(f"Loaded {len(self.devices)} devices from config")
        except Exception as e:
            logger.error(f"Error loading devices: {e}")

    def _save_devices(self):
        """Save devices to configuration file"""
        try:
            devices_list = list(self.devices.values())
            ConfigManager.save_devices({'devices': devices_list})
        except Exception as e:
            logger.error(f"Error saving devices: {e}")

    def add_device(self, name: str, mac: str, ip: str = None, 
                   device_type: str = "gateway", location: str = None) -> Dict[str, Any]:
        """
        Add a new device
        
        Args:
            name: Device name
            mac: MAC address
            ip: IP address (optional)
            device_type: Device type
            location: Device location
            
        Returns:
            Device dictionary
        """
        device_id = str(uuid4())
        device = {
            'id': device_id,
            'name': name,
            'mac_address': mac,
            'ip_address': ip,
            'device_type': device_type,
            'location': location,
            'status': 'unknown',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'last_seen': None,
        }
        
        self.devices[device_id] = device
        self._save_devices()
        logger.info(f"Added device: {name} ({device_id})")
        
        return device

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device by ID"""
        return self.devices.get(device_id)

    def get_devices_by_mac(self, mac: str) -> Optional[Dict[str, Any]]:
        """Get device by MAC address"""
        for device in self.devices.values():
            if device['mac_address'].lower() == mac.lower():
                return device
        return None

    def list_devices(self, status: str = None) -> List[Dict[str, Any]]:
        """
        List all devices, optionally filtered by status
        
        Args:
            status: Optional status filter
            
        Returns:
            List of devices
        """
        devices = list(self.devices.values())
        if status:
            devices = [d for d in devices if d.get('status') == status]
        return devices

    def update_device(self, device_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update device information"""
        if device_id not in self.devices:
            return None

        device = self.devices[device_id]
        allowed_fields = {'name', 'ip_address', 'device_type', 'location', 'status'}
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                device[key] = value

        device['updated_at'] = datetime.now().isoformat()
        self._save_devices()
        logger.info(f"Updated device: {device_id}")
        
        return device

    def update_device_status(self, device_id: str, status: str, ip_address: str = None):
        """Update device status and optionally IP address"""
        if device_id in self.devices:
            self.devices[device_id]['status'] = status
            self.devices[device_id]['last_seen'] = datetime.now().isoformat()
            if ip_address:
                self.devices[device_id]['ip_address'] = ip_address
            self._save_devices()

    def delete_device(self, device_id: str) -> bool:
        """Delete a device"""
        if device_id in self.devices:
            del self.devices[device_id]
            self._save_devices()
            logger.info(f"Deleted device: {device_id}")
            return True
        return False

    def get_device_count(self) -> int:
        """Get total number of devices"""
        return len(self.devices)

    def get_online_devices(self) -> List[Dict[str, Any]]:
        """Get list of online devices"""
        return [d for d in self.devices.values() if d.get('status') == 'online']


# Global device manager instance
device_manager = DeviceManager()
