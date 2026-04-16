"""
MQTT Manager - Handles all MQTT communication
Replaces Paho C library with async Python implementation
"""

import asyncio
import json
from typing import Callable, Optional, Dict, Any
import paho.mqtt.client as mqtt
from app.settings import settings
from app.utils import logger


class MQTTManager:
    """Manages MQTT connections and pub/sub operations"""

    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="RATS_Server")
        self.connected = False
        self.subscriptions: Dict[str, list] = {}
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Setup MQTT client callbacks"""
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        """Called when client connects to broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {settings.MQTT_BROKER}:{settings.MQTT_PORT}")
            
            # Resubscribe to topics
            for topic in self.subscriptions:
                client.subscribe(topic, qos=settings.MQTT_QOS)
                logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Called when client disconnects from broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker (code: {rc})")
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_message(self, client, userdata, msg):
        """Called when message is received on subscribed topic"""
        try:
            payload = msg.payload.decode('utf-8')
            topic = msg.topic
            
            logger.debug(f"Received message on {topic}: {payload[:100]}")
            
            # Call registered callbacks for this topic
            if topic in self.subscriptions:
                for callback in self.subscriptions[topic]:
                    try:
                        callback(topic, payload)
                    except Exception as e:
                        logger.error(f"Error in message callback: {e}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    async def connect(self) -> bool:
        """
        Connect to MQTT broker
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
                self.client.username_pw_set(
                    settings.MQTT_USERNAME,
                    settings.MQTT_PASSWORD
                )

            self.client.connect(
                settings.MQTT_BROKER,
                settings.MQTT_PORT,
                keepalive=settings.MQTT_KEEPALIVE
            )
            
            # Start network loop in background
            self.client.loop_start()
            
            # Wait for connection
            for _ in range(50):  # 5 seconds timeout
                if self.connected:
                    return True
                await asyncio.sleep(0.1)
            
            logger.error("Timeout waiting for MQTT connection")
            return False
            
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    async def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT broker: {e}")

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any] | str,
        qos: int = None
    ) -> bool:
        """
        Publish message to MQTT topic
        
        Args:
            topic: MQTT topic
            message: Message dict or string
            qos: Quality of Service (0, 1, or 2)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if qos is None:
                qos = settings.MQTT_QOS

            if isinstance(message, dict):
                payload = json.dumps(message)
            else:
                payload = str(message)

            result = self.client.publish(topic, payload, qos=qos)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload[:100]}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}: rc={result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable = None):
        """
        Subscribe to MQTT topic
        
        Args:
            topic: MQTT topic pattern
            callback: Optional callback function(topic, payload)
        """
        try:
            if topic not in self.subscriptions:
                self.subscriptions[topic] = []
                self.client.subscribe(topic, qos=settings.MQTT_QOS)
                logger.info(f"Subscribed to topic: {topic}")

            if callback:
                self.subscriptions[topic].append(callback)
                logger.debug(f"Added callback for topic: {topic}")

        except Exception as e:
            logger.error(f"Error subscribing to topic {topic}: {e}")

    def unsubscribe(self, topic: str):
        """
        Unsubscribe from MQTT topic
        
        Args:
            topic: MQTT topic pattern
        """
        try:
            if topic in self.subscriptions:
                del self.subscriptions[topic]
            self.client.unsubscribe(topic)
            logger.info(f"Unsubscribed from topic: {topic}")
        except Exception as e:
            logger.error(f"Error unsubscribing from topic {topic}: {e}")


# Global MQTT manager instance
mqtt_manager = MQTTManager()
