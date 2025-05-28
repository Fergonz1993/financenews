"""
WebSocket notification system for real-time updates.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages WebSocket connections for real-time notifications."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_ids: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}  # Maps user_id to connection_ids
        
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: Optional[str] = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_ids[connection_id] = websocket
        
        # Track user connections if user_id is provided
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(connection_id)
            
        # Send welcome message
        await self.send_personal_message(
            {
                "type": "connection_established",
                "connection_id": connection_id,
                "timestamp": datetime.now().isoformat(),
                "message": "Connected to Financial News notification system"
            },
            connection_id
        )
        
        logger.info(f"Client connected: {connection_id} (User: {user_id or 'anonymous'})")
        
    def disconnect(self, connection_id: str, user_id: Optional[str] = None):
        """Disconnect a WebSocket connection."""
        if connection_id in self.connection_ids:
            websocket = self.connection_ids[connection_id]
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            del self.connection_ids[connection_id]
            
            # Remove from user connections if applicable
            if user_id and user_id in self.user_connections:
                if connection_id in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
                    
            logger.info(f"Client disconnected: {connection_id} (User: {user_id or 'anonymous'})")
    
    async def send_personal_message(self, message: Dict[str, Any], connection_id: str):
        """Send a message to a specific connection."""
        if connection_id in self.connection_ids:
            websocket = self.connection_ids[connection_id]
            await websocket.send_json(message)
    
    async def send_to_user(self, message: Dict[str, Any], user_id: str):
        """Send a message to all connections of a specific user."""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id]:
                await self.send_personal_message(message, connection_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        for websocket in self.active_connections:
            await websocket.send_json(message)
    
    async def broadcast_market_alert(self, alert: Dict[str, Any]):
        """Broadcast a market alert to all connected clients."""
        message = {
            "type": "market_alert",
            "alert": alert,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def broadcast_news_update(self, news_item: Dict[str, Any]):
        """Broadcast a news update to all connected clients."""
        message = {
            "type": "news_update",
            "news": news_item,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)


# Create a global instance of the notification manager
manager = NotificationManager()


# Function to simulate real-time alerts (for demo/testing)
async def generate_demo_alerts():
    """Generate demo alerts for testing the notification system."""
    import random
    
    # Demo market alerts
    market_alerts = [
        {
            "title": "S&P 500 down 1.5% on inflation concerns",
            "severity": "warning",
            "source": "Market Data",
            "details": "S&P 500 index dropped 1.5% following higher than expected inflation numbers."
        },
        {
            "title": "Fed announces interest rate hike",
            "severity": "info",
            "source": "Federal Reserve",
            "details": "The Federal Reserve has announced a 0.25% increase in interest rates."
        },
        {
            "title": "Apple (AAPL) reports strong quarterly earnings",
            "severity": "success",
            "source": "Earnings Report",
            "details": "Apple Inc. reported earnings per share of $1.52, beating expectations by 12%."
        },
        {
            "title": "Oil prices surge 3% amid supply concerns",
            "severity": "warning",
            "source": "Commodity Markets",
            "details": "WTI Crude Oil prices jumped 3% following reports of production cuts."
        },
        {
            "title": "Bitcoin falls below $50,000",
            "severity": "error",
            "source": "Crypto Markets",
            "details": "Bitcoin price dropped below the key $50,000 support level on increased selling pressure."
        }
    ]
    
    # Demo news updates
    news_updates = [
        {
            "title": "Tesla announces new battery technology",
            "summary": "Tesla unveiled a new battery technology that could significantly reduce costs and increase range.",
            "source": "Technology News",
            "url": "/articles/tesla-battery"
        },
        {
            "title": "Amazon to acquire startup for $4 billion",
            "summary": "Amazon is in talks to acquire an AI startup for approximately $4 billion, sources say.",
            "source": "Business News",
            "url": "/articles/amazon-acquisition"
        },
        {
            "title": "New regulations for cryptocurrency trading",
            "summary": "Regulatory agencies announced new compliance requirements for cryptocurrency exchanges.",
            "source": "Regulatory News",
            "url": "/articles/crypto-regulations"
        },
        {
            "title": "Global chip shortage expected to ease by Q3",
            "summary": "Industry experts predict the semiconductor shortage will begin to ease by the third quarter.",
            "source": "Supply Chain News",
            "url": "/articles/chip-shortage"
        }
    ]
    
    while True:
        # Randomly decide whether to send an alert or news update
        if random.random() < 0.5:
            alert = random.choice(market_alerts)
            await manager.broadcast_market_alert(alert)
            logger.info(f"Sent market alert: {alert['title']}")
        else:
            news = random.choice(news_updates)
            await manager.broadcast_news_update(news)
            logger.info(f"Sent news update: {news['title']}")
            
        # Wait between 30-120 seconds before sending next alert
        await asyncio.sleep(random.randint(30, 120))
