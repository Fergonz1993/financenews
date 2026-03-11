"""Notification and websocket routes."""

from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

from financial_news.api.dependencies import (
    get_logger,
    get_notification_manager,
    require_admin_access,
)
from financial_news.api.helpers import _request_id_from_request, _with_request_id

router = APIRouter()


async def _notification_socket_loop(
    websocket: WebSocket,
    connection_id: str,
    user_id: str | None,
) -> None:
    notification_manager = cast(Any, websocket.app.state.container.notification_manager)
    await notification_manager.connect(websocket, connection_id, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_manager.disconnect(connection_id, user_id)


@router.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket) -> None:
    connection_id = str(uuid.uuid4())
    user_id = websocket.query_params.get("user_id")
    await _notification_socket_loop(websocket, connection_id, user_id)


@router.websocket("/ws")
async def websocket_canonical_endpoint(websocket: WebSocket) -> None:
    connection_id = str(uuid.uuid4())
    user_id = websocket.query_params.get("user_id")
    await _notification_socket_loop(websocket, connection_id, user_id)


@router.websocket("/ws/notifications/{user_id}")
async def user_websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    connection_id = str(uuid.uuid4())
    await _notification_socket_loop(websocket, connection_id, user_id)


@router.post("/api/notifications/send")
async def send_notification(
    data: dict[str, Any],
    request: Request,
    admin_actor: str = Depends(require_admin_access("admin", "ops")),
    notification_manager: Any = Depends(get_notification_manager),
    logger: Any = Depends(get_logger),
) -> dict[str, Any]:
    request_id = _request_id_from_request(request)
    logger.info(
        "admin_send_notification request_id=%s actor=%s notification_type=%s",
        request_id,
        admin_actor,
        data.get("type"),
    )
    if "type" not in data:
        raise HTTPException(status_code=400, detail="Notification type is required")
    if data["type"] == "market_alert" and "alert" in data:
        await notification_manager.broadcast_market_alert(
            data["alert"],
            request_id=request_id,
        )
    elif data["type"] == "news_update" and "news" in data:
        await notification_manager.broadcast_news_update(
            data["news"],
            request_id=request_id,
        )
    elif (
        data["type"] == "user_notification"
        and "user_id" in data
        and "message" in data
    ):
        message_payload = data["message"]
        if not isinstance(message_payload, dict):
            message_payload = {"message": str(message_payload)}
        await notification_manager.send_to_user(
            message_payload,
            data["user_id"],
            event_type="user_notification",
            request_id=request_id,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid notification format")
    return _with_request_id(
        {"status": "success", "message": "Notification sent"},
        request_id=request_id,
    )
