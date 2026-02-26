"""
Enterprise Security & Compliance Module

This module provides comprehensive security features including authentication, authorization,
data encryption, audit logging, compliance reporting, and security monitoring.
"""

import asyncio
import base64
import ipaddress
import json
import logging
import os
import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security access levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class AuditAction(Enum):
    """Types of audit actions."""

    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_VIOLATION = "security_violation"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_DISABLED = "account_disabled"


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""

    SOX = "sox"  # Sarbanes-Oxley
    GDPR = "gdpr"  # General Data Protection Regulation
    PCI_DSS = "pci_dss"  # Payment Card Industry Data Security Standard
    HIPAA = "hipaa"  # Health Insurance Portability and Accountability Act
    FINRA = "finra"  # Financial Industry Regulatory Authority
    SEC = "sec"  # Securities and Exchange Commission
    ISO27001 = "iso27001"  # International Organization for Standardization
    NIST = "nist"  # National Institute of Standards and Technology


class ThreatLevel(Enum):
    """Security threat levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class User:
    """User account information."""

    user_id: str
    username: str
    email: str
    password_hash: str
    roles: set[str]
    permissions: set[str]
    security_level: SecurityLevel
    is_active: bool = True
    last_login: datetime | None = None
    failed_login_attempts: int = 0
    account_locked_until: datetime | None = None
    password_expires: datetime | None = None
    two_factor_enabled: bool = False
    two_factor_secret: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AuditLog:
    """Audit log entry."""

    log_id: str
    user_id: str
    action: AuditAction
    resource: str
    details: dict[str, Any]
    ip_address: str
    user_agent: str
    timestamp: datetime
    risk_score: float = 0.0
    compliance_tags: list[str] = field(default_factory=list)


@dataclass
class SecurityIncident:
    """Security incident record."""

    incident_id: str
    threat_level: ThreatLevel
    incident_type: str
    description: str
    affected_users: list[str]
    affected_resources: list[str]
    source_ip: str
    detection_time: datetime
    resolution_time: datetime | None = None
    status: str = "open"  # open, investigating, resolved, closed
    assigned_to: str | None = None
    mitigation_actions: list[str] = field(default_factory=list)


@dataclass
class ComplianceReport:
    """Compliance report."""

    report_id: str
    framework: ComplianceFramework
    report_type: str
    period_start: datetime
    period_end: datetime
    findings: list[dict[str, Any]]
    compliance_score: float
    recommendations: list[str]
    generated_by: str
    generated_at: datetime


class EncryptionManager:
    """Handle data encryption and decryption."""

    def __init__(self):
        self.master_key = self._load_or_generate_master_key()
        self.fernet = Fernet(self.master_key)
        self.rsa_private_key = self._load_or_generate_rsa_key()
        self.rsa_public_key = self.rsa_private_key.public_key()

    def _load_or_generate_master_key(self) -> bytes:
        """Load or generate master encryption key."""
        key_file = Path("master.key")

        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            return key

    def _load_or_generate_rsa_key(self):
        """Load or generate RSA key pair."""
        key_file = Path("private_key.pem")

        if key_file.exists():
            with open(key_file, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)
        else:
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

            # Save private key
            with open(key_file, "wb") as f:
                f.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )

            return private_key

    def encrypt_symmetric(self, data: str) -> str:
        """Encrypt data using symmetric encryption."""
        return base64.b64encode(self.fernet.encrypt(data.encode())).decode()

    def decrypt_symmetric(self, encrypted_data: str) -> str:
        """Decrypt data using symmetric encryption."""
        return self.fernet.decrypt(base64.b64decode(encrypted_data)).decode()

    def encrypt_asymmetric(self, data: str) -> str:
        """Encrypt data using asymmetric encryption."""
        encrypted = self.rsa_public_key.encrypt(
            data.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted).decode()

    def decrypt_asymmetric(self, encrypted_data: str) -> str:
        """Decrypt data using asymmetric encryption."""
        decrypted = self.rsa_private_key.decrypt(
            base64.b64decode(encrypted_data),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return decrypted.decode()

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode(), password_hash.encode())


class AuthenticationManager:
    """Handle user authentication and authorization."""

    def __init__(self, encryption_manager: EncryptionManager):
        self.encryption = encryption_manager
        self.jwt_secret = secrets.token_urlsafe(32)
        self.active_sessions = {}
        self.failed_attempts = {}
        self.db_path = "security.db"
        self._setup_database()

    def _setup_database(self):
        """Setup security database."""
        conn = sqlite3.connect(self.db_path)

        # Users table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT,
                roles TEXT,
                permissions TEXT,
                security_level TEXT,
                is_active BOOLEAN,
                last_login TEXT,
                failed_login_attempts INTEGER,
                account_locked_until TEXT,
                password_expires TEXT,
                two_factor_enabled BOOLEAN,
                two_factor_secret TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """
        )

        # Sessions table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT,
                expires_at TEXT,
                is_active BOOLEAN
            )
        """
        )

        # API Keys table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                user_id TEXT,
                key_hash TEXT,
                name TEXT,
                permissions TEXT,
                expires_at TEXT,
                last_used TEXT,
                is_active BOOLEAN,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: set[str],
        security_level: SecurityLevel = SecurityLevel.INTERNAL,
    ) -> User:
        """Create a new user account."""
        try:
            user_id = str(uuid.uuid4())
            password_hash = self.encryption.hash_password(password)

            # Set password expiry (90 days)
            password_expires = datetime.now() + timedelta(days=90)

            user = User(
                user_id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                roles=roles,
                permissions=self._get_permissions_for_roles(roles),
                security_level=security_level,
                password_expires=password_expires,
            )

            # Store in database
            await self._store_user(user)

            logger.info(f"Created user account for {username}")
            return user

        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: str,
        user_agent: str,
        two_factor_code: str | None = None,
    ) -> dict[str, Any] | None:
        """Authenticate user login."""
        try:
            # Check for rate limiting
            if self._is_rate_limited(ip_address):
                logger.warning(f"Rate limit exceeded for IP: {ip_address}")
                return None

            # Get user from database
            user = await self._get_user_by_username(username)
            if not user:
                self._record_failed_attempt(ip_address)
                return None

            # Check if account is locked
            if user.account_locked_until and datetime.now() < user.account_locked_until:
                logger.warning(f"Account locked for user: {username}")
                return None

            # Check if account is active
            if not user.is_active:
                logger.warning(f"Inactive account login attempt: {username}")
                return None

            # Verify password
            if not self.encryption.verify_password(password, user.password_hash):
                await self._handle_failed_login(user)
                self._record_failed_attempt(ip_address)
                return None

            # Check two-factor authentication
            if user.two_factor_enabled:
                if not two_factor_code or not self._verify_2fa_code(
                    user, two_factor_code
                ):
                    logger.warning(f"2FA verification failed for user: {username}")
                    return None

            # Successful authentication
            await self._handle_successful_login(user, ip_address, user_agent)

            # Generate JWT token
            token = self._generate_jwt_token(user)

            # Create session
            session_id = await self._create_session(
                user.user_id, ip_address, user_agent
            )

            return {
                "user_id": user.user_id,
                "username": user.username,
                "roles": list(user.roles),
                "permissions": list(user.permissions),
                "security_level": user.security_level.value,
                "token": token,
                "session_id": session_id,
            }

        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return None

    async def authorize_action(
        self,
        user_id: str,
        action: str,
        resource: str,
        resource_security_level: SecurityLevel = SecurityLevel.INTERNAL,
    ) -> bool:
        """Authorize user action on resource."""
        try:
            user = await self._get_user_by_id(user_id)
            if not user or not user.is_active:
                return False

            # Check security level clearance
            if not self._has_security_clearance(
                user.security_level, resource_security_level
            ):
                return False

            # Check permissions
            required_permission = f"{action}:{resource}"
            return not (
                required_permission not in user.permissions
                and "admin:all" not in user.permissions
            )

        except Exception as e:
            logger.error(f"Error authorizing action: {e}")
            return False

    def _get_permissions_for_roles(self, roles: set[str]) -> set[str]:
        """Get permissions for given roles."""
        role_permissions = {
            "admin": {"admin:all"},
            "analyst": {"read:all", "write:reports", "write:analysis"},
            "researcher": {"read:all", "write:research"},
            "viewer": {"read:public", "read:internal"},
            "trader": {"read:all", "write:trades", "execute:trades"},
            "compliance": {"read:all", "write:compliance", "audit:all"},
            "security": {"read:all", "write:security", "admin:security"},
        }

        permissions = set()
        for role in roles:
            permissions.update(role_permissions.get(role, set()))

        return permissions

    def _has_security_clearance(
        self, user_level: SecurityLevel, required_level: SecurityLevel
    ) -> bool:
        """Check if user has required security clearance."""
        level_hierarchy = {
            SecurityLevel.PUBLIC: 0,
            SecurityLevel.INTERNAL: 1,
            SecurityLevel.CONFIDENTIAL: 2,
            SecurityLevel.RESTRICTED: 3,
            SecurityLevel.TOP_SECRET: 4,
        }

        return level_hierarchy[user_level] >= level_hierarchy[required_level]

    def _is_rate_limited(self, ip_address: str) -> bool:
        """Check if IP address is rate limited."""
        current_time = time.time()
        window = 300  # 5 minutes
        max_attempts = 10

        if ip_address not in self.failed_attempts:
            return False

        # Clean old attempts
        self.failed_attempts[ip_address] = [
            timestamp
            for timestamp in self.failed_attempts[ip_address]
            if current_time - timestamp < window
        ]

        return len(self.failed_attempts[ip_address]) >= max_attempts

    def _record_failed_attempt(self, ip_address: str):
        """Record failed login attempt."""
        if ip_address not in self.failed_attempts:
            self.failed_attempts[ip_address] = []

        self.failed_attempts[ip_address].append(time.time())

    async def _handle_failed_login(self, user: User):
        """Handle failed login attempt."""
        user.failed_login_attempts += 1

        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.account_locked_until = datetime.now() + timedelta(minutes=30)
            logger.warning(f"Account locked for user: {user.username}")

        await self._update_user(user)

    async def _handle_successful_login(
        self, user: User, ip_address: str, user_agent: str
    ):
        """Handle successful login."""
        user.last_login = datetime.now()
        user.failed_login_attempts = 0
        user.account_locked_until = None

        await self._update_user(user)

    def _generate_jwt_token(self, user: User) -> str:
        """Generate JWT token for user."""
        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "roles": list(user.roles),
            "security_level": user.security_level.value,
            "exp": datetime.utcnow() + timedelta(hours=8),
            "iat": datetime.utcnow(),
        }

        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_jwt_token(self, token: str) -> dict[str, Any] | None:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token")
            return None

    async def _create_session(
        self, user_id: str, ip_address: str, user_agent: str
    ) -> str:
        """Create user session."""
        session_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=8)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO user_sessions
            (session_id, user_id, ip_address, user_agent, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session_id,
                user_id,
                ip_address,
                user_agent,
                datetime.now().isoformat(),
                expires_at.isoformat(),
                True,
            ),
        )
        conn.commit()
        conn.close()

        return session_id

    async def _store_user(self, user: User):
        """Store user in database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO users
            (user_id, username, email, password_hash, roles, permissions,
             security_level, is_active, last_login, failed_login_attempts,
             account_locked_until, password_expires, two_factor_enabled,
             two_factor_secret, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user.user_id,
                user.username,
                user.email,
                user.password_hash,
                json.dumps(list(user.roles)),
                json.dumps(list(user.permissions)),
                user.security_level.value,
                user.is_active,
                user.last_login.isoformat() if user.last_login else None,
                user.failed_login_attempts,
                (
                    user.account_locked_until.isoformat()
                    if user.account_locked_until
                    else None
                ),
                user.password_expires.isoformat() if user.password_expires else None,
                user.two_factor_enabled,
                user.two_factor_secret,
                user.created_at.isoformat(),
                user.updated_at.isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    async def _update_user(self, user: User):
        """Update user in database."""
        user.updated_at = datetime.now()
        await self._store_user(user)

    async def _get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_user(row)
        return None

    async def _get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_user(row)
        return None

    def _row_to_user(self, row) -> User:
        """Convert database row to User object."""
        return User(
            user_id=row[0],
            username=row[1],
            email=row[2],
            password_hash=row[3],
            roles=set(json.loads(row[4])),
            permissions=set(json.loads(row[5])),
            security_level=SecurityLevel(row[6]),
            is_active=bool(row[7]),
            last_login=datetime.fromisoformat(row[8]) if row[8] else None,
            failed_login_attempts=row[9],
            account_locked_until=datetime.fromisoformat(row[10]) if row[10] else None,
            password_expires=datetime.fromisoformat(row[11]) if row[11] else None,
            two_factor_enabled=bool(row[12]),
            two_factor_secret=row[13],
            created_at=datetime.fromisoformat(row[14]),
            updated_at=datetime.fromisoformat(row[15]),
        )


class AuditManager:
    """Handle audit logging and compliance tracking."""

    def __init__(self):
        self.db_path = "audit.db"
        self._setup_database()

    def _setup_database(self):
        """Setup audit database."""
        conn = sqlite3.connect(self.db_path)

        # Audit logs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                user_id TEXT,
                action TEXT,
                resource TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT,
                risk_score REAL,
                compliance_tags TEXT
            )
        """
        )

        # Security incidents table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS security_incidents (
                incident_id TEXT PRIMARY KEY,
                threat_level TEXT,
                incident_type TEXT,
                description TEXT,
                affected_users TEXT,
                affected_resources TEXT,
                source_ip TEXT,
                detection_time TEXT,
                resolution_time TEXT,
                status TEXT,
                assigned_to TEXT,
                mitigation_actions TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    async def log_action(
        self,
        user_id: str,
        action: AuditAction,
        resource: str,
        details: dict[str, Any],
        ip_address: str,
        user_agent: str = "",
        compliance_tags: list[str] | None = None,
    ) -> str:
        """Log an audit action."""
        try:
            log_id = str(uuid.uuid4())
            risk_score = self._calculate_risk_score(action, details, ip_address)

            audit_log = AuditLog(
                log_id=log_id,
                user_id=user_id,
                action=action,
                resource=resource,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.now(),
                risk_score=risk_score,
                compliance_tags=compliance_tags or [],
            )

            await self._store_audit_log(audit_log)

            # Check for security incidents
            if risk_score > 0.7:
                await self._create_security_incident(audit_log)

            return log_id

        except Exception as e:
            logger.error(f"Error logging audit action: {e}")
            raise

    def _calculate_risk_score(
        self, action: AuditAction, details: dict[str, Any], ip_address: str
    ) -> float:
        """Calculate risk score for action."""
        risk_score = 0.0

        # Base risk by action type
        action_risks = {
            AuditAction.LOGIN: 0.1,
            AuditAction.LOGOUT: 0.0,
            AuditAction.ACCESS_GRANTED: 0.2,
            AuditAction.ACCESS_DENIED: 0.5,
            AuditAction.DATA_READ: 0.1,
            AuditAction.DATA_WRITE: 0.3,
            AuditAction.DATA_DELETE: 0.6,
            AuditAction.CONFIGURATION_CHANGE: 0.7,
            AuditAction.SECURITY_VIOLATION: 0.9,
            AuditAction.PASSWORD_CHANGE: 0.2,
            AuditAction.ACCOUNT_CREATED: 0.3,
            AuditAction.ACCOUNT_DISABLED: 0.4,
        }

        risk_score += action_risks.get(action, 0.3)

        # IP address risk (simplified geolocation check)
        if self._is_suspicious_ip(ip_address):
            risk_score += 0.3

        # Time-based risk (off-hours access)
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:
            risk_score += 0.2

        # Data sensitivity
        if details.get("data_classification") == "confidential":
            risk_score += 0.2
        elif details.get("data_classification") == "restricted":
            risk_score += 0.3

        return min(1.0, risk_score)

    def _is_suspicious_ip(self, ip_address: str) -> bool:
        """Check if IP address is suspicious."""
        try:
            ip = ipaddress.ip_address(ip_address)

            # Check if it's a private IP (less suspicious)
            if ip.is_private:
                return False

            # Add more sophisticated IP reputation checking here
            # For demo, we'll consider certain ranges suspicious
            suspicious_ranges = [
                ipaddress.ip_network("192.0.2.0/24"),  # Documentation range
                ipaddress.ip_network("198.51.100.0/24"),  # Documentation range
            ]

            return any(ip in network for network in suspicious_ranges)

        except ValueError:
            return True  # Invalid IP is suspicious

    async def _create_security_incident(self, audit_log: AuditLog):
        """Create security incident for high-risk actions."""
        incident_id = str(uuid.uuid4())

        # Determine threat level
        if audit_log.risk_score > 0.9:
            threat_level = ThreatLevel.CRITICAL
        elif audit_log.risk_score > 0.7:
            threat_level = ThreatLevel.HIGH
        else:
            threat_level = ThreatLevel.MEDIUM

        incident = SecurityIncident(
            incident_id=incident_id,
            threat_level=threat_level,
            incident_type=f"Suspicious {audit_log.action.value}",
            description=f"High-risk action detected: {audit_log.action.value} on {audit_log.resource}",
            affected_users=[audit_log.user_id],
            affected_resources=[audit_log.resource],
            source_ip=audit_log.ip_address,
            detection_time=audit_log.timestamp,
        )

        await self._store_security_incident(incident)

        # Send alert
        await self._send_security_alert(incident)

    async def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        start_date: datetime,
        end_date: datetime,
        generated_by: str,
    ) -> ComplianceReport:
        """Generate compliance report."""
        try:
            report_id = str(uuid.uuid4())

            # Get relevant audit logs
            audit_logs = await self._get_audit_logs_by_period(start_date, end_date)

            # Analyze compliance based on framework
            findings = []
            compliance_score = 1.0
            recommendations = []

            if framework == ComplianceFramework.SOX:
                findings, compliance_score, recommendations = (
                    self._analyze_sox_compliance(audit_logs)
                )
            elif framework == ComplianceFramework.GDPR:
                findings, compliance_score, recommendations = (
                    self._analyze_gdpr_compliance(audit_logs)
                )
            elif framework == ComplianceFramework.FINRA:
                findings, compliance_score, recommendations = (
                    self._analyze_finra_compliance(audit_logs)
                )
            # Add more frameworks as needed

            report = ComplianceReport(
                report_id=report_id,
                framework=framework,
                report_type="periodic",
                period_start=start_date,
                period_end=end_date,
                findings=findings,
                compliance_score=compliance_score,
                recommendations=recommendations,
                generated_by=generated_by,
                generated_at=datetime.now(),
            )

            await self._store_compliance_report(report)
            return report

        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            raise

    def _analyze_sox_compliance(self, audit_logs: list[AuditLog]) -> tuple:
        """Analyze SOX compliance requirements."""
        findings = []
        score = 1.0
        recommendations = []

        # Check for proper access controls
        access_violations = [
            log
            for log in audit_logs
            if log.action == AuditAction.ACCESS_DENIED and log.risk_score > 0.5
        ]

        if len(access_violations) > 10:
            findings.append(
                {
                    "type": "access_control",
                    "severity": "medium",
                    "description": f"{len(access_violations)} access violations detected",
                    "count": len(access_violations),
                }
            )
            score -= 0.1
            recommendations.append("Review and strengthen access controls")

        # Check for data integrity
        data_changes = [
            log
            for log in audit_logs
            if log.action in [AuditAction.DATA_WRITE, AuditAction.DATA_DELETE]
        ]

        unauthorized_changes = [
            log for log in data_changes if not log.details.get("authorized")
        ]

        if unauthorized_changes:
            findings.append(
                {
                    "type": "data_integrity",
                    "severity": "high",
                    "description": f"{len(unauthorized_changes)} unauthorized data changes",
                    "count": len(unauthorized_changes),
                }
            )
            score -= 0.2
            recommendations.append("Implement stronger data change authorization")

        return findings, max(0.0, score), recommendations

    def _analyze_gdpr_compliance(self, audit_logs: list[AuditLog]) -> tuple:
        """Analyze GDPR compliance requirements."""
        findings = []
        score = 1.0
        recommendations = []

        # Check for data access logging
        data_access_logs = [
            log
            for log in audit_logs
            if log.action == AuditAction.DATA_READ
            and "personal_data" in log.compliance_tags
        ]

        if not data_access_logs:
            findings.append(
                {
                    "type": "data_access_logging",
                    "severity": "medium",
                    "description": "No personal data access logging found",
                    "count": 0,
                }
            )
            score -= 0.15
            recommendations.append(
                "Implement comprehensive personal data access logging"
            )

        # Check for data deletion requests
        deletion_requests = [
            log
            for log in audit_logs
            if log.action == AuditAction.DATA_DELETE
            and "gdpr_deletion" in log.compliance_tags
        ]

        findings.append(
            {
                "type": "data_deletion",
                "severity": "info",
                "description": f"{len(deletion_requests)} GDPR deletion requests processed",
                "count": len(deletion_requests),
            }
        )

        return findings, max(0.0, score), recommendations

    def _analyze_finra_compliance(self, audit_logs: list[AuditLog]) -> tuple:
        """Analyze FINRA compliance requirements."""
        findings = []
        score = 1.0
        recommendations = []

        # Check for trading activity monitoring
        trading_logs = [
            log
            for log in audit_logs
            if "trading" in log.resource
            and log.action in [AuditAction.DATA_WRITE, AuditAction.DATA_READ]
        ]

        if not trading_logs:
            findings.append(
                {
                    "type": "trading_monitoring",
                    "severity": "high",
                    "description": "No trading activity monitoring found",
                    "count": 0,
                }
            )
            score -= 0.3
            recommendations.append(
                "Implement comprehensive trading activity monitoring"
            )

        # Check for communication surveillance
        comm_logs = [log for log in audit_logs if "communication" in log.resource]

        findings.append(
            {
                "type": "communication_surveillance",
                "severity": "info",
                "description": f"{len(comm_logs)} communication events monitored",
                "count": len(comm_logs),
            }
        )

        return findings, max(0.0, score), recommendations

    async def _store_audit_log(self, audit_log: AuditLog):
        """Store audit log in database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO audit_logs
            (log_id, user_id, action, resource, details, ip_address,
             user_agent, timestamp, risk_score, compliance_tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                audit_log.log_id,
                audit_log.user_id,
                audit_log.action.value,
                audit_log.resource,
                json.dumps(audit_log.details),
                audit_log.ip_address,
                audit_log.user_agent,
                audit_log.timestamp.isoformat(),
                audit_log.risk_score,
                json.dumps(audit_log.compliance_tags),
            ),
        )
        conn.commit()
        conn.close()

    async def _store_security_incident(self, incident: SecurityIncident):
        """Store security incident in database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO security_incidents
            (incident_id, threat_level, incident_type, description,
             affected_users, affected_resources, source_ip, detection_time,
             resolution_time, status, assigned_to, mitigation_actions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                incident.incident_id,
                incident.threat_level.value,
                incident.incident_type,
                incident.description,
                json.dumps(incident.affected_users),
                json.dumps(incident.affected_resources),
                incident.source_ip,
                incident.detection_time.isoformat(),
                (
                    incident.resolution_time.isoformat()
                    if incident.resolution_time
                    else None
                ),
                incident.status,
                incident.assigned_to,
                json.dumps(incident.mitigation_actions),
            ),
        )
        conn.commit()
        conn.close()

    async def _store_compliance_report(self, report: ComplianceReport):
        """Store compliance report in database."""
        # Implementation would store in a reports database
        pass

    async def _get_audit_logs_by_period(
        self, start_date: datetime, end_date: datetime
    ) -> list[AuditLog]:
        """Get audit logs for a specific period."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            SELECT * FROM audit_logs
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
        """,
            (start_date.isoformat(), end_date.isoformat()),
        )

        logs = []
        for row in cursor.fetchall():
            logs.append(
                AuditLog(
                    log_id=row[0],
                    user_id=row[1],
                    action=AuditAction(row[2]),
                    resource=row[3],
                    details=json.loads(row[4]),
                    ip_address=row[5],
                    user_agent=row[6],
                    timestamp=datetime.fromisoformat(row[7]),
                    risk_score=row[8],
                    compliance_tags=json.loads(row[9]),
                )
            )

        conn.close()
        return logs

    async def _send_security_alert(self, incident: SecurityIncident):
        """Send security alert notification."""
        # Implementation would send email/SMS alerts to security team
        logger.critical(
            f"SECURITY ALERT: {incident.incident_type} - {incident.description}"
        )


class SecurityManager:
    """Main security manager coordinating all security components."""

    def __init__(self):
        self.encryption = EncryptionManager()
        self.auth = AuthenticationManager(self.encryption)
        self.audit = AuditManager()

    async def initialize_default_admin(self):
        """Initialize default admin account."""
        try:
            admin_user = await self.auth.create_user(
                username="admin",
                email="admin@company.com",
                password=os.environ.get("DEFAULT_ADMIN_PASSWORD", "change-me-immediately"),
                roles={"admin", "security"},
                security_level=SecurityLevel.TOP_SECRET,
            )

            logger.info("Default admin account created")
            return admin_user

        except Exception:
            logger.info("Admin account may already exist")

    def require_auth(self, required_permissions: list[str] | None = None):
        """Decorator to require authentication and authorization."""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract token from request headers (implementation depends on framework)
                token = kwargs.get("auth_token") or getattr(args[0], "auth_token", None)

                if not token:
                    raise SecurityError("Authentication required")

                # Verify token
                payload = self.auth.verify_jwt_token(token)
                if not payload:
                    raise SecurityError("Invalid or expired token")

                # Check permissions if specified
                if required_permissions:
                    user_permissions = set(payload.get("permissions", []))
                    required_perms = set(required_permissions)

                    if (
                        not required_perms.intersection(user_permissions)
                        and "admin:all" not in user_permissions
                    ):
                        raise SecurityError("Insufficient permissions")

                # Add user info to kwargs
                kwargs["current_user"] = payload

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    async def secure_data_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        data: Any,
        ip_address: str,
        security_level: SecurityLevel = SecurityLevel.INTERNAL,
    ) -> Any:
        """Secure wrapper for data access with logging and encryption."""
        try:
            # Authorize access
            authorized = await self.auth.authorize_action(
                user_id, action, resource, security_level
            )

            if not authorized:
                # Log unauthorized access attempt
                await self.audit.log_action(
                    user_id=user_id,
                    action=AuditAction.ACCESS_DENIED,
                    resource=resource,
                    details={"attempted_action": action},
                    ip_address=ip_address,
                )
                raise SecurityError("Access denied")

            # Log authorized access
            await self.audit.log_action(
                user_id=user_id,
                action=AuditAction.ACCESS_GRANTED,
                resource=resource,
                details={"action": action, "data_classification": security_level.value},
                ip_address=ip_address,
                compliance_tags=["data_access"],
            )

            # Encrypt sensitive data if needed
            if security_level in [
                SecurityLevel.CONFIDENTIAL,
                SecurityLevel.RESTRICTED,
                SecurityLevel.TOP_SECRET,
            ]:
                if isinstance(data, str):
                    data = self.encryption.encrypt_symmetric(data)

            return data

        except Exception as e:
            logger.error(f"Error in secure data access: {e}")
            raise


class SecurityError(Exception):
    """Custom security exception."""

    pass


# Example usage and testing
async def main():
    """Example usage of the enterprise security system."""

    # Initialize security manager
    security = SecurityManager()

    # Create default admin
    await security.initialize_default_admin()

    # Create test users
    analyst = await security.auth.create_user(
        username="analyst1",
        email="analyst1@company.com",
        password=os.environ.get("DEFAULT_ADMIN_PASSWORD", "change-me-immediately"),
        roles={"analyst"},
        security_level=SecurityLevel.CONFIDENTIAL,
    )

    trader = await security.auth.create_user(
        username="trader1",
        email="trader1@company.com",
        password=os.environ.get("DEFAULT_ADMIN_PASSWORD", "change-me-immediately"),
        roles={"trader"},
        security_level=SecurityLevel.INTERNAL,
    )

    print(f"Created users: {analyst.username}, {trader.username}")

    # Test authentication
    auth_result = await security.auth.authenticate_user(
        username="analyst1",
        password=os.environ.get("DEFAULT_ADMIN_PASSWORD", "change-me-immediately"),
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0...",
    )

    if auth_result:
        print(f"Authentication successful: {auth_result['username']}")

        # Test authorization
        authorized = await security.auth.authorize_action(
            user_id=auth_result["user_id"],
            action="read",
            resource="financial_data",
            resource_security_level=SecurityLevel.INTERNAL,
        )

        print(f"Authorization result: {authorized}")

        # Test audit logging
        await security.audit.log_action(
            user_id=auth_result["user_id"],
            action=AuditAction.DATA_READ,
            resource="financial_data",
            details={"query": "SELECT * FROM stock_prices"},
            ip_address="192.168.1.100",
            compliance_tags=["sox", "finra"],
        )

        print("Audit log created")

        # Generate compliance report
        report = await security.audit.generate_compliance_report(
            framework=ComplianceFramework.SOX,
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            generated_by=auth_result["user_id"],
        )

        print(f"Compliance report generated: {report.compliance_score:.2f}")

    else:
        print("Authentication failed")


if __name__ == "__main__":
    asyncio.run(main())
