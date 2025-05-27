"""
API Management & Developer Tools Module

This module provides comprehensive API management capabilities including gateway functionality,
rate limiting, authentication, documentation generation, monitoring, and developer portal.
"""

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import yaml
from aiohttp import web

logger = logging.getLogger(__name__)


class APIMethod(Enum):
    """HTTP methods for API endpoints."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class RateLimitType(Enum):
    """Rate limiting strategies."""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


class APIStatus(Enum):
    """API endpoint status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    BETA = "beta"
    ALPHA = "alpha"
    DISABLED = "disabled"


class SubscriptionTier(Enum):
    """API subscription tiers."""

    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    UNLIMITED = "unlimited"


@dataclass
class APIEndpoint:
    """API endpoint definition."""

    endpoint_id: str
    path: str
    method: APIMethod
    handler: Callable
    description: str
    version: str = "v1"
    status: APIStatus = APIStatus.ACTIVE
    rate_limit: dict[str, int] | None = None
    auth_required: bool = True
    scopes: list[str] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class APIKey:
    """API key information."""

    key_id: str
    key_value: str
    user_id: str
    name: str
    description: str
    subscription_tier: SubscriptionTier
    scopes: list[str]
    rate_limits: dict[str, int]
    created_at: datetime
    expires_at: datetime | None = None
    last_used: datetime | None = None
    is_active: bool = True
    usage_count: int = 0


@dataclass
class APIUsageMetric:
    """API usage metrics."""

    metric_id: str
    api_key: str
    endpoint: str
    method: str
    timestamp: datetime
    response_time: float
    status_code: int
    request_size: int
    response_size: int
    ip_address: str
    user_agent: str


@dataclass
class RateLimit:
    """Rate limiting configuration."""

    limit_id: str
    name: str
    limit_type: RateLimitType
    requests_per_window: int
    window_size_seconds: int
    subscription_tiers: list[SubscriptionTier]
    endpoints: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class APIDocumentation:
    """API documentation."""

    doc_id: str
    title: str
    description: str
    version: str
    base_url: str
    endpoints: list[APIEndpoint]
    schemas: dict[str, dict] = field(default_factory=dict)
    examples: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)


