"""
Collaboration Engine Module

This module provides comprehensive collaboration capabilities including shared workspaces,
real-time communication, collaborative research, and team analytics features.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import websockets

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles in collaborative environment."""

    ADMIN = "admin"
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    VIEWER = "viewer"
    GUEST = "guest"


class WorkspaceType(Enum):
    """Types of collaborative workspaces."""

    RESEARCH = "research"
    TRADING = "trading"
    ANALYSIS = "analysis"
    PRESENTATION = "presentation"
    DASHBOARD = "dashboard"


class MessageType(Enum):
    """Types of collaboration messages."""

    CHAT = "chat"
    ANNOTATION = "annotation"
    ALERT = "alert"
    COMMENT = "comment"
    MENTION = "mention"
    SYSTEM = "system"


class PermissionLevel(Enum):
    """Permission levels for workspace access."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


@dataclass
class User:
    """User in the collaboration system."""

    user_id: str
    username: str
    email: str
    display_name: str
    role: UserRole
    avatar_url: str | None = None
    is_active: bool = True
    last_seen: datetime | None = None
    preferences: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Workspace:
    """Collaborative workspace."""

    workspace_id: str
    name: str
    description: str
    workspace_type: WorkspaceType
    owner_id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    settings: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class WorkspaceMember:
    """Workspace member with permissions."""

    workspace_id: str
    user_id: str
    permission_level: PermissionLevel
    joined_at: datetime
    invited_by: str
    is_active: bool = True


@dataclass
class Message:
    """Collaboration message."""

    message_id: str
    workspace_id: str
    user_id: str
    message_type: MessageType
    content: str
    thread_id: str | None = None
    parent_message_id: str | None = None
    mentions: list[str] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    edited_at: datetime | None = None
    is_deleted: bool = False


@dataclass
class Annotation:
    """Annotation on charts, documents, or data."""

    annotation_id: str
    workspace_id: str
    user_id: str
    target_type: str  # 'chart', 'document', 'data_point'
    target_id: str
    position: dict[str, float]  # x, y coordinates or data reference
    content: str
    annotation_type: str  # 'note', 'highlight', 'arrow', 'shape'
    style: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    is_resolved: bool = False


@dataclass
class SharedResource:
    """Shared resource in workspace."""

    resource_id: str
    workspace_id: str
    resource_type: str  # 'dashboard', 'chart', 'report', 'dataset'
    name: str
    description: str
    content: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime
    version: int = 1
    is_locked: bool = False
    locked_by: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class CollaborationSession:
    """Real-time collaboration session."""

    session_id: str
    workspace_id: str
    resource_id: str
    participants: set[str]
    started_at: datetime
    last_activity: datetime
    session_type: str = "editing"  # 'editing', 'viewing', 'meeting'
    is_active: bool = True


@dataclass
class TeamAnalytics:
    """Team collaboration analytics."""

    workspace_id: str
    period_start: datetime
    period_end: datetime
    metrics: dict[str, Any]
    user_activities: dict[str, dict] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)


class CollaborationEngine:
    """Main collaboration engine managing all collaborative features."""

    def __init__(self):
        self.db_path = "collaboration.db"
        self.active_connections = {}  # websocket connections
        self.active_sessions = {}
        self.user_presence = {}  # online/offline status
        self.workspace_subscribers = defaultdict(set)
        self._setup_database()

    def _setup_database(self):
        """Setup database for collaboration data."""
        conn = sqlite3.connect(self.db_path)

        # Users table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                display_name TEXT,
                role TEXT,
                avatar_url TEXT,
                is_active BOOLEAN,
                last_seen TEXT,
                preferences TEXT,
                created_at TEXT
            )
        """
        )

        # Workspaces table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                workspace_type TEXT,
                owner_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                is_active BOOLEAN,
                settings TEXT,
                tags TEXT
            )
        """
        )

        # Workspace members table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id TEXT,
                user_id TEXT,
                permission_level TEXT,
                joined_at TEXT,
                invited_by TEXT,
                is_active BOOLEAN,
                PRIMARY KEY (workspace_id, user_id)
            )
        """
        )

        # Messages table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                workspace_id TEXT,
                user_id TEXT,
                message_type TEXT,
                content TEXT,
                thread_id TEXT,
                parent_message_id TEXT,
                mentions TEXT,
                attachments TEXT,
                metadata TEXT,
                timestamp TEXT,
                edited_at TEXT,
                is_deleted BOOLEAN
            )
        """
        )

        # Annotations table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS annotations (
                annotation_id TEXT PRIMARY KEY,
                workspace_id TEXT,
                user_id TEXT,
                target_type TEXT,
                target_id TEXT,
                position TEXT,
                content TEXT,
                annotation_type TEXT,
                style TEXT,
                timestamp TEXT,
                is_resolved BOOLEAN
            )
        """
        )

        # Shared resources table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shared_resources (
                resource_id TEXT PRIMARY KEY,
                workspace_id TEXT,
                resource_type TEXT,
                name TEXT,
                description TEXT,
                content TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                version INTEGER,
                is_locked BOOLEAN,
                locked_by TEXT,
                tags TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    async def create_user(
        self,
        username: str,
        email: str,
        display_name: str,
        role: UserRole = UserRole.ANALYST,
    ) -> User:
        """Create a new user."""
        try:
            user_id = str(uuid.uuid4())

            user = User(
                user_id=user_id,
                username=username,
                email=email,
                display_name=display_name,
                role=role,
            )

            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO users
                (user_id, username, email, display_name, role, avatar_url,
                 is_active, last_seen, preferences, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user.user_id,
                    user.username,
                    user.email,
                    user.display_name,
                    user.role.value,
                    user.avatar_url,
                    user.is_active,
                    user.last_seen.isoformat() if user.last_seen else None,
                    json.dumps(user.preferences),
                    user.created_at.isoformat(),
                ),
            )
            conn.commit()
            conn.close()

            logger.info(f"Created user {username} with ID {user_id}")
            return user

        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def create_workspace(
        self, name: str, description: str, workspace_type: WorkspaceType, owner_id: str
    ) -> Workspace:
        """Create a new collaborative workspace."""
        try:
            workspace_id = str(uuid.uuid4())
            current_time = datetime.now()

            workspace = Workspace(
                workspace_id=workspace_id,
                name=name,
                description=description,
                workspace_type=workspace_type,
                owner_id=owner_id,
                created_at=current_time,
                updated_at=current_time,
            )

            conn = sqlite3.connect(self.db_path)

            # Create workspace
            conn.execute(
                """
                INSERT INTO workspaces
                (workspace_id, name, description, workspace_type, owner_id,
                 created_at, updated_at, is_active, settings, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    workspace.workspace_id,
                    workspace.name,
                    workspace.description,
                    workspace.workspace_type.value,
                    workspace.owner_id,
                    workspace.created_at.isoformat(),
                    workspace.updated_at.isoformat(),
                    workspace.is_active,
                    json.dumps(workspace.settings),
                    json.dumps(workspace.tags),
                ),
            )

            # Add owner as admin member
            await self._add_workspace_member(
                workspace_id, owner_id, PermissionLevel.OWNER, owner_id, conn
            )

            conn.commit()
            conn.close()

            logger.info(f"Created workspace {name} with ID {workspace_id}")
            return workspace

        except Exception as e:
            logger.error(f"Error creating workspace: {e}")
            raise

    async def add_workspace_member(
        self,
        workspace_id: str,
        user_id: str,
        permission_level: PermissionLevel,
        invited_by: str,
    ) -> bool:
        """Add a member to a workspace."""
        try:
            conn = sqlite3.connect(self.db_path)
            result = await self._add_workspace_member(
                workspace_id, user_id, permission_level, invited_by, conn
            )
            conn.commit()
            conn.close()

            if result:
                # Notify other workspace members
                await self._broadcast_to_workspace(
                    workspace_id,
                    {
                        "type": "member_added",
                        "user_id": user_id,
                        "permission_level": permission_level.value,
                        "invited_by": invited_by,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            return result

        except Exception as e:
            logger.error(f"Error adding workspace member: {e}")
            return False

    async def _add_workspace_member(
        self,
        workspace_id: str,
        user_id: str,
        permission_level: PermissionLevel,
        invited_by: str,
        conn: sqlite3.Connection,
    ) -> bool:
        """Internal method to add workspace member."""
        try:
            member = WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user_id,
                permission_level=permission_level,
                joined_at=datetime.now(),
                invited_by=invited_by,
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO workspace_members
                (workspace_id, user_id, permission_level, joined_at, invited_by, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    member.workspace_id,
                    member.user_id,
                    member.permission_level.value,
                    member.joined_at.isoformat(),
                    member.invited_by,
                    member.is_active,
                ),
            )

            return True

        except Exception as e:
            logger.error(f"Error in _add_workspace_member: {e}")
            return False

    async def send_message(
        self,
        workspace_id: str,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.CHAT,
        thread_id: str | None = None,
        mentions: list[str] | None = None,
    ) -> Message:
        """Send a message to a workspace."""
        try:
            message_id = str(uuid.uuid4())

            message = Message(
                message_id=message_id,
                workspace_id=workspace_id,
                user_id=user_id,
                message_type=message_type,
                content=content,
                thread_id=thread_id,
                mentions=mentions or [],
            )

            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO messages
                (message_id, workspace_id, user_id, message_type, content,
                 thread_id, parent_message_id, mentions, attachments, metadata,
                 timestamp, edited_at, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    message.message_id,
                    message.workspace_id,
                    message.user_id,
                    message.message_type.value,
                    message.content,
                    message.thread_id,
                    message.parent_message_id,
                    json.dumps(message.mentions),
                    json.dumps(message.attachments),
                    json.dumps(message.metadata),
                    message.timestamp.isoformat(),
                    message.edited_at.isoformat() if message.edited_at else None,
                    message.is_deleted,
                ),
            )
            conn.commit()
            conn.close()

            # Broadcast message to workspace subscribers
            await self._broadcast_to_workspace(
                workspace_id,
                {
                    "type": "new_message",
                    "message": {
                        "message_id": message.message_id,
                        "user_id": message.user_id,
                        "content": message.content,
                        "message_type": message.message_type.value,
                        "timestamp": message.timestamp.isoformat(),
                        "mentions": message.mentions,
                    },
                },
            )

            # Send notifications to mentioned users
            if message.mentions:
                await self._send_mention_notifications(message)

            logger.info(f"Sent message {message_id} to workspace {workspace_id}")
            return message

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def create_annotation(
        self,
        workspace_id: str,
        user_id: str,
        target_type: str,
        target_id: str,
        position: dict[str, float],
        content: str,
        annotation_type: str = "note",
    ) -> Annotation:
        """Create an annotation on a chart, document, or data point."""
        try:
            annotation_id = str(uuid.uuid4())

            annotation = Annotation(
                annotation_id=annotation_id,
                workspace_id=workspace_id,
                user_id=user_id,
                target_type=target_type,
                target_id=target_id,
                position=position,
                content=content,
                annotation_type=annotation_type,
            )

            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO annotations
                (annotation_id, workspace_id, user_id, target_type, target_id,
                 position, content, annotation_type, style, timestamp, is_resolved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    annotation.annotation_id,
                    annotation.workspace_id,
                    annotation.user_id,
                    annotation.target_type,
                    annotation.target_id,
                    json.dumps(annotation.position),
                    annotation.content,
                    annotation.annotation_type,
                    json.dumps(annotation.style),
                    annotation.timestamp.isoformat(),
                    annotation.is_resolved,
                ),
            )
            conn.commit()
            conn.close()

            # Broadcast annotation to workspace
            await self._broadcast_to_workspace(
                workspace_id,
                {
                    "type": "new_annotation",
                    "annotation": {
                        "annotation_id": annotation.annotation_id,
                        "user_id": annotation.user_id,
                        "target_type": annotation.target_type,
                        "target_id": annotation.target_id,
                        "position": annotation.position,
                        "content": annotation.content,
                        "annotation_type": annotation.annotation_type,
                        "timestamp": annotation.timestamp.isoformat(),
                    },
                },
            )

            logger.info(
                f"Created annotation {annotation_id} in workspace {workspace_id}"
            )
            return annotation

        except Exception as e:
            logger.error(f"Error creating annotation: {e}")
            raise

    async def share_resource(
        self,
        workspace_id: str,
        resource_type: str,
        name: str,
        description: str,
        content: dict[str, Any],
        created_by: str,
    ) -> SharedResource:
        """Share a resource (dashboard, chart, report) in workspace."""
        try:
            resource_id = str(uuid.uuid4())
            current_time = datetime.now()

            resource = SharedResource(
                resource_id=resource_id,
                workspace_id=workspace_id,
                resource_type=resource_type,
                name=name,
                description=description,
                content=content,
                created_by=created_by,
                created_at=current_time,
                updated_at=current_time,
            )

            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO shared_resources
                (resource_id, workspace_id, resource_type, name, description,
                 content, created_by, created_at, updated_at, version,
                 is_locked, locked_by, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    resource.resource_id,
                    resource.workspace_id,
                    resource.resource_type,
                    resource.name,
                    resource.description,
                    json.dumps(resource.content),
                    resource.created_by,
                    resource.created_at.isoformat(),
                    resource.updated_at.isoformat(),
                    resource.version,
                    resource.is_locked,
                    resource.locked_by,
                    json.dumps(resource.tags),
                ),
            )
            conn.commit()
            conn.close()

            # Broadcast new resource to workspace
            await self._broadcast_to_workspace(
                workspace_id,
                {
                    "type": "resource_shared",
                    "resource": {
                        "resource_id": resource.resource_id,
                        "resource_type": resource.resource_type,
                        "name": resource.name,
                        "description": resource.description,
                        "created_by": resource.created_by,
                        "created_at": resource.created_at.isoformat(),
                    },
                },
            )

            logger.info(f"Shared resource {resource_id} in workspace {workspace_id}")
            return resource

        except Exception as e:
            logger.error(f"Error sharing resource: {e}")
            raise

    async def start_collaboration_session(
        self,
        workspace_id: str,
        resource_id: str,
        user_id: str,
        session_type: str = "editing",
    ) -> CollaborationSession:
        """Start a real-time collaboration session."""
        try:
            session_id = str(uuid.uuid4())
            current_time = datetime.now()

            session = CollaborationSession(
                session_id=session_id,
                workspace_id=workspace_id,
                resource_id=resource_id,
                participants={user_id},
                started_at=current_time,
                last_activity=current_time,
                session_type=session_type,
            )

            self.active_sessions[session_id] = session

            # Notify workspace about new session
            await self._broadcast_to_workspace(
                workspace_id,
                {
                    "type": "session_started",
                    "session": {
                        "session_id": session.session_id,
                        "resource_id": session.resource_id,
                        "session_type": session.session_type,
                        "started_by": user_id,
                        "started_at": session.started_at.isoformat(),
                    },
                },
            )

            logger.info(f"Started collaboration session {session_id}")
            return session

        except Exception as e:
            logger.error(f"Error starting collaboration session: {e}")
            raise

    async def join_collaboration_session(self, session_id: str, user_id: str) -> bool:
        """Join an existing collaboration session."""
        try:
            if session_id not in self.active_sessions:
                return False

            session = self.active_sessions[session_id]
            session.participants.add(user_id)
            session.last_activity = datetime.now()

            # Notify other participants
            await self._broadcast_to_workspace(
                session.workspace_id,
                {
                    "type": "user_joined_session",
                    "session_id": session_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            logger.info(f"User {user_id} joined session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error joining collaboration session: {e}")
            return False

    async def update_user_presence(
        self, user_id: str, status: str, workspace_id: str | None = None
    ):
        """Update user's online presence."""
        try:
            self.user_presence[user_id] = {
                "status": status,  # 'online', 'away', 'busy', 'offline'
                "workspace_id": workspace_id,
                "last_seen": datetime.now(),
                "activity": "active" if status == "online" else "inactive",
            }

            # Broadcast presence update to relevant workspaces
            if workspace_id:
                await self._broadcast_to_workspace(
                    workspace_id,
                    {
                        "type": "presence_update",
                        "user_id": user_id,
                        "status": status,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"Error updating user presence: {e}")

    async def get_workspace_messages(
        self, workspace_id: str, limit: int = 50, before: datetime | None = None
    ) -> list[Message]:
        """Get messages from a workspace."""
        try:
            conn = sqlite3.connect(self.db_path)

            query = """
                SELECT message_id, workspace_id, user_id, message_type, content,
                       thread_id, parent_message_id, mentions, attachments,
                       metadata, timestamp, edited_at, is_deleted
                FROM messages
                WHERE workspace_id = ? AND is_deleted = 0
            """
            params = [workspace_id]

            if before:
                query += " AND timestamp < ?"
                params.append(before.isoformat())

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            messages = []
            for row in rows:
                message = Message(
                    message_id=row[0],
                    workspace_id=row[1],
                    user_id=row[2],
                    message_type=MessageType(row[3]),
                    content=row[4],
                    thread_id=row[5],
                    parent_message_id=row[6],
                    mentions=json.loads(row[7]) if row[7] else [],
                    attachments=json.loads(row[8]) if row[8] else [],
                    metadata=json.loads(row[9]) if row[9] else {},
                    timestamp=datetime.fromisoformat(row[10]),
                    edited_at=datetime.fromisoformat(row[11]) if row[11] else None,
                    is_deleted=bool(row[12]),
                )
                messages.append(message)

            return messages

        except Exception as e:
            logger.error(f"Error getting workspace messages: {e}")
            return []

    async def get_workspace_annotations(
        self, workspace_id: str, target_id: str | None = None
    ) -> list[Annotation]:
        """Get annotations for a workspace or specific target."""
        try:
            conn = sqlite3.connect(self.db_path)

            query = """
                SELECT annotation_id, workspace_id, user_id, target_type, target_id,
                       position, content, annotation_type, style, timestamp, is_resolved
                FROM annotations
                WHERE workspace_id = ?
            """
            params = [workspace_id]

            if target_id:
                query += " AND target_id = ?"
                params.append(target_id)

            query += " ORDER BY timestamp DESC"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            annotations = []
            for row in rows:
                annotation = Annotation(
                    annotation_id=row[0],
                    workspace_id=row[1],
                    user_id=row[2],
                    target_type=row[3],
                    target_id=row[4],
                    position=json.loads(row[5]),
                    content=row[6],
                    annotation_type=row[7],
                    style=json.loads(row[8]) if row[8] else {},
                    timestamp=datetime.fromisoformat(row[9]),
                    is_resolved=bool(row[10]),
                )
                annotations.append(annotation)

            return annotations

        except Exception as e:
            logger.error(f"Error getting workspace annotations: {e}")
            return []

    async def generate_team_analytics(
        self, workspace_id: str, period_days: int = 30
    ) -> TeamAnalytics:
        """Generate team collaboration analytics."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            conn = sqlite3.connect(self.db_path)

            # Get workspace members
            members_cursor = conn.execute(
                """
                SELECT user_id FROM workspace_members
                WHERE workspace_id = ? AND is_active = 1
            """,
                (workspace_id,),
            )
            member_ids = [row[0] for row in members_cursor.fetchall()]

            # Message activity
            messages_cursor = conn.execute(
                """
                SELECT user_id, COUNT(*) as message_count,
                       MIN(timestamp) as first_message, MAX(timestamp) as last_message
                FROM messages
                WHERE workspace_id = ? AND timestamp >= ? AND timestamp <= ?
                GROUP BY user_id
            """,
                (workspace_id, start_date.isoformat(), end_date.isoformat()),
            )

            message_stats = {}
            total_messages = 0
            for row in messages_cursor.fetchall():
                user_id, count, first, last = row
                message_stats[user_id] = {
                    "message_count": count,
                    "first_message": first,
                    "last_message": last,
                }
                total_messages += count

            # Annotation activity
            annotations_cursor = conn.execute(
                """
                SELECT user_id, COUNT(*) as annotation_count
                FROM annotations
                WHERE workspace_id = ? AND timestamp >= ? AND timestamp <= ?
                GROUP BY user_id
            """,
                (workspace_id, start_date.isoformat(), end_date.isoformat()),
            )

            annotation_stats = {}
            total_annotations = 0
            for row in annotations_cursor.fetchall():
                user_id, count = row
                annotation_stats[user_id] = count
                total_annotations += count

            # Resource sharing activity
            resources_cursor = conn.execute(
                """
                SELECT created_by, COUNT(*) as resource_count
                FROM shared_resources
                WHERE workspace_id = ? AND created_at >= ? AND created_at <= ?
                GROUP BY created_by
            """,
                (workspace_id, start_date.isoformat(), end_date.isoformat()),
            )

            resource_stats = {}
            total_resources = 0
            for row in resources_cursor.fetchall():
                user_id, count = row
                resource_stats[user_id] = count
                total_resources += count

            conn.close()

            # Calculate user activities
            user_activities = {}
            for user_id in member_ids:
                user_activities[user_id] = {
                    "messages": message_stats.get(user_id, {}).get("message_count", 0),
                    "annotations": annotation_stats.get(user_id, 0),
                    "resources_shared": resource_stats.get(user_id, 0),
                    "engagement_score": self._calculate_engagement_score(
                        message_stats.get(user_id, {}).get("message_count", 0),
                        annotation_stats.get(user_id, 0),
                        resource_stats.get(user_id, 0),
                    ),
                }

            # Overall metrics
            metrics = {
                "total_messages": total_messages,
                "total_annotations": total_annotations,
                "total_resources_shared": total_resources,
                "active_members": len(
                    [u for u in user_activities.values() if u["engagement_score"] > 0]
                ),
                "avg_messages_per_user": (
                    total_messages / len(member_ids) if member_ids else 0
                ),
                "avg_annotations_per_user": (
                    total_annotations / len(member_ids) if member_ids else 0
                ),
                "collaboration_intensity": self._calculate_collaboration_intensity(
                    total_messages, total_annotations, total_resources, period_days
                ),
            }

            analytics = TeamAnalytics(
                workspace_id=workspace_id,
                period_start=start_date,
                period_end=end_date,
                metrics=metrics,
                user_activities=user_activities,
            )

            return analytics

        except Exception as e:
            logger.error(f"Error generating team analytics: {e}")
            raise

    def _calculate_engagement_score(
        self, messages: int, annotations: int, resources: int
    ) -> float:
        """Calculate user engagement score."""
        # Weighted engagement score
        score = (messages * 1.0) + (annotations * 2.0) + (resources * 3.0)
        return min(100, score)  # Cap at 100

    def _calculate_collaboration_intensity(
        self, messages: int, annotations: int, resources: int, days: int
    ) -> float:
        """Calculate overall collaboration intensity."""
        total_activities = messages + annotations + resources
        daily_average = total_activities / days if days > 0 else 0

        # Normalize to 0-1 scale (assuming 50 activities per day is high intensity)
        intensity = min(1.0, daily_average / 50)
        return intensity

    async def _broadcast_to_workspace(self, workspace_id: str, message: dict[str, Any]):
        """Broadcast a message to all subscribers of a workspace."""
        try:
            if workspace_id in self.workspace_subscribers:
                subscribers = self.workspace_subscribers[workspace_id].copy()

                for user_id in subscribers:
                    if user_id in self.active_connections:
                        websocket = self.active_connections[user_id]
                        try:
                            await websocket.send(
                                json.dumps({"workspace_id": workspace_id, **message})
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send message to {user_id}: {e}")
                            # Remove disconnected websocket
                            if user_id in self.active_connections:
                                del self.active_connections[user_id]
                            self.workspace_subscribers[workspace_id].discard(user_id)

        except Exception as e:
            logger.error(f"Error broadcasting to workspace {workspace_id}: {e}")

    async def _send_mention_notifications(self, message: Message):
        """Send notifications to mentioned users."""
        try:
            for mentioned_user_id in message.mentions:
                # Create notification (could integrate with email, push notifications, etc.)
                notification = {
                    "type": "mention",
                    "message_id": message.message_id,
                    "workspace_id": message.workspace_id,
                    "mentioned_by": message.user_id,
                    "content_preview": message.content[:100],
                    "timestamp": message.timestamp.isoformat(),
                }

                # Send real-time notification if user is online
                if mentioned_user_id in self.active_connections:
                    websocket = self.active_connections[mentioned_user_id]
                    try:
                        await websocket.send(
                            json.dumps(
                                {"type": "notification", "notification": notification}
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send mention notification: {e}")

        except Exception as e:
            logger.error(f"Error sending mention notifications: {e}")

    async def handle_websocket_connection(
        self, websocket, user_id: str, workspace_id: str
    ):
        """Handle websocket connection for real-time collaboration."""
        try:
            # Register connection
            self.active_connections[user_id] = websocket
            self.workspace_subscribers[workspace_id].add(user_id)

            # Update user presence
            await self.update_user_presence(user_id, "online", workspace_id)

            logger.info(f"User {user_id} connected to workspace {workspace_id}")

            # Keep connection alive and handle messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_websocket_message(user_id, workspace_id, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {user_id}: {message}")
                except Exception as e:
                    logger.error(f"Error handling websocket message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"User {user_id} disconnected from workspace {workspace_id}")
        except Exception as e:
            logger.error(f"Error in websocket connection: {e}")
        finally:
            # Clean up connection
            if user_id in self.active_connections:
                del self.active_connections[user_id]
            self.workspace_subscribers[workspace_id].discard(user_id)

            # Update user presence
            await self.update_user_presence(user_id, "offline")

    async def _handle_websocket_message(
        self, user_id: str, workspace_id: str, data: dict[str, Any]
    ):
        """Handle incoming websocket message."""
        try:
            message_type = data.get("type")

            if message_type == "chat_message":
                await self.send_message(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    content=data.get("content", ""),
                    message_type=MessageType.CHAT,
                    thread_id=data.get("thread_id"),
                    mentions=data.get("mentions", []),
                )

            elif message_type == "annotation":
                await self.create_annotation(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    target_type=data.get("target_type"),
                    target_id=data.get("target_id"),
                    position=data.get("position"),
                    content=data.get("content"),
                    annotation_type=data.get("annotation_type", "note"),
                )

            elif message_type == "presence_update":
                await self.update_user_presence(
                    user_id=user_id,
                    status=data.get("status"),
                    workspace_id=workspace_id,
                )

            elif message_type == "join_session":
                session_id = data.get("session_id")
                if session_id:
                    await self.join_collaboration_session(session_id, user_id)

            # Add more message types as needed

        except Exception as e:
            logger.error(
                f"Error handling websocket message type {data.get('type')}: {e}"
            )


# Example usage and testing
async def main():
    """Example usage of the collaboration engine."""
    engine = CollaborationEngine()

    # Create users
    alice = await engine.create_user(
        "alice", "alice@example.com", "Alice Johnson", UserRole.ANALYST
    )
    bob = await engine.create_user(
        "bob", "bob@example.com", "Bob Smith", UserRole.RESEARCHER
    )

    print(f"Created users: {alice.username}, {bob.username}")

    # Create workspace
    workspace = await engine.create_workspace(
        name="Market Analysis Team",
        description="Collaborative workspace for market analysis",
        workspace_type=WorkspaceType.RESEARCH,
        owner_id=alice.user_id,
    )

    print(f"Created workspace: {workspace.name}")

    # Add member to workspace
    await engine.add_workspace_member(
        workspace.workspace_id, bob.user_id, PermissionLevel.WRITE, alice.user_id
    )

    print(f"Added {bob.username} to workspace")

    # Send messages
    message1 = await engine.send_message(
        workspace.workspace_id,
        alice.user_id,
        "Let's analyze the latest earnings reports",
        MessageType.CHAT,
    )

    message2 = await engine.send_message(
        workspace.workspace_id,
        bob.user_id,
        f"@{alice.user_id} Great idea! I'll start with tech stocks",
        MessageType.CHAT,
        mentions=[alice.user_id],
    )

    print(f"Sent {len([message1, message2])} messages")

    # Create annotation
    annotation = await engine.create_annotation(
        workspace.workspace_id,
        alice.user_id,
        target_type="chart",
        target_id="earnings_chart_1",
        position={"x": 0.5, "y": 0.3},
        content="Notice the upward trend here",
        annotation_type="arrow",
    )

    print(f"Created annotation: {annotation.content}")

    # Share resource
    resource = await engine.share_resource(
        workspace.workspace_id,
        resource_type="dashboard",
        name="Q3 Earnings Dashboard",
        description="Dashboard showing Q3 earnings analysis",
        content={"charts": ["earnings_chart_1", "revenue_chart_2"]},
        created_by=alice.user_id,
    )

    print(f"Shared resource: {resource.name}")

    # Generate team analytics
    analytics = await engine.generate_team_analytics(workspace.workspace_id)
    print(f"Team analytics: {analytics.metrics}")


if __name__ == "__main__":
    asyncio.run(main())
