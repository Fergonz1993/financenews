"""
Automation Engine Module

This module provides comprehensive automation capabilities including real-time data streams,
webhook systems, brokerage integrations, and automated reporting.
"""

import asyncio
import json
import logging
import sqlite3
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import aiohttp
import numpy as np
import redis
import schedule
from jinja2 import Template

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IntegrationType(Enum):
    """Types of external integrations."""

    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    BROKERAGE = "brokerage"
    API = "api"


@dataclass
class WebhookEvent:
    """Webhook event data structure."""

    event_type: str
    timestamp: datetime
    data: dict[str, Any]
    source: str
    severity: AlertSeverity
    metadata: dict | None = None


@dataclass
class AlertRule:
    """Alert rule configuration."""

    rule_id: str
    name: str
    description: str
    condition: str  # Python expression
    severity: AlertSeverity
    enabled: bool
    integrations: list[str]
    cooldown_minutes: int
    metadata: dict[str, Any]


@dataclass
class ReportSchedule:
    """Automated report schedule configuration."""

    report_id: str
    name: str
    description: str
    template: str
    schedule_expression: str  # Cron-like expression
    recipients: list[str]
    format: str  # 'html', 'pdf', 'json'
    enabled: bool
    last_run: datetime | None = None


@dataclass
class IntegrationConfig:
    """External integration configuration."""

    integration_id: str
    integration_type: IntegrationType
    name: str
    endpoint_url: str | None
    api_key: str | None
    username: str | None
    password: str | None
    additional_config: dict[str, Any]
    enabled: bool


class RealTimeDataStreamer:
    """Real-time data streaming service."""

    def __init__(self):
        self.active_streams = {}
        self.subscribers = {}
        self.redis_client = None
        self._setup_redis()

    def _setup_redis(self):
        """Setup Redis for real-time data storage and pub/sub."""
        try:
            self.redis_client = redis.Redis(
                host="localhost", port=6379, decode_responses=True
            )
            self.redis_client.ping()  # Test connection
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            self.redis_client = None

    async def start_price_stream(
        self, symbols: list[str], callback: Callable | None = None
    ) -> str:
        """
        Start real-time price streaming for given symbols.

        Args:
            symbols: List of stock symbols to stream
            callback: Optional callback function for price updates

        Returns:
            Stream ID
        """
        stream_id = f"price_stream_{int(datetime.now().timestamp())}"

        try:
            # This would integrate with actual market data providers
            # For demo purposes, we'll simulate price updates
            self.active_streams[stream_id] = {
                "type": "price",
                "symbols": symbols,
                "callback": callback,
                "active": True,
                "started": datetime.now(),
            }

            # Start the streaming task
            asyncio.create_task(self._price_stream_worker(stream_id, symbols, callback))

            logger.info(f"Started price stream {stream_id} for symbols: {symbols}")
            return stream_id

        except Exception as e:
            logger.error(f"Error starting price stream: {e}")
            raise

    async def start_news_stream(
        self, keywords: list[str], callback: Callable | None = None
    ) -> str:
        """
        Start real-time news streaming for given keywords.

        Args:
            keywords: List of keywords to monitor
            callback: Optional callback function for news updates

        Returns:
            Stream ID
        """
        stream_id = f"news_stream_{int(datetime.now().timestamp())}"

        try:
            self.active_streams[stream_id] = {
                "type": "news",
                "keywords": keywords,
                "callback": callback,
                "active": True,
                "started": datetime.now(),
            }

            # Start the streaming task
            asyncio.create_task(self._news_stream_worker(stream_id, keywords, callback))

            logger.info(f"Started news stream {stream_id} for keywords: {keywords}")
            return stream_id

        except Exception as e:
            logger.error(f"Error starting news stream: {e}")
            raise

    async def _price_stream_worker(
        self, stream_id: str, symbols: list[str], callback: Callable | None
    ):
        """Worker function for price streaming."""
        while self.active_streams.get(stream_id, {}).get("active", False):
            try:
                for symbol in symbols:
                    # Simulate price data (replace with real market data API)
                    price_data = {
                        "symbol": symbol,
                        "price": round(100 + np.random.normal(0, 5), 2),
                        "volume": int(np.random.exponential(1000)),
                        "timestamp": datetime.now().isoformat(),
                        "change": round(np.random.normal(0, 2), 2),
                    }

                    # Store in Redis if available
                    if self.redis_client:
                        self.redis_client.setex(
                            f"price:{symbol}",
                            60,  # 1 minute expiry
                            json.dumps(price_data),
                        )

                        # Publish to subscribers
                        self.redis_client.publish(
                            f"price_updates:{symbol}", json.dumps(price_data)
                        )

                    # Call callback if provided
                    if callback:
                        await callback(price_data)

                await asyncio.sleep(1)  # Update every second

            except Exception as e:
                logger.error(f"Error in price stream worker: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _news_stream_worker(
        self, stream_id: str, keywords: list[str], callback: Callable | None
    ):
        """Worker function for news streaming."""
        while self.active_streams.get(stream_id, {}).get("active", False):
            try:
                # Simulate news data (replace with real news API)
                for keyword in keywords:
                    if np.random.random() < 0.1:  # 10% chance of news per cycle
                        news_data = {
                            "keyword": keyword,
                            "headline": f"Breaking news about {keyword}",
                            "sentiment": round(np.random.uniform(-1, 1), 2),
                            "source": "NewsAPI",
                            "timestamp": datetime.now().isoformat(),
                            "importance": round(np.random.uniform(0, 1), 2),
                        }

                        # Store in Redis if available
                        if self.redis_client:
                            self.redis_client.lpush(
                                f"news:{keyword}", json.dumps(news_data)
                            )
                            # Keep only latest 100 news items
                            self.redis_client.ltrim(f"news:{keyword}", 0, 99)

                            # Publish to subscribers
                            self.redis_client.publish(
                                f"news_updates:{keyword}", json.dumps(news_data)
                            )

                        # Call callback if provided
                        if callback:
                            await callback(news_data)

                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Error in news stream worker: {e}")
                await asyncio.sleep(30)  # Wait before retrying

    async def stop_stream(self, stream_id: str) -> bool:
        """Stop a specific data stream."""
        if stream_id in self.active_streams:
            self.active_streams[stream_id]["active"] = False
            del self.active_streams[stream_id]
            logger.info(f"Stopped stream {stream_id}")
            return True
        return False

    async def get_latest_data(self, data_type: str, identifier: str) -> dict | None:
        """Get latest data from Redis cache."""
        if not self.redis_client:
            return None

        try:
            key = f"{data_type}:{identifier}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error getting latest data: {e}")
            return None