class RateLimiter:
    """Rate limiting implementation with multiple strategies."""

    def __init__(self):
        self.windows = defaultdict(dict)  # Fixed window counters
        self.buckets = defaultdict(dict)  # Token buckets
        self.sliding_windows = defaultdict(lambda: defaultdict(deque))

    async def check_rate_limit(
        self, key: str, rate_limit: RateLimit, client_id: str
    ) -> dict[str, Any]:
        """Check if request is within rate limits."""
        current_time = time.time()

        if rate_limit.limit_type == RateLimitType.FIXED_WINDOW:
            return await self._check_fixed_window(key, rate_limit, current_time)
        elif rate_limit.limit_type == RateLimitType.SLIDING_WINDOW:
            return await self._check_sliding_window(key, rate_limit, current_time)
        elif rate_limit.limit_type == RateLimitType.TOKEN_BUCKET:
            return await self._check_token_bucket(key, rate_limit, current_time)
        else:
            return {"allowed": True, "remaining": rate_limit.requests_per_window}

    async def _check_fixed_window(
        self, key: str, rate_limit: RateLimit, current_time: float
    ) -> dict[str, Any]:
        """Check fixed window rate limit."""
        window_start = (
            int(current_time // rate_limit.window_size_seconds)
            * rate_limit.window_size_seconds
        )

        if key not in self.windows:
            self.windows[key] = {}

        if window_start not in self.windows[key]:
            self.windows[key][window_start] = 0

        # Clean old windows
        old_windows = [w for w in self.windows[key] if w < window_start]
        for old_window in old_windows:
            del self.windows[key][old_window]

        current_count = self.windows[key][window_start]

        if current_count >= rate_limit.requests_per_window:
            return {
                "allowed": False,
                "remaining": 0,
                "reset_time": window_start + rate_limit.window_size_seconds,
            }

        self.windows[key][window_start] += 1

        return {
            "allowed": True,
            "remaining": rate_limit.requests_per_window - current_count - 1,
            "reset_time": window_start + rate_limit.window_size_seconds,
        }

    async def _check_sliding_window(
        self, key: str, rate_limit: RateLimit, current_time: float
    ) -> dict[str, Any]:
        """Check sliding window rate limit."""
        window = self.sliding_windows[key][rate_limit.limit_id]

        # Remove old requests outside the window
        cutoff_time = current_time - rate_limit.window_size_seconds
        while window and window[0] < cutoff_time:
            window.popleft()

        if len(window) >= rate_limit.requests_per_window:
            return {
                "allowed": False,
                "remaining": 0,
                "reset_time": window[0] + rate_limit.window_size_seconds,
            }

        window.append(current_time)

        return {
            "allowed": True,
            "remaining": rate_limit.requests_per_window - len(window),
            "reset_time": None,
        }

    async def _check_token_bucket(
        self, key: str, rate_limit: RateLimit, current_time: float
    ) -> dict[str, Any]:
        """Check token bucket rate limit."""
        if key not in self.buckets:
            self.buckets[key] = {
                "tokens": rate_limit.requests_per_window,
                "last_refill": current_time,
            }

        bucket = self.buckets[key]

        # Refill tokens based on time elapsed
        time_elapsed = current_time - bucket["last_refill"]
        tokens_to_add = (
            time_elapsed / rate_limit.window_size_seconds
        ) * rate_limit.requests_per_window
        bucket["tokens"] = min(
            rate_limit.requests_per_window, bucket["tokens"] + tokens_to_add
        )
        bucket["last_refill"] = current_time

        if bucket["tokens"] < 1:
            return {
                "allowed": False,
                "remaining": 0,
                "reset_time": current_time + rate_limit.window_size_seconds,
            }

        bucket["tokens"] -= 1

        return {"allowed": True, "remaining": int(bucket["tokens"]), "reset_time": None}


class APIGateway:
    """API Gateway handling routing, authentication, and rate limiting."""

    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
        self.endpoints = {}
        self.rate_limits = {}
        self.middleware = []
        self.db_path = "api_management.db"
        self._setup_database()

    def _setup_database(self):
        """Setup API management database."""
        conn = sqlite3.connect(self.db_path)

        # API keys table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_value TEXT UNIQUE,
                user_id TEXT,
                name TEXT,
                description TEXT,
                subscription_tier TEXT,
                scopes TEXT,
                rate_limits TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used TEXT,
                is_active BOOLEAN,
                usage_count INTEGER
            )
        """
        )

        # API usage metrics table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_usage_metrics (
                metric_id TEXT PRIMARY KEY,
                api_key TEXT,
                endpoint TEXT,
                method TEXT,
                timestamp TEXT,
                response_time REAL,
                status_code INTEGER,
                request_size INTEGER,
                response_size INTEGER,
                ip_address TEXT,
                user_agent TEXT
            )
        """
        )

        # Rate limits table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rate_limits (
                limit_id TEXT PRIMARY KEY,
                name TEXT,
                limit_type TEXT,
                requests_per_window INTEGER,
                window_size_seconds INTEGER,
                subscription_tiers TEXT,
                endpoints TEXT,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def register_endpoint(self, endpoint: APIEndpoint):
        """Register an API endpoint."""
        route_key = f"{endpoint.method.value}:{endpoint.path}"
        self.endpoints[route_key] = endpoint
        logger.info(f"Registered endpoint: {route_key}")

    def add_rate_limit(self, rate_limit: RateLimit):
        """Add a rate limit configuration."""
        self.rate_limits[rate_limit.limit_id] = rate_limit
        logger.info(f"Added rate limit: {rate_limit.name}")

    def add_middleware(self, middleware: Callable):
        """Add middleware function."""
        self.middleware.append(middleware)

    async def handle_request(self, request: web.Request) -> web.Response:
        """Handle incoming API request."""
        start_time = time.time()

        try:
            # Apply middleware
            for middleware in self.middleware:
                response = await middleware(request)
                if response:
                    return response

            # Find matching endpoint
            route_key = f"{request.method}:{request.path}"
            endpoint = self.endpoints.get(route_key)

            if not endpoint:
                return web.json_response({"error": "Endpoint not found"}, status=404)

            # Check if endpoint is active
            if endpoint.status == APIStatus.DISABLED:
                return web.json_response({"error": "Endpoint is disabled"}, status=503)

            # Authentication
            if endpoint.auth_required:
                auth_result = await self._authenticate_request(request)
                if not auth_result["success"]:
                    return web.json_response(
                        {"error": auth_result["error"]}, status=401
                    )

                api_key = auth_result["api_key"]

                # Rate limiting
                rate_limit_result = await self._check_rate_limits(
                    request, endpoint, api_key
                )

                if not rate_limit_result["allowed"]:
                    return web.json_response(
                        {"error": "Rate limit exceeded"},
                        status=429,
                        headers={
                            "X-RateLimit-Remaining": str(
                                rate_limit_result["remaining"]
                            ),
                            "X-RateLimit-Reset": str(
                                rate_limit_result.get("reset_time", "")
                            ),
                        },
                    )

            # Execute endpoint handler
            response = await endpoint.handler(request)

            # Log usage metrics
            end_time = time.time()
            await self._log_usage_metric(
                request,
                endpoint,
                api_key if endpoint.auth_required else None,
                response,
                start_time,
                end_time,
            )

            return response

        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _authenticate_request(self, request: web.Request) -> dict[str, Any]:
        """Authenticate API request."""
        # Check for API key in headers
        api_key_header = request.headers.get("X-API-Key")
        if not api_key_header:
            # Check in query parameters
            api_key_header = request.query.get("api_key")

        if not api_key_header:
            return {"success": False, "error": "API key required"}

        # Validate API key
        api_key = await self._get_api_key(api_key_header)
        if not api_key:
            return {"success": False, "error": "Invalid API key"}

        if not api_key.is_active:
            return {"success": False, "error": "API key is inactive"}

        if api_key.expires_at and datetime.now() > api_key.expires_at:
            return {"success": False, "error": "API key has expired"}

        return {"success": True, "api_key": api_key}

    async def _check_rate_limits(
        self, request: web.Request, endpoint: APIEndpoint, api_key: APIKey
    ) -> dict[str, Any]:
        """Check rate limits for request."""
        # Check endpoint-specific rate limits
        if endpoint.rate_limit:
            rate_limit = RateLimit(
                limit_id=f"endpoint_{endpoint.endpoint_id}",
                name=f"Rate limit for {endpoint.path}",
                limit_type=RateLimitType.FIXED_WINDOW,
                requests_per_window=endpoint.rate_limit["requests"],
                window_size_seconds=endpoint.rate_limit["window"],
                subscription_tiers=[api_key.subscription_tier],
            )

            result = await self.rate_limiter.check_rate_limit(
                f"{api_key.key_id}:{endpoint.endpoint_id}", rate_limit, api_key.key_id
            )

            if not result["allowed"]:
                return result

        # Check subscription tier rate limits
        tier_limits = api_key.rate_limits
        if tier_limits:
            for limit_name, limit_config in tier_limits.items():
                rate_limit = RateLimit(
                    limit_id=f"tier_{limit_name}",
                    name=f"Tier limit: {limit_name}",
                    limit_type=RateLimitType.FIXED_WINDOW,
                    requests_per_window=limit_config["requests"],
                    window_size_seconds=limit_config["window"],
                    subscription_tiers=[api_key.subscription_tier],
                )

                result = await self.rate_limiter.check_rate_limit(
                    f"{api_key.key_id}:{limit_name}", rate_limit, api_key.key_id
                )

                if not result["allowed"]:
                    return result

        return {"allowed": True, "remaining": 1000}  # Default

    async def _get_api_key(self, key_value: str) -> APIKey | None:
        """Get API key from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT * FROM api_keys WHERE key_value = ? AND is_active = 1",
                (key_value,),
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return APIKey(
                    key_id=row[0],
                    key_value=row[1],
                    user_id=row[2],
                    name=row[3],
                    description=row[4],
                    subscription_tier=SubscriptionTier(row[5]),
                    scopes=json.loads(row[6]),
                    rate_limits=json.loads(row[7]),
                    created_at=datetime.fromisoformat(row[8]),
                    expires_at=datetime.fromisoformat(row[9]) if row[9] else None,
                    last_used=datetime.fromisoformat(row[10]) if row[10] else None,
                    is_active=bool(row[11]),
                    usage_count=row[12],
                )

            return None

        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            return None

    async def _log_usage_metric(
        self,
        request: web.Request,
        endpoint: APIEndpoint,
        api_key: APIKey | None,
        response: web.Response,
        start_time: float,
        end_time: float,
    ):
        """Log API usage metrics."""
        try:
            metric = APIUsageMetric(
                metric_id=str(uuid.uuid4()),
                api_key=api_key.key_id if api_key else "anonymous",
                endpoint=endpoint.path,
                method=endpoint.method.value,
                timestamp=datetime.now(),
                response_time=end_time - start_time,
                status_code=response.status,
                request_size=(
                    len(await request.read()) if hasattr(request, "read") else 0
                ),
                response_size=len(response.body) if hasattr(response, "body") else 0,
                ip_address=request.remote,
                user_agent=request.headers.get("User-Agent", ""),
            )

            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO api_usage_metrics
                (metric_id, api_key, endpoint, method, timestamp, response_time,
                 status_code, request_size, response_size, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metric.metric_id,
                    metric.api_key,
                    metric.endpoint,
                    metric.method,
                    metric.timestamp.isoformat(),
                    metric.response_time,
                    metric.status_code,
                    metric.request_size,
                    metric.response_size,
                    metric.ip_address,
                    metric.user_agent,
                ),
            )
            conn.commit()
            conn.close()

            # Update API key usage count
            if api_key:
                await self._update_api_key_usage(api_key.key_id)

        except Exception as e:
            logger.error(f"Error logging usage metric: {e}")

    async def _update_api_key_usage(self, key_id: str):
        """Update API key usage statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                UPDATE api_keys
                SET usage_count = usage_count + 1, last_used = ?
                WHERE key_id = ?
            """,
                (datetime.now().isoformat(), key_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating API key usage: {e}")


class APIKeyManager:
    """Manage API keys and subscriptions."""

    def __init__(self):
        self.db_path = "api_management.db"
        self.subscription_limits = {
            SubscriptionTier.FREE: {
                "requests_per_hour": 100,
                "requests_per_day": 1000,
                "rate_limits": {
                    "hourly": {"requests": 100, "window": 3600},
                    "daily": {"requests": 1000, "window": 86400},
                },
            },
            SubscriptionTier.BASIC: {
                "requests_per_hour": 1000,
                "requests_per_day": 10000,
                "rate_limits": {
                    "hourly": {"requests": 1000, "window": 3600},
                    "daily": {"requests": 10000, "window": 86400},
                },
            },
            SubscriptionTier.PROFESSIONAL: {
                "requests_per_hour": 10000,
                "requests_per_day": 100000,
                "rate_limits": {
                    "hourly": {"requests": 10000, "window": 3600},
                    "daily": {"requests": 100000, "window": 86400},
                },
            },
            SubscriptionTier.ENTERPRISE: {
                "requests_per_hour": 50000,
                "requests_per_day": 500000,
                "rate_limits": {
                    "hourly": {"requests": 50000, "window": 3600},
                    "daily": {"requests": 500000, "window": 86400},
                },
            },
            SubscriptionTier.UNLIMITED: {
                "requests_per_hour": float("inf"),
                "requests_per_day": float("inf"),
                "rate_limits": {},
            },
        }

    async def create_api_key(
        self,
        user_id: str,
        name: str,
        description: str,
        subscription_tier: SubscriptionTier,
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
    ) -> APIKey:
        """Create a new API key."""
        try:
            key_id = str(uuid.uuid4())
            key_value = self._generate_api_key()

            expires_at = None
            if expires_in_days:
                expires_at = datetime.now() + timedelta(days=expires_in_days)

            rate_limits = self.subscription_limits[subscription_tier]["rate_limits"]

            api_key = APIKey(
                key_id=key_id,
                key_value=key_value,
                user_id=user_id,
                name=name,
                description=description,
                subscription_tier=subscription_tier,
                scopes=scopes or [],
                rate_limits=rate_limits,
                created_at=datetime.now(),
                expires_at=expires_at,
            )

            # Store in database
            await self._store_api_key(api_key)

            logger.info(f"Created API key for user {user_id}: {name}")
            return api_key

        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            raise

    def _generate_api_key(self) -> str:
        """Generate a secure API key."""
        # Create a unique identifier
        unique_id = str(uuid.uuid4()).replace("-", "")
        timestamp = str(int(time.time()))

        # Create hash
        hash_input = f"{unique_id}{timestamp}".encode()
        api_key = hashlib.sha256(hash_input).hexdigest()

        # Format as API key
        return f"fn_{api_key[:32]}"

    async def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE api_keys SET is_active = 0 WHERE key_id = ?", (key_id,)
            )
            conn.commit()
            conn.close()

            logger.info(f"Revoked API key: {key_id}")
            return True

        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False

    async def get_user_api_keys(self, user_id: str) -> list[APIKey]:
        """Get all API keys for a user."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            conn.close()

            api_keys = []
            for row in rows:
                api_key = APIKey(
                    key_id=row[0],
                    key_value=row[1],
                    user_id=row[2],
                    name=row[3],
                    description=row[4],
                    subscription_tier=SubscriptionTier(row[5]),
                    scopes=json.loads(row[6]),
                    rate_limits=json.loads(row[7]),
                    created_at=datetime.fromisoformat(row[8]),
                    expires_at=datetime.fromisoformat(row[9]) if row[9] else None,
                    last_used=datetime.fromisoformat(row[10]) if row[10] else None,
                    is_active=bool(row[11]),
                    usage_count=row[12],
                )
                api_keys.append(api_key)

            return api_keys

        except Exception as e:
            logger.error(f"Error getting user API keys: {e}")
            return []

    async def _store_api_key(self, api_key: APIKey):
        """Store API key in database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO api_keys
            (key_id, key_value, user_id, name, description, subscription_tier,
             scopes, rate_limits, created_at, expires_at, last_used, is_active, usage_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                api_key.key_id,
                api_key.key_value,
                api_key.user_id,
                api_key.name,
                api_key.description,
                api_key.subscription_tier.value,
                json.dumps(api_key.scopes),
                json.dumps(api_key.rate_limits),
                api_key.created_at.isoformat(),
                api_key.expires_at.isoformat() if api_key.expires_at else None,
                api_key.last_used.isoformat() if api_key.last_used else None,
                api_key.is_active,
                api_key.usage_count,
            ),
        )
        conn.commit()
        conn.close()


class APIMonitoringService:
    """Monitor API usage, performance, and health."""

    def __init__(self):
        self.db_path = "api_management.db"
        self.metrics_cache = {}

    async def get_usage_analytics(
        self, start_date: datetime, end_date: datetime, api_key: str | None = None
    ) -> dict[str, Any]:
        """Get API usage analytics for a period."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Base query
            base_query = """
                SELECT endpoint, method, COUNT(*) as request_count,
                       AVG(response_time) as avg_response_time,
                       MIN(response_time) as min_response_time,
                       MAX(response_time) as max_response_time,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count,
                       DATE(timestamp) as date
                FROM api_usage_metrics
                WHERE timestamp >= ? AND timestamp <= ?
            """
            params = [start_date.isoformat(), end_date.isoformat()]

            if api_key:
                base_query += " AND api_key = ?"
                params.append(api_key)

            base_query += " GROUP BY endpoint, method, DATE(timestamp)"

            cursor = conn.execute(base_query, params)
            rows = cursor.fetchall()

            # Process results
            analytics = {
                "total_requests": 0,
                "total_errors": 0,
                "avg_response_time": 0,
                "endpoints": {},
                "daily_stats": defaultdict(
                    lambda: {"requests": 0, "errors": 0, "avg_response_time": 0}
                ),
            }

            total_response_time = 0

            for row in rows:
                endpoint, method, count, avg_rt, min_rt, max_rt, errors, date = row

                analytics["total_requests"] += count
                analytics["total_errors"] += errors
                total_response_time += avg_rt * count

                # Endpoint stats
                endpoint_key = f"{method} {endpoint}"
                if endpoint_key not in analytics["endpoints"]:
                    analytics["endpoints"][endpoint_key] = {
                        "requests": 0,
                        "errors": 0,
                        "avg_response_time": 0,
                        "min_response_time": float("inf"),
                        "max_response_time": 0,
                    }

                ep_stats = analytics["endpoints"][endpoint_key]
                ep_stats["requests"] += count
                ep_stats["errors"] += errors
                ep_stats["avg_response_time"] = (
                    ep_stats["avg_response_time"] * (ep_stats["requests"] - count)
                    + avg_rt * count
                ) / ep_stats["requests"]
                ep_stats["min_response_time"] = min(
                    ep_stats["min_response_time"], min_rt
                )
                ep_stats["max_response_time"] = max(
                    ep_stats["max_response_time"], max_rt
                )

                # Daily stats
                analytics["daily_stats"][date]["requests"] += count
                analytics["daily_stats"][date]["errors"] += errors
                analytics["daily_stats"][date]["avg_response_time"] = avg_rt

            # Calculate overall average response time
            if analytics["total_requests"] > 0:
                analytics["avg_response_time"] = (
                    total_response_time / analytics["total_requests"]
                )
                analytics["error_rate"] = (
                    analytics["total_errors"] / analytics["total_requests"]
                )

            conn.close()
            return analytics

        except Exception as e:
            logger.error(f"Error getting usage analytics: {e}")
            return {}

    async def generate_usage_charts(self, analytics: dict[str, Any]) -> dict[str, str]:
        """Generate usage charts from analytics data."""
        charts = {}

        try:
            # Daily requests chart
            daily_data = analytics.get("daily_stats", {})
            if daily_data:
                dates = list(daily_data.keys())
                requests = [daily_data[date]["requests"] for date in dates]
                errors = [daily_data[date]["errors"] for date in dates]

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=dates, y=requests, name="Requests", mode="lines+markers"
                    )
                )
                fig.add_trace(
                    go.Scatter(x=dates, y=errors, name="Errors", mode="lines+markers")
                )

                fig.update_layout(
                    title="Daily API Usage",
                    xaxis_title="Date",
                    yaxis_title="Count",
                    template="plotly_white",
                )

                charts["daily_usage"] = fig.to_html(include_plotlyjs="cdn")

            # Endpoint performance chart
            endpoints = analytics.get("endpoints", {})
            if endpoints:
                ep_names = list(endpoints.keys())
                response_times = [endpoints[ep]["avg_response_time"] for ep in ep_names]

                fig = go.Figure(
                    data=go.Bar(
                        x=ep_names,
                        y=response_times,
                        text=[f"{rt:.2f}ms" for rt in response_times],
                        textposition="auto",
                    )
                )

                fig.update_layout(
                    title="Average Response Time by Endpoint",
                    xaxis_title="Endpoint",
                    yaxis_title="Response Time (ms)",
                    template="plotly_white",
                    xaxis={"tickangle": 45},
                )

                charts["endpoint_performance"] = fig.to_html(include_plotlyjs="cdn")

            return charts

        except Exception as e:
            logger.error(f"Error generating usage charts: {e}")
            return {}


