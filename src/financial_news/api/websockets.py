"""WebSocket notification system for real-time updates."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class NotificationManager:
    """Manages WebSocket connections for real-time notifications."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.connection_ids: dict[str, WebSocket] = {}
        self.user_connections: dict[str, list[str]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: str | None = None,
    ) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_ids[connection_id] = websocket

        if user_id:
            self.user_connections.setdefault(user_id, []).append(connection_id)

        await self.send_personal_envelope(
            event_type="connection_established",
            payload={
                "connection_id": connection_id,
                "message": "Connected to Financial News notification system",
                "user_id": user_id,
            },
            connection_id=connection_id,
        )
        logger.info(
            "Client connected: %s (user=%s)",
            connection_id,
            user_id or "anonymous",
        )

    def disconnect(self, connection_id: str, user_id: str | None = None) -> None:
        """Disconnect a WebSocket connection."""
        websocket = self.connection_ids.pop(connection_id, None)
        if websocket and websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if user_id:
            users_to_scan = [user_id]
        else:
            users_to_scan = list(self.user_connections.keys())

        for user_key in users_to_scan:
            connections = self.user_connections.get(user_key, [])
            if connection_id in connections:
                connections.remove(connection_id)
            if not connections and user_key in self.user_connections:
                del self.user_connections[user_key]

        logger.info(
            "Client disconnected: %s (user=%s)",
            connection_id,
            user_id or "anonymous",
        )

    @staticmethod
    def _envelope(
        event_type: str,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "type": event_type,
            "payload": payload,
            "ts": _now_iso(),
            "request_id": request_id or uuid.uuid4().hex[:16],
        }

    async def send_personal_message(
        self,
        message: dict[str, Any],
        connection_id: str,
    ) -> None:
        """Send a raw message to a specific connection."""
        websocket = self.connection_ids.get(connection_id)
        if websocket is None:
            return
        await websocket.send_json(message)

    async def send_personal_envelope(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        connection_id: str,
        request_id: str | None = None,
    ) -> None:
        await self.send_personal_message(
            self._envelope(event_type, payload, request_id=request_id),
            connection_id,
        )

    async def send_to_user(
        self,
        message: dict[str, Any],
        user_id: str,
        *,
        event_type: str = "user_notification",
        request_id: str | None = None,
    ) -> None:
        """Send an envelope message to all connections of a specific user."""
        for connection_id in self.user_connections.get(user_id, []):
            await self.send_personal_envelope(
                event_type=event_type,
                payload=message,
                connection_id=connection_id,
                request_id=request_id,
            )

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a raw message to all connected clients."""
        for websocket in list(self.active_connections):
            await websocket.send_json(message)

    async def broadcast_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> None:
        await self.broadcast(
            self._envelope(event_type, payload, request_id=request_id),
        )

    async def broadcast_market_alert(
        self,
        alert: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> None:
        await self.broadcast_event(
            "market_alert",
            {"alert": alert},
            request_id=request_id,
        )

    async def broadcast_news_update(
        self,
        news_item: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> None:
        await self.broadcast_event(
            "news_update",
            {"news": news_item},
            request_id=request_id,
        )


manager = NotificationManager()


async def generate_demo_alerts() -> None:
    """Generate demo alerts for testing the notification system."""
    import random

    market_alerts = [
        {
            "title": "S&P 500 down 1.5% on inflation concerns",
            "severity": "warning",
            "source": "Market Data",
            "details": "S&P 500 index dropped 1.5% following higher than expected inflation numbers.",
        },
        {
            "title": "Fed announces interest rate hike",
            "severity": "info",
            "source": "Federal Reserve",
            "details": "The Federal Reserve has announced a 0.25% increase in interest rates.",
        },
        {
            "title": "Apple (AAPL) reports strong quarterly earnings",
            "severity": "success",
            "source": "Earnings Report",
            "details": "Apple Inc. reported earnings per share of $1.52, beating expectations by 12%.",
        },
        {
            "title": "Oil prices surge 3% amid supply concerns",
            "severity": "warning",
            "source": "Commodity Markets",
            "details": "WTI Crude Oil prices jumped 3% following reports of production cuts.",
        },
        {
            "title": "Bitcoin falls below $50,000",
            "severity": "error",
            "source": "Crypto Markets",
            "details": "Bitcoin price dropped below the key $50,000 support level on increased selling pressure.",
        },
    ]

    news_updates = [
        {
            "title": "Tesla announces new battery technology",
            "summary": "Tesla unveiled a new battery technology that could significantly reduce costs and increase range.",
            "source": "Technology News",
            "url": "/articles/tesla-battery",
        },
        {
            "title": "Amazon to acquire startup for $4 billion",
            "summary": "Amazon is in talks to acquire an AI startup for approximately $4 billion, sources say.",
            "source": "Business News",
            "url": "/articles/amazon-acquisition",
        },
        {
            "title": "New regulations for cryptocurrency trading",
            "summary": "Regulatory agencies announced new compliance requirements for cryptocurrency exchanges.",
            "source": "Regulatory News",
            "url": "/articles/crypto-regulations",
        },
        {
            "title": "Global chip shortage expected to ease by Q3",
            "summary": "Industry experts predict the semiconductor shortage will begin to ease by the third quarter.",
            "source": "Supply Chain News",
            "url": "/articles/chip-shortage",
        },
    ]

    while True:
        request_id = uuid.uuid4().hex[:16]
        if random.random() < 0.5:
            alert = random.choice(market_alerts)
            await manager.broadcast_market_alert(alert, request_id=request_id)
            logger.info("Sent market alert: %s", alert["title"])
        else:
            news = random.choice(news_updates)
            await manager.broadcast_news_update(news, request_id=request_id)
            logger.info("Sent news update: %s", news["title"])
        await asyncio.sleep(random.randint(30, 120))