class WebhookManager:
    """Webhook management and delivery system."""

    def __init__(self):
        self.webhooks = {}
        self.event_queue = asyncio.Queue()
        self.delivery_stats = {}

    async def register_webhook(
        self,
        webhook_id: str,
        url: str,
        event_types: list[str],
        secret: str | None = None,
        headers: dict | None = None,
    ) -> bool:
        """
        Register a new webhook endpoint.

        Args:
            webhook_id: Unique identifier for the webhook
            url: Webhook endpoint URL
            event_types: List of event types to send to this webhook
            secret: Optional secret for signature verification
            headers: Optional custom headers

        Returns:
            True if registered successfully
        """
        try:
            self.webhooks[webhook_id] = {
                "url": url,
                "event_types": event_types,
                "secret": secret,
                "headers": headers or {},
                "enabled": True,
                "created": datetime.now(),
                "last_delivery": None,
                "delivery_count": 0,
                "failure_count": 0,
            }

            self.delivery_stats[webhook_id] = {
                "total_deliveries": 0,
                "successful_deliveries": 0,
                "failed_deliveries": 0,
                "average_response_time": 0.0,
            }

            logger.info(f"Registered webhook {webhook_id} for events: {event_types}")
            return True

        except Exception as e:
            logger.error(f"Error registering webhook: {e}")
            return False

    async def send_webhook_event(self, event: WebhookEvent) -> None:
        """Queue a webhook event for delivery."""
        await self.event_queue.put(event)

    async def start_webhook_worker(self) -> None:
        """Start the webhook delivery worker."""
        logger.info("Starting webhook delivery worker")

        while True:
            try:
                # Get event from queue
                event = await self.event_queue.get()

                # Find matching webhooks
                matching_webhooks = [
                    (webhook_id, config)
                    for webhook_id, config in self.webhooks.items()
                    if config["enabled"] and event.event_type in config["event_types"]
                ]

                # Deliver to all matching webhooks
                delivery_tasks = [
                    self._deliver_webhook(webhook_id, config, event)
                    for webhook_id, config in matching_webhooks
                ]

                if delivery_tasks:
                    await asyncio.gather(*delivery_tasks, return_exceptions=True)

                self.event_queue.task_done()

            except Exception as e:
                logger.error(f"Error in webhook worker: {e}")
                await asyncio.sleep(1)

    async def _deliver_webhook(
        self, webhook_id: str, config: dict, event: WebhookEvent
    ) -> bool:
        """Deliver webhook event to a specific endpoint."""
        start_time = time.time()

        try:
            # Prepare payload
            payload = {
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
                "source": event.source,
                "severity": event.severity.value,
                "metadata": event.metadata or {},
            }

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "FinancialNews-Webhook/1.0",
                **config["headers"],
            }

            # Add signature if secret is provided
            if config["secret"]:
                import hashlib
                import hmac

                payload_str = json.dumps(payload, sort_keys=True)
                signature = hmac.new(
                    config["secret"].encode(), payload_str.encode(), hashlib.sha256
                ).hexdigest()
                headers["X-Signature-SHA256"] = f"sha256={signature}"

            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    config["url"],
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    success = response.status < 400

                    # Update statistics
                    response_time = time.time() - start_time
                    self._update_webhook_stats(webhook_id, success, response_time)

                    if success:
                        logger.debug(f"Webhook {webhook_id} delivered successfully")
                    else:
                        logger.warning(
                            f"Webhook {webhook_id} failed with status {response.status}"
                        )

                    return success

        except Exception as e:
            logger.error(f"Error delivering webhook {webhook_id}: {e}")
            self._update_webhook_stats(webhook_id, False, time.time() - start_time)
            return False

    def _update_webhook_stats(
        self, webhook_id: str, success: bool, response_time: float
    ):
        """Update webhook delivery statistics."""
        if webhook_id not in self.delivery_stats:
            return

        stats = self.delivery_stats[webhook_id]
        stats["total_deliveries"] += 1

        if success:
            stats["successful_deliveries"] += 1
            self.webhooks[webhook_id]["delivery_count"] += 1
        else:
            stats["failed_deliveries"] += 1
            self.webhooks[webhook_id]["failure_count"] += 1

        # Update average response time
        current_avg = stats["average_response_time"]
        total = stats["total_deliveries"]
        stats["average_response_time"] = (
            current_avg * (total - 1) + response_time
        ) / total

        self.webhooks[webhook_id]["last_delivery"] = datetime.now()