class APIDocumentationGenerator:
    """Generate comprehensive API documentation."""

    def __init__(self):
        self.templates_dir = Path("templates")
        self.templates_dir.mkdir(exist_ok=True)
        self._create_templates()

    def _create_templates(self):
        """Create documentation templates."""
        # Main documentation template
        main_template = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }} - API Documentation</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.24.1/themes/prism.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100vh; overflow-y: auto; }
        .content { margin-left: 250px; padding: 20px; }
        .endpoint-card { margin-bottom: 20px; }
        .method-badge { font-size: 0.8em; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar -->
            <div class="col-md-3 col-lg-2 sidebar bg-light p-3">
                <h5>{{ title }}</h5>
                <p class="text-muted">Version {{ version }}</p>
                <hr>
                <ul class="nav flex-column">
                    {% for endpoint in endpoints %}
                    <li class="nav-item">
                        <a class="nav-link" href="#{{ endpoint.endpoint_id }}">
                            <span class="badge bg-{{ endpoint.method.value.lower() == 'get' and 'primary' or
                                                     endpoint.method.value.lower() == 'post' and 'success' or
                                                     endpoint.method.value.lower() == 'put' and 'warning' or
                                                     endpoint.method.value.lower() == 'delete' and 'danger' or 'secondary' }}
                                        method-badge">{{ endpoint.method.value }}</span>
                            {{ endpoint.path }}
                        </a>
                    </li>
                    {% endfor %}
                </ul>
            </div>

            <!-- Main content -->
            <div class="col-md-9 col-lg-10 content">
                <h1>{{ title }}</h1>
                <p class="lead">{{ description }}</p>

                <div class="alert alert-info">
                    <strong>Base URL:</strong> <code>{{ base_url }}</code>
                </div>

                <h2>Authentication</h2>
                <p>This API uses API key authentication. Include your API key in the request headers:</p>
                <pre><code>X-API-Key: your_api_key_here</code></pre>

                <h2>Endpoints</h2>
                {% for endpoint in endpoints %}
                <div class="card endpoint-card" id="{{ endpoint.endpoint_id }}">
                    <div class="card-header">
                        <h5>
                            <span class="badge bg-{{ endpoint.method.value.lower() == 'get' and 'primary' or
                                                     endpoint.method.value.lower() == 'post' and 'success' or
                                                     endpoint.method.value.lower() == 'put' and 'warning' or
                                                     endpoint.method.value.lower() == 'delete' and 'danger' or 'secondary' }}">
                                {{ endpoint.method.value }}
                            </span>
                            {{ endpoint.path }}
                        </h5>
                        <p class="mb-0">{{ endpoint.description }}</p>
                    </div>
                    <div class="card-body">
                        {% if endpoint.parameters %}
                        <h6>Parameters</h6>
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Type</th>
                                    <th>Required</th>
                                    <th>Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for param in endpoint.parameters %}
                                <tr>
                                    <td><code>{{ param.name }}</code></td>
                                    <td>{{ param.type }}</td>
                                    <td>{{ param.required and 'Yes' or 'No' }}</td>
                                    <td>{{ param.description }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        {% endif %}

                        <h6>Example Request</h6>
                        <pre><code class="language-bash">curl -X {{ endpoint.method.value }} \\
  "{{ base_url }}{{ endpoint.path }}" \\
  -H "X-API-Key: your_api_key_here" \\
  -H "Content-Type: application/json"</code></pre>

                        {% if endpoint.responses %}
                        <h6>Responses</h6>
                        {% for status_code, response in endpoint.responses.items() %}
                        <div class="mb-3">
                            <strong>{{ status_code }}</strong> - {{ response.description }}
                            {% if response.example %}
                            <pre><code class="language-json">{{ response.example | tojson(indent=2) }}</code></pre>
                            {% endif %}
                        </div>
                        {% endfor %}
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.24.1/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.24.1/plugins/autoloader/prism-autoloader.min.js"></script>
</body>
</html>
        """

        with open(self.templates_dir / "api_docs.html", "w") as f:
            f.write(main_template)

    async def generate_documentation(
        self,
        endpoints: list[APIEndpoint],
        title: str = "Financial News API",
        description: str = "Comprehensive financial news and analysis API",
        version: str = "v1",
        base_url: str = "https://api.financialnews.com",
    ) -> str:
        """Generate HTML documentation for API endpoints."""
        try:
            from jinja2 import Environment, FileSystemLoader

            env = Environment(loader=FileSystemLoader(self.templates_dir))
            template = env.get_template("api_docs.html")

            # Group endpoints by tags
            grouped_endpoints = {}
            for endpoint in endpoints:
                for tag in endpoint.tags or ["General"]:
                    if tag not in grouped_endpoints:
                        grouped_endpoints[tag] = []
                    grouped_endpoints[tag].append(endpoint)

            html = template.render(
                title=title,
                description=description,
                version=version,
                base_url=base_url,
                endpoints=endpoints,
                grouped_endpoints=grouped_endpoints,
            )

            return html

        except Exception as e:
            logger.error(f"Error generating documentation: {e}")
            return f"<h1>Error generating documentation: {e}</h1>"

    async def generate_openapi_spec(
        self,
        endpoints: list[APIEndpoint],
        title: str = "Financial News API",
        description: str = "Comprehensive financial news and analysis API",
        version: str = "v1",
    ) -> dict[str, Any]:
        """Generate OpenAPI 3.0 specification."""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": title,
                "description": description,
                "version": version,
                "contact": {"email": "support@financialnews.com"},
            },
            "servers": [
                {
                    "url": "https://api.financialnews.com",
                    "description": "Production server",
                },
                {
                    "url": "https://staging-api.financialnews.com",
                    "description": "Staging server",
                },
            ],
            "components": {
                "securitySchemes": {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key",
                    }
                }
            },
            "security": [{"ApiKeyAuth": []}],
            "paths": {},
        }

        # Convert endpoints to OpenAPI paths
        for endpoint in endpoints:
            path = endpoint.path
            method = endpoint.method.value.lower()

            if path not in spec["paths"]:
                spec["paths"][path] = {}

            spec["paths"][path][method] = {
                "summary": endpoint.description,
                "operationId": endpoint.endpoint_id,
                "tags": endpoint.tags or ["General"],
                "parameters": [
                    {
                        "name": param["name"],
                        "in": param.get("in", "query"),
                        "required": param.get("required", False),
                        "schema": {"type": param.get("type", "string")},
                        "description": param.get("description", ""),
                    }
                    for param in endpoint.parameters
                ],
                "responses": (
                    {
                        status: {
                            "description": response.get("description", ""),
                            "content": {
                                "application/json": {
                                    "schema": response.get("schema", {"type": "object"})
                                }
                            },
                        }
                        for status, response in endpoint.responses.items()
                    }
                    if endpoint.responses
                    else {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    }
                ),
            }

        return spec


class DeveloperPortal:
    """Developer portal with API key management and documentation."""

    def __init__(
        self, api_key_manager: APIKeyManager, doc_generator: APIDocumentationGenerator
    ):
        self.api_key_manager = api_key_manager
        self.doc_generator = doc_generator
        self.monitoring = APIMonitoringService()

    async def create_portal_dashboard(self, user_id: str) -> str:
        """Create developer portal dashboard HTML."""
        try:
            # Get user's API keys
            api_keys = await self.api_key_manager.get_user_api_keys(user_id)

            # Get usage analytics for user's keys
            if api_keys:
                start_date = datetime.now() - timedelta(days=30)
                end_date = datetime.now()

                analytics = await self.monitoring.get_usage_analytics(
                    start_date, end_date, api_keys[0].key_id
                )
            else:
                analytics = {}

            # Create dashboard HTML
            dashboard_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Developer Portal</title>
                <meta charset="utf-8">
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            </head>
            <body>
                <div class="container mt-4">
                    <h1>Developer Portal</h1>

                    <div class="row">
                        <div class="col-md-8">
                            <div class="card">
                                <div class="card-header">
                                    <h5>API Keys</h5>
                                </div>
                                <div class="card-body">
                                    <table class="table">
                                        <thead>
                                            <tr>
                                                <th>Name</th>
                                                <th>Tier</th>
                                                <th>Usage</th>
                                                <th>Last Used</th>
                                                <th>Status</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {''.join([
                                                f'<tr><td>{key.name}</td><td>{key.subscription_tier.value}</td>'
                                                f'<td>{key.usage_count}</td>'
                                                f'<td>{key.last_used.strftime("%Y-%m-%d") if key.last_used else "Never"}</td>'
                                                f'<td><span class="badge bg-{"success" if key.is_active else "danger"}">'
                                                f'{"Active" if key.is_active else "Inactive"}</span></td></tr>'
                                                for key in api_keys
                                            ])}
                                        </tbody>
                                    </table>
                                    <button class="btn btn-primary" onclick="createAPIKey()">Create New API Key</button>
                                </div>
                            </div>
                        </div>

                        <div class="col-md-4">
                            <div class="card">
                                <div class="card-header">
                                    <h5>Usage Statistics (30 days)</h5>
                                </div>
                                <div class="card-body">
                                    <p><strong>Total Requests:</strong> {analytics.get('total_requests', 0)}</p>
                                    <p><strong>Error Rate:</strong> {analytics.get('error_rate', 0)*100:.1f}%</p>
                                    <p><strong>Avg Response Time:</strong> {analytics.get('avg_response_time', 0):.2f}ms</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="row mt-4">
                        <div class="col-12">
                            <div class="card">
                                <div class="card-header">
                                    <h5>Quick Start</h5>
                                </div>
                                <div class="card-body">
                                    <p>Get started with our API in minutes:</p>
                                    <ol>
                                        <li>Create an API key above</li>
                                        <li>Review our <a href="/docs">API documentation</a></li>
                                        <li>Start making requests</li>
                                    </ol>

                                    <h6>Example Request</h6>
                                    <pre><code>curl -H "X-API-Key: your_api_key" https://api.financialnews.com/v1/news</code></pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <script>
                function createAPIKey() {{
                    // Implementation for creating API key
                    alert('Create API Key functionality would be implemented here');
                }}
                </script>
            </body>
            </html>
            """

            return dashboard_html

        except Exception as e:
            logger.error(f"Error creating portal dashboard: {e}")
            return f"<h1>Error: {e}</h1>"


# Example usage and testing
async def main():
    """Example usage of the API management system."""

    # Initialize components
    rate_limiter = RateLimiter()
    gateway = APIGateway(rate_limiter)
    key_manager = APIKeyManager()
    doc_generator = APIDocumentationGenerator()
    portal = DeveloperPortal(key_manager, doc_generator)

    # Example endpoint handler
    async def get_news(request):
        """Get latest financial news."""
        return web.json_response(
            {
                "news": [
                    {"title": "Market Update", "content": "Markets are up today..."},
                    {"title": "Earnings Report", "content": "Company XYZ reports..."},
                ]
            }
        )

    async def get_stock_price(request):
        """Get stock price."""
        symbol = request.query.get("symbol", "AAPL")
        return web.json_response({"symbol": symbol, "price": 150.00, "change": 2.50})

    # Register endpoints
    news_endpoint = APIEndpoint(
        endpoint_id="get_news",
        path="/v1/news",
        method=APIMethod.GET,
        handler=get_news,
        description="Get latest financial news",
        rate_limit={"requests": 100, "window": 3600},
        parameters=[
            {
                "name": "limit",
                "type": "integer",
                "description": "Number of news items to return",
            }
        ],
        responses={"200": {"description": "Success", "example": {"news": []}}},
        tags=["News"],
    )

    stock_endpoint = APIEndpoint(
        endpoint_id="get_stock_price",
        path="/v1/stock/price",
        method=APIMethod.GET,
        handler=get_stock_price,
        description="Get current stock price",
        parameters=[
            {
                "name": "symbol",
                "type": "string",
                "required": True,
                "description": "Stock symbol",
            }
        ],
        responses={
            "200": {
                "description": "Success",
                "example": {"symbol": "AAPL", "price": 150.00},
            }
        },
        tags=["Stocks"],
    )

    gateway.register_endpoint(news_endpoint)
    gateway.register_endpoint(stock_endpoint)

    # Create test API key
    test_api_key = await key_manager.create_api_key(
        user_id="test_user",
        name="Test API Key",
        description="API key for testing",
        subscription_tier=SubscriptionTier.BASIC,
        scopes=["read:news", "read:stocks"],
    )

    print(f"Created test API key: {test_api_key.key_value}")

    # Generate documentation
    documentation = await doc_generator.generate_documentation(
        endpoints=[news_endpoint, stock_endpoint]
    )

    # Save documentation to file
    with open("api_docs.html", "w") as f:
        f.write(documentation)

    print("Generated API documentation: api_docs.html")

    # Generate OpenAPI spec
    openapi_spec = await doc_generator.generate_openapi_spec(
        endpoints=[news_endpoint, stock_endpoint]
    )

    with open("openapi.yaml", "w") as f:
        yaml.dump(openapi_spec, f, default_flow_style=False)

    print("Generated OpenAPI specification: openapi.yaml")

    # Create developer portal
    portal_html = await portal.create_portal_dashboard("test_user")

    with open("developer_portal.html", "w") as f:
        f.write(portal_html)

    print("Created developer portal: developer_portal.html")

    # Set up web application
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", gateway.handle_request)

    print("API Gateway is ready!")
    print("Example requests:")
    print(
        f"curl -H 'X-API-Key: {test_api_key.key_value}' http://localhost:8080/v1/news"
    )
    print(
        f"curl -H 'X-API-Key: {test_api_key.key_value}' http://localhost:8080/v1/stock/price?symbol=AAPL"
    )

    # Start server (uncomment to run)
    # web.run_app(app, host='localhost', port=8080)


if __name__ == "__main__":
    asyncio.run(main())