class AlertEngine:
    """Intelligent alert engine with rule-based monitoring."""

    def __init__(self):
        self.rules = {}
        self.alert_history = {}
        self.cooldown_tracker = {}
        self.db_path = "alerts.db"
        self._setup_database()

    def _setup_database(self):
        """Setup SQLite database for alert storage."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT,
                timestamp TEXT,
                severity TEXT,
                message TEXT,
                data TEXT,
                delivered BOOLEAN DEFAULT FALSE
            )
        """
        )
        conn.commit()
        conn.close()

    async def add_alert_rule(self, rule: AlertRule) -> bool:
        """Add a new alert rule."""
        try:
            self.rules[rule.rule_id] = rule
            logger.info(f"Added alert rule: {rule.name}")
            return True
        except Exception as e:
            logger.error(f"Error adding alert rule: {e}")
            return False

    async def evaluate_rules(self, context: dict[str, Any]) -> list[WebhookEvent]:
        """Evaluate all alert rules against current context."""
        triggered_events = []

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            # Check cooldown
            if self._is_in_cooldown(rule_id):
                continue

            try:
                # Evaluate rule condition
                if self._evaluate_condition(rule.condition, context):
                    # Create alert event
                    event = WebhookEvent(
                        event_type="alert_triggered",
                        timestamp=datetime.now(),
                        data={
                            "rule_id": rule_id,
                            "rule_name": rule.name,
                            "description": rule.description,
                            "severity": rule.severity.value,
                            "context": context,
                        },
                        source="alert_engine",
                        severity=rule.severity,
                        metadata=rule.metadata,
                    )

                    triggered_events.append(event)

                    # Store alert in database
                    self._store_alert(rule_id, event)

                    # Update cooldown
                    self.cooldown_tracker[rule_id] = datetime.now()

                    logger.info(f"Alert triggered: {rule.name}")

            except Exception as e:
                logger.error(f"Error evaluating rule {rule_id}: {e}")

        return triggered_events

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """Safely evaluate a rule condition."""
        try:
            # Create a safe evaluation environment
            safe_globals = {
                "__builtins__": {},
                "abs": abs,
                "min": min,
                "max": max,
                "round": round,
                "len": len,
                "sum": sum,
                "any": any,
                "all": all,
            }

            # Add context variables
            safe_globals.update(context)

            # Evaluate condition
            return bool(eval(condition, safe_globals))

        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False

    def _is_in_cooldown(self, rule_id: str) -> bool:
        """Check if a rule is in cooldown period."""
        if rule_id not in self.cooldown_tracker:
            return False

        rule = self.rules.get(rule_id)
        if not rule:
            return False

        last_trigger = self.cooldown_tracker[rule_id]
        cooldown_end = last_trigger + timedelta(minutes=rule.cooldown_minutes)

        return datetime.now() < cooldown_end

    def _store_alert(self, rule_id: str, event: WebhookEvent):
        """Store alert in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO alerts (rule_id, timestamp, severity, message, data) VALUES (?, ?, ?, ?, ?)",
                (
                    rule_id,
                    event.timestamp.isoformat(),
                    event.severity.value,
                    event.data.get("description", ""),
                    json.dumps(event.data),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing alert: {e}")


class ReportGenerator:
    """Automated report generation and scheduling."""

    def __init__(self):
        self.schedules = {}
        self.templates = {}
        self.executor = ThreadPoolExecutor(max_workers=3)

    async def add_report_schedule(self, schedule_config: ReportSchedule) -> bool:
        """Add a new report schedule."""
        try:
            self.schedules[schedule_config.report_id] = schedule_config

            # Schedule the report using the schedule library
            if schedule_config.enabled:
                self._schedule_report(schedule_config)

            logger.info(f"Added report schedule: {schedule_config.name}")
            return True

        except Exception as e:
            logger.error(f"Error adding report schedule: {e}")
            return False

    def _schedule_report(self, schedule_config: ReportSchedule):
        """Schedule a report using cron-like expressions."""
        # This is a simplified implementation
        # In production, you'd use a more robust cron parser
        schedule_expr = schedule_config.schedule_expression

        if schedule_expr == "daily":
            schedule.every().day.at("09:00").do(
                self._run_scheduled_report, schedule_config.report_id
            )
        elif schedule_expr == "weekly":
            schedule.every().monday.at("09:00").do(
                self._run_scheduled_report, schedule_config.report_id
            )
        elif schedule_expr == "monthly":
            schedule.every().day.at("09:00").do(
                self._check_monthly_report, schedule_config.report_id
            )

    def _run_scheduled_report(self, report_id: str):
        """Run a scheduled report."""
        try:
            schedule_config = self.schedules.get(report_id)
            if not schedule_config or not schedule_config.enabled:
                return

            # Generate report in thread pool to avoid blocking
            self.executor.submit(self._generate_report_sync, schedule_config)
            logger.info(f"Started generating report: {schedule_config.name}")

        except Exception as e:
            logger.error(f"Error running scheduled report {report_id}: {e}")

    def _check_monthly_report(self, report_id: str):
        """Check if monthly report should run (first day of month)."""
        if datetime.now().day == 1:
            self._run_scheduled_report(report_id)

    def _generate_report_sync(self, schedule_config: ReportSchedule):
        """Generate report synchronously (runs in thread)."""
        try:
            # This would generate the actual report
            # For now, we'll create a simple HTML report
            report_data = self._collect_report_data(schedule_config)

            if schedule_config.format == "html":
                report_content = self._generate_html_report(
                    schedule_config, report_data
                )
            elif schedule_config.format == "json":
                report_content = json.dumps(report_data, indent=2)
            else:
                report_content = str(report_data)

            # Send report to recipients
            self._deliver_report(schedule_config, report_content)

            # Update last run time
            schedule_config.last_run = datetime.now()

            logger.info(f"Generated and delivered report: {schedule_config.name}")

        except Exception as e:
            logger.error(f"Error generating report {schedule_config.report_id}: {e}")

    def _collect_report_data(self, schedule_config: ReportSchedule) -> dict:
        """Collect data for report generation."""
        # This would collect actual data from your system
        # For demo purposes, we'll return sample data
        return {
            "report_name": schedule_config.name,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_alerts": 25,
                "critical_alerts": 3,
                "top_performing_stocks": ["AAPL", "MSFT", "GOOGL"],
                "market_sentiment": 0.15,
            },
            "details": {
                "sentiment_analysis": {
                    "positive_news": 145,
                    "negative_news": 89,
                    "neutral_news": 256,
                },
                "trading_signals": {
                    "buy_signals": 12,
                    "sell_signals": 8,
                    "hold_signals": 35,
                },
            },
        }

    def _generate_html_report(self, schedule_config: ReportSchedule, data: dict) -> str:
        """Generate HTML report from template."""
        template_str = """
        <html>
        <head>
            <title>{{ report_name }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .summary { background: #f5f5f5; padding: 15px; border-radius: 5px; }
                .metric { display: inline-block; margin: 10px; padding: 10px; background: white; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>{{ report_name }}</h1>
            <p>Generated at: {{ generated_at }}</p>

            <div class="summary">
                <h2>Summary</h2>
                <div class="metric">
                    <strong>Total Alerts:</strong> {{ summary.total_alerts }}
                </div>
                <div class="metric">
                    <strong>Critical Alerts:</strong> {{ summary.critical_alerts }}
                </div>
                <div class="metric">
                    <strong>Market Sentiment:</strong> {{ summary.market_sentiment }}
                </div>
            </div>

            <h2>Top Performing Stocks</h2>
            <ul>
            {% for stock in summary.top_performing_stocks %}
                <li>{{ stock }}</li>
            {% endfor %}
            </ul>

            <h2>Sentiment Analysis</h2>
            <p>Positive News: {{ details.sentiment_analysis.positive_news }}</p>
            <p>Negative News: {{ details.sentiment_analysis.negative_news }}</p>
            <p>Neutral News: {{ details.sentiment_analysis.neutral_news }}</p>

            <h2>Trading Signals</h2>
            <p>Buy Signals: {{ details.trading_signals.buy_signals }}</p>
            <p>Sell Signals: {{ details.trading_signals.sell_signals }}</p>
            <p>Hold Signals: {{ details.trading_signals.hold_signals }}</p>
        </body>
        </html>
        """

        template = Template(template_str)
        return template.render(**data)

    def _deliver_report(self, schedule_config: ReportSchedule, content: str):
        """Deliver report to recipients."""
        # This would integrate with email service, Slack, etc.
        # For demo purposes, we'll just save to file
        filename = f"report_{schedule_config.report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{schedule_config.format}"

        with open(filename, "w") as f:
            f.write(content)

        logger.info(f"Report saved to {filename}")


class BrokerageIntegration:
    """Integration with brokerage APIs for automated trading."""

    def __init__(self):
        self.connections = {}
        self.paper_trading = True  # Safety first!

    async def add_brokerage_connection(
        self,
        connection_id: str,
        broker_type: str,
        api_key: str,
        secret_key: str,
        paper_trading: bool = True,
    ) -> bool:
        """Add a new brokerage connection."""
        try:
            self.connections[connection_id] = {
                "broker_type": broker_type,
                "api_key": api_key,
                "secret_key": secret_key,
                "paper_trading": paper_trading,
                "connected": False,
                "last_activity": None,
            }

            # Test connection
            connected = await self._test_connection(connection_id)
            self.connections[connection_id]["connected"] = connected

            logger.info(
                f"Added brokerage connection {connection_id} ({'paper' if paper_trading else 'live'} trading)"
            )
            return connected

        except Exception as e:
            logger.error(f"Error adding brokerage connection: {e}")
            return False

    async def _test_connection(self, connection_id: str) -> bool:
        """Test brokerage connection."""
        # This would test actual brokerage API connection
        # For demo purposes, we'll simulate it
        return True

    async def place_order(
        self,
        connection_id: str,
        symbol: str,
        quantity: int,
        order_type: str,
        price: float | None = None,
    ) -> dict:
        """Place an order through brokerage API."""
        if connection_id not in self.connections:
            raise ValueError(f"Connection {connection_id} not found")

        connection = self.connections[connection_id]
        if not connection["connected"]:
            raise ValueError(f"Connection {connection_id} not active")

        try:
            # Simulate order placement
            order_id = f"ORDER_{int(datetime.now().timestamp())}"

            order_result = {
                "order_id": order_id,
                "symbol": symbol,
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
                "status": "submitted",
                "timestamp": datetime.now().isoformat(),
                "paper_trading": connection["paper_trading"],
            }

            connection["last_activity"] = datetime.now()

            logger.info(
                f"Placed {'paper' if connection['paper_trading'] else 'live'} order: {order_result}"
            )
            return order_result

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    async def get_portfolio(self, connection_id: str) -> dict:
        """Get current portfolio from brokerage."""
        if connection_id not in self.connections:
            raise ValueError(f"Connection {connection_id} not found")

        # Simulate portfolio data
        return {
            "cash": 10000.0,
            "positions": [
                {"symbol": "AAPL", "quantity": 10, "avg_price": 150.0},
                {"symbol": "MSFT", "quantity": 5, "avg_price": 300.0},
            ],
            "total_value": 25000.0,
            "day_change": 250.0,
            "day_change_percent": 1.0,
        }


class AutomationEngine:
    """Main automation engine orchestrating all services."""

    def __init__(self):
        self.data_streamer = RealTimeDataStreamer()
        self.webhook_manager = WebhookManager()
        self.alert_engine = AlertEngine()
        self.report_generator = ReportGenerator()
        self.brokerage_integration = BrokerageIntegration()
        self.running = False

    async def start(self) -> None:
        """Start the automation engine."""
        if self.running:
            return

        self.running = True
        logger.info("Starting automation engine...")

        # Start core services
        await asyncio.gather(
            self.webhook_manager.start_webhook_worker(),
            self._alert_monitoring_loop(),
            self._schedule_runner(),
            return_exceptions=True,
        )

    async def stop(self) -> None:
        """Stop the automation engine."""
        self.running = False
        logger.info("Stopping automation engine...")

        # Stop all active streams
        for stream_id in list(self.data_streamer.active_streams.keys()):
            await self.data_streamer.stop_stream(stream_id)

    async def _alert_monitoring_loop(self) -> None:
        """Continuous alert monitoring loop."""
        while self.running:
            try:
                # Collect current system context
                context = await self._collect_system_context()

                # Evaluate alert rules
                triggered_events = await self.alert_engine.evaluate_rules(context)

                # Send webhook events for triggered alerts
                for event in triggered_events:
                    await self.webhook_manager.send_webhook_event(event)

                # Wait before next evaluation
                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _collect_system_context(self) -> dict[str, Any]:
        """Collect current system context for alert evaluation."""
        # This would collect real system metrics
        # For demo purposes, we'll return sample data
        return {
            "current_time": datetime.now(),
            "market_open": 9 <= datetime.now().hour <= 16,
            "total_alerts_today": 25,
            "critical_alerts_today": 3,
            "avg_sentiment": 0.15,
            "news_volume": 150,
            "active_streams": len(self.data_streamer.active_streams),
            "system_load": 0.75,
        }

    async def _schedule_runner(self) -> None:
        """Run scheduled reports."""
        while self.running:
            try:
                schedule.run_pending()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in schedule runner: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error


# Example usage and testing
async def main():
    """Example usage of the automation engine."""
    engine = AutomationEngine()

    # Add a webhook
    await engine.webhook_manager.register_webhook(
        webhook_id="test_webhook",
        url="https://httpbin.org/post",
        event_types=["alert_triggered", "price_update"],
    )

    # Add an alert rule
    rule = AlertRule(
        rule_id="high_volatility",
        name="High Volatility Alert",
        description="Alert when market volatility exceeds threshold",
        condition="avg_sentiment > 0.5 or avg_sentiment < -0.5",
        severity=AlertSeverity.HIGH,
        enabled=True,
        integrations=["test_webhook"],
        cooldown_minutes=60,
        metadata={"threshold": 0.5},
    )

    await engine.alert_engine.add_alert_rule(rule)

    # Add a report schedule
    report_schedule = ReportSchedule(
        report_id="daily_summary",
        name="Daily Market Summary",
        description="Daily summary of market activity and alerts",
        template="daily_template",
        schedule_expression="daily",
        recipients=["admin@example.com"],
        format="html",
        enabled=True,
    )

    await engine.report_generator.add_report_schedule(report_schedule)

    # Start price streaming
    stream_id = await engine.data_streamer.start_price_stream(
        symbols=["AAPL", "MSFT", "GOOGL"],
        callback=lambda data: print(f"Price update: {data}"),
    )

    print(f"Started automation engine with stream {stream_id}")
    print("Press Ctrl+C to stop...")

    try:
        # Start the engine (this would run indefinitely)
        await engine.start()
    except KeyboardInterrupt:
        print("Stopping automation engine...")
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
