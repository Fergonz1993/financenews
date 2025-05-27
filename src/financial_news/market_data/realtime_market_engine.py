"""
Real-Time Market Data & Analytics Engine

This module provides comprehensive real-time market data streaming, analytics,
order book management, and market microstructure analysis capabilities for
financial platforms. It integrates with multiple data sources and provides
advanced real-time analytical tools.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
import warnings
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import aiohttp
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import IsolationForest

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """Market data source types."""

    YAHOO_FINANCE = "yahoo_finance"
    ALPHA_VANTAGE = "alpha_vantage"
    IEX_CLOUD = "iex_cloud"
    POLYGON = "polygon"
    FINNHUB = "finnhub"
    WEBSOCKET = "websocket"
    SIMULATED = "simulated"


class MessageType(Enum):
    """Market data message types."""

    TRADE = "trade"
    QUOTE = "quote"
    ORDER_BOOK = "order_book"
    LEVEL1 = "level1"
    LEVEL2 = "level2"
    OHLCV = "ohlcv"
    NEWS = "news"
    CORPORATE_ACTION = "corporate_action"
    MARKET_STATUS = "market_status"
    ERROR = "error"


class OrderSide(Enum):
    """Order side types."""

    BID = "bid"
    ASK = "ask"


class MarketStatus(Enum):
    """Market status types."""

    PRE_MARKET = "pre_market"
    OPEN = "open"
    CLOSED = "closed"
    AFTER_HOURS = "after_hours"
    HOLIDAY = "holiday"


class AlertType(Enum):
    """Alert types for market events."""

    PRICE_MOVEMENT = "price_movement"
    VOLUME_SPIKE = "volume_spike"
    VOLATILITY_SPIKE = "volatility_spike"
    UNUSUAL_ACTIVITY = "unusual_activity"
    TECHNICAL_INDICATOR = "technical_indicator"
    NEWS_SENTIMENT = "news_sentiment"
    MARKET_ANOMALY = "market_anomaly"


@dataclass
class MarketTick:
    """Individual market data tick."""

    symbol: str
    timestamp: datetime
    message_type: MessageType
    price: float | None = None
    size: int | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    bid_size: int | None = None
    ask_size: int | None = None
    volume: int | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    vwap: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderBookLevel:
    """Order book price level."""

    price: float
    size: int
    orders: int = 1
    side: OrderSide = OrderSide.BID


@dataclass
class OrderBook:
    """Complete order book state."""

    symbol: str
    timestamp: datetime
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    sequence: int = 0

    def get_spread(self) -> float | None:
        """Get bid-ask spread."""
        if self.bids and self.asks:
            return self.asks[0].price - self.bids[0].price
        return None

    def get_mid_price(self) -> float | None:
        """Get mid price."""
        if self.bids and self.asks:
            return (self.bids[0].price + self.asks[0].price) / 2
        return None

    def get_depth(self, levels: int = 5) -> dict[str, Any]:
        """Get order book depth."""
        return {
            "bids": [(level.price, level.size) for level in self.bids[:levels]],
            "asks": [(level.price, level.size) for level in self.asks[:levels]],
            "spread": self.get_spread(),
            "mid_price": self.get_mid_price(),
        }


@dataclass
class MarketAlert:
    """Market alert/notification."""

    alert_id: str
    symbol: str
    alert_type: AlertType
    message: str
    severity: str  # low, medium, high, critical
    timestamp: datetime
    data: dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


@dataclass
class MarketStatistics:
    """Real-time market statistics."""

    symbol: str
    timestamp: datetime
    price: float
    change: float
    change_percent: float
    volume: int
    avg_volume: float
    volatility: float
    beta: float | None = None
    rsi: float | None = None
    macd: float | None = None
    bollinger_position: float | None = None
    support_level: float | None = None
    resistance_level: float | None = None


class DataFeedHandler:
    """Base class for market data feed handlers."""

    def __init__(self, source: DataSource):
        self.source = source
        self.is_connected = False
        self.subscribers = set()
        self.error_count = 0
        self.last_heartbeat = datetime.now()

    async def connect(self) -> bool:
        """Connect to data source."""
        raise NotImplementedError

    async def disconnect(self):
        """Disconnect from data source."""
        raise NotImplementedError

    async def subscribe(self, symbols: list[str], message_types: list[MessageType]):
        """Subscribe to market data."""
        raise NotImplementedError

    async def unsubscribe(self, symbols: list[str]):
        """Unsubscribe from market data."""
        raise NotImplementedError

    def add_subscriber(self, callback: Callable[[MarketTick], None]):
        """Add data subscriber."""
        self.subscribers.add(callback)

    def remove_subscriber(self, callback: Callable[[MarketTick], None]):
        """Remove data subscriber."""
        self.subscribers.discard(callback)

    async def _notify_subscribers(self, tick: MarketTick):
        """Notify all subscribers of new data."""
        for callback in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(tick)
                else:
                    callback(tick)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")


class YahooFinanceHandler(DataFeedHandler):
    """Yahoo Finance data feed handler."""

    def __init__(self):
        super().__init__(DataSource.YAHOO_FINANCE)
        self.session = None
        self.polling_interval = 1.0  # seconds
        self.active_symbols = set()
        self.polling_task = None

    async def connect(self) -> bool:
        """Connect to Yahoo Finance."""
        try:
            self.session = aiohttp.ClientSession()
            self.is_connected = True
            logger.info("Connected to Yahoo Finance")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Yahoo Finance: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Yahoo Finance."""
        if self.polling_task:
            self.polling_task.cancel()

        if self.session:
            await self.session.close()

        self.is_connected = False
        logger.info("Disconnected from Yahoo Finance")

    async def subscribe(self, symbols: list[str], message_types: list[MessageType]):
        """Subscribe to Yahoo Finance data."""
        self.active_symbols.update(symbols)

        if not self.polling_task:
            self.polling_task = asyncio.create_task(self._polling_loop())

        logger.info(f"Subscribed to {len(symbols)} symbols on Yahoo Finance")

    async def unsubscribe(self, symbols: list[str]):
        """Unsubscribe from symbols."""
        self.active_symbols.difference_update(symbols)

        if not self.active_symbols and self.polling_task:
            self.polling_task.cancel()
            self.polling_task = None

    async def _polling_loop(self):
        """Main polling loop for Yahoo Finance data."""
        while self.is_connected and self.active_symbols:
            try:
                await self._fetch_data()
                await asyncio.sleep(self.polling_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Yahoo Finance polling loop: {e}")
                self.error_count += 1
                await asyncio.sleep(5)  # Back off on error

    async def _fetch_data(self):
        """Fetch data for all active symbols."""
        if not self.active_symbols:
            return

        symbols_str = " ".join(self.active_symbols)

        try:
            # Use yfinance to get current data
            tickers = yf.Tickers(symbols_str)

            for symbol in self.active_symbols:
                try:
                    ticker = tickers.tickers[symbol]
                    info = ticker.info
                    hist = ticker.history(period="1d", interval="1m")

                    if not hist.empty:
                        latest = hist.iloc[-1]

                        tick = MarketTick(
                            symbol=symbol,
                            timestamp=datetime.now(),
                            message_type=MessageType.OHLCV,
                            price=float(latest["Close"]),
                            volume=int(latest["Volume"]),
                            open_price=float(latest["Open"]),
                            high_price=float(latest["High"]),
                            low_price=float(latest["Low"]),
                            close_price=float(latest["Close"]),
                            metadata={
                                "source": "yahoo_finance",
                                "market_cap": info.get("marketCap"),
                                "pe_ratio": info.get("trailingPE"),
                                "dividend_yield": info.get("dividendYield"),
                            },
                        )

                        await self._notify_subscribers(tick)

                except Exception as e:
                    logger.warning(f"Error fetching data for {symbol}: {e}")

        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance data: {e}")


class SimulatedDataHandler(DataFeedHandler):
    """Simulated market data handler for testing."""

    def __init__(self):
        super().__init__(DataSource.SIMULATED)
        self.active_symbols = {}  # symbol -> current_price
        self.simulation_task = None
        self.tick_interval = 0.1  # seconds

    async def connect(self) -> bool:
        """Connect to simulated data source."""
        self.is_connected = True
        logger.info("Connected to simulated data source")
        return True

    async def disconnect(self):
        """Disconnect from simulated data source."""
        if self.simulation_task:
            self.simulation_task.cancel()

        self.is_connected = False
        logger.info("Disconnected from simulated data source")

    async def subscribe(self, symbols: list[str], message_types: list[MessageType]):
        """Subscribe to simulated data."""
        for symbol in symbols:
            if symbol not in self.active_symbols:
                # Initialize with random starting price
                self.active_symbols[symbol] = np.random.uniform(50, 500)

        if not self.simulation_task:
            self.simulation_task = asyncio.create_task(self._simulation_loop())

        logger.info(f"Subscribed to {len(symbols)} simulated symbols")

    async def unsubscribe(self, symbols: list[str]):
        """Unsubscribe from symbols."""
        for symbol in symbols:
            self.active_symbols.pop(symbol, None)

        if not self.active_symbols and self.simulation_task:
            self.simulation_task.cancel()
            self.simulation_task = None

    async def _simulation_loop(self):
        """Main simulation loop."""
        while self.is_connected and self.active_symbols:
            try:
                await self._generate_ticks()
                await asyncio.sleep(self.tick_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")

    async def _generate_ticks(self):
        """Generate simulated market ticks."""
        for symbol, current_price in self.active_symbols.items():
            # Generate realistic price movement
            change_percent = np.random.normal(0, 0.001)  # 0.1% std dev
            new_price = current_price * (1 + change_percent)

            # Update stored price
            self.active_symbols[symbol] = new_price

            # Generate bid/ask spread
            spread_percent = np.random.uniform(0.0001, 0.001)  # 0.01% to 0.1%
            spread = new_price * spread_percent

            bid_price = new_price - spread / 2
            ask_price = new_price + spread / 2

            # Generate volume
            volume = int(np.random.exponential(1000))

            # Create trade tick
            trade_tick = MarketTick(
                symbol=symbol,
                timestamp=datetime.now(),
                message_type=MessageType.TRADE,
                price=new_price,
                size=volume,
                volume=volume,
                metadata={"source": "simulated"},
            )

            # Create quote tick
            quote_tick = MarketTick(
                symbol=symbol,
                timestamp=datetime.now(),
                message_type=MessageType.QUOTE,
                bid_price=bid_price,
                ask_price=ask_price,
                bid_size=int(np.random.exponential(500)),
                ask_size=int(np.random.exponential(500)),
                metadata={"source": "simulated"},
            )

            await self._notify_subscribers(trade_tick)
            await self._notify_subscribers(quote_tick)


class OrderBookManager:
    """Real-time order book management."""

    def __init__(self, max_levels: int = 10):
        self.max_levels = max_levels
        self.order_books = {}  # symbol -> OrderBook
        self.subscribers = set()
        self.last_update = {}  # symbol -> timestamp

    def add_subscriber(self, callback: Callable[[str, OrderBook], None]):
        """Add order book subscriber."""
        self.subscribers.add(callback)

    def remove_subscriber(self, callback: Callable[[str, OrderBook], None]):
        """Remove order book subscriber."""
        self.subscribers.discard(callback)

    async def update_order_book(self, symbol: str, tick: MarketTick):
        """Update order book with new market data."""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(
                symbol=symbol, timestamp=tick.timestamp
            )

        book = self.order_books[symbol]
        book.timestamp = tick.timestamp

        if tick.message_type == MessageType.QUOTE:
            # Update top of book
            if tick.bid_price and tick.bid_size:
                book.bids = [
                    OrderBookLevel(
                        price=tick.bid_price, size=tick.bid_size, side=OrderSide.BID
                    )
                ]

            if tick.ask_price and tick.ask_size:
                book.asks = [
                    OrderBookLevel(
                        price=tick.ask_price, size=tick.ask_size, side=OrderSide.ASK
                    )
                ]

        elif tick.message_type == MessageType.LEVEL2:
            # Full order book update (would need more detailed data structure)
            pass

        self.last_update[symbol] = tick.timestamp

        # Notify subscribers
        await self._notify_subscribers(symbol, book)

    async def _notify_subscribers(self, symbol: str, book: OrderBook):
        """Notify subscribers of order book update."""
        for callback in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(symbol, book)
                else:
                    callback(symbol, book)
            except Exception as e:
                logger.error(f"Error notifying order book subscriber: {e}")

    def get_order_book(self, symbol: str) -> OrderBook | None:
        """Get current order book for symbol."""
        return self.order_books.get(symbol)

    def get_market_depth(self, symbol: str, levels: int = 5) -> dict[str, Any] | None:
        """Get market depth for symbol."""
        book = self.get_order_book(symbol)
        if book:
            return book.get_depth(levels)
        return None


class TechnicalIndicatorCalculator:
    """Real-time technical indicator calculations."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.price_history = defaultdict(lambda: deque(maxlen=window_size))
        self.volume_history = defaultdict(lambda: deque(maxlen=window_size))

    def update(self, symbol: str, tick: MarketTick):
        """Update price and volume history."""
        if tick.price:
            self.price_history[symbol].append(tick.price)

        if tick.volume:
            self.volume_history[symbol].append(tick.volume)

    def calculate_sma(self, symbol: str, period: int = 20) -> float | None:
        """Calculate Simple Moving Average."""
        prices = list(self.price_history[symbol])
        if len(prices) >= period:
            return np.mean(prices[-period:])
        return None

    def calculate_ema(self, symbol: str, period: int = 20) -> float | None:
        """Calculate Exponential Moving Average."""
        prices = list(self.price_history[symbol])
        if len(prices) >= period:
            return pd.Series(prices).ewm(span=period).mean().iloc[-1]
        return None

    def calculate_rsi(self, symbol: str, period: int = 14) -> float | None:
        """Calculate Relative Strength Index."""
        prices = list(self.price_history[symbol])
        if len(prices) >= period + 1:
            price_series = pd.Series(prices)
            delta = price_series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        return None

    def calculate_macd(
        self, symbol: str, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> dict[str, float] | None:
        """Calculate MACD."""
        prices = list(self.price_history[symbol])
        if len(prices) >= slow:
            price_series = pd.Series(prices)
            ema_fast = price_series.ewm(span=fast).mean()
            ema_slow = price_series.ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal).mean()
            histogram = macd_line - signal_line

            return {
                "macd": macd_line.iloc[-1],
                "signal": signal_line.iloc[-1],
                "histogram": histogram.iloc[-1],
            }
        return None

    def calculate_bollinger_bands(
        self, symbol: str, period: int = 20, std_dev: float = 2
    ) -> dict[str, float] | None:
        """Calculate Bollinger Bands."""
        prices = list(self.price_history[symbol])
        if len(prices) >= period:
            price_series = pd.Series(prices)
            sma = price_series.rolling(window=period).mean()
            std = price_series.rolling(window=period).std()

            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)

            current_price = prices[-1]
            bb_position = (current_price - lower_band.iloc[-1]) / (
                upper_band.iloc[-1] - lower_band.iloc[-1]
            )

            return {
                "upper_band": upper_band.iloc[-1],
                "middle_band": sma.iloc[-1],
                "lower_band": lower_band.iloc[-1],
                "bb_position": bb_position,
            }
        return None

    def calculate_volatility(self, symbol: str, period: int = 20) -> float | None:
        """Calculate historical volatility."""
        prices = list(self.price_history[symbol])
        if len(prices) >= period + 1:
            price_series = pd.Series(prices)
            returns = price_series.pct_change().dropna()
            volatility = returns.rolling(window=period).std().iloc[-1] * np.sqrt(
                252
            )  # Annualized
            return volatility
        return None


class MarketAnomalyDetector:
    """Real-time market anomaly detection."""

    def __init__(self):
        self.price_models = {}  # symbol -> IsolationForest
        self.volume_models = {}  # symbol -> IsolationForest
        self.training_data = defaultdict(list)
        self.min_training_samples = 100
        self.anomaly_threshold = -0.5

    def update_training_data(self, symbol: str, tick: MarketTick):
        """Update training data for anomaly detection."""
        if tick.price and tick.volume:
            features = [
                tick.price,
                tick.volume,
                tick.timestamp.hour,
                tick.timestamp.minute,
            ]

            self.training_data[symbol].append(features)

            # Retrain model periodically
            if len(self.training_data[symbol]) >= self.min_training_samples:
                if (
                    len(self.training_data[symbol]) % 50 == 0
                ):  # Retrain every 50 samples
                    self._train_models(symbol)

    def _train_models(self, symbol: str):
        """Train anomaly detection models."""
        try:
            data = np.array(self.training_data[symbol])

            # Train isolation forest for price/volume anomalies
            model = IsolationForest(
                contamination=0.1, random_state=42, n_estimators=100
            )

            model.fit(data)
            self.price_models[symbol] = model

            logger.info(f"Trained anomaly detection model for {symbol}")

        except Exception as e:
            logger.error(f"Error training anomaly model for {symbol}: {e}")

    def detect_anomaly(self, symbol: str, tick: MarketTick) -> dict[str, Any] | None:
        """Detect if current tick is anomalous."""
        if symbol not in self.price_models or not tick.price or not tick.volume:
            return None

        try:
            features = np.array(
                [[tick.price, tick.volume, tick.timestamp.hour, tick.timestamp.minute]]
            )

            model = self.price_models[symbol]
            anomaly_score = model.decision_function(features)[0]
            is_anomaly = anomaly_score < self.anomaly_threshold

            if is_anomaly:
                return {
                    "symbol": symbol,
                    "timestamp": tick.timestamp,
                    "anomaly_score": anomaly_score,
                    "price": tick.price,
                    "volume": tick.volume,
                    "severity": "high" if anomaly_score < -0.7 else "medium",
                }

        except Exception as e:
            logger.error(f"Error detecting anomaly for {symbol}: {e}")

        return None


class AlertManager:
    """Real-time alert management system."""

    def __init__(self):
        self.alerts = {}  # alert_id -> MarketAlert
        self.alert_rules = {}  # rule_id -> alert_rule
        self.subscribers = set()
        self.alert_history = deque(maxlen=1000)

    def add_subscriber(self, callback: Callable[[MarketAlert], None]):
        """Add alert subscriber."""
        self.subscribers.add(callback)

    def remove_subscriber(self, callback: Callable[[MarketAlert], None]):
        """Remove alert subscriber."""
        self.subscribers.discard(callback)

    def add_alert_rule(self, rule_id: str, rule: dict[str, Any]):
        """Add alert rule."""
        self.alert_rules[rule_id] = rule
        logger.info(f"Added alert rule: {rule_id}")

    def remove_alert_rule(self, rule_id: str):
        """Remove alert rule."""
        self.alert_rules.pop(rule_id, None)
        logger.info(f"Removed alert rule: {rule_id}")

    async def check_alerts(
        self, symbol: str, tick: MarketTick, statistics: MarketStatistics
    ):
        """Check if any alert conditions are met."""
        for rule_id, rule in self.alert_rules.items():
            try:
                if self._evaluate_rule(rule, symbol, tick, statistics):
                    alert = await self._create_alert(rule, symbol, tick, statistics)
                    await self._trigger_alert(alert)
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule_id}: {e}")

    def _evaluate_rule(
        self,
        rule: dict[str, Any],
        symbol: str,
        tick: MarketTick,
        stats: MarketStatistics,
    ) -> bool:
        """Evaluate if alert rule conditions are met."""
        # Check symbol filter
        if "symbols" in rule and symbol not in rule["symbols"]:
            return False

        # Check price movement
        if "price_change_percent" in rule:
            threshold = rule["price_change_percent"]
            if abs(stats.change_percent) >= threshold:
                return True

        # Check volume spike
        if "volume_spike_ratio" in rule:
            threshold = rule["volume_spike_ratio"]
            if stats.volume > stats.avg_volume * threshold:
                return True

        # Check volatility spike
        if "volatility_threshold" in rule:
            threshold = rule["volatility_threshold"]
            if stats.volatility >= threshold:
                return True

        # Check RSI levels
        if "rsi_overbought" in rule and stats.rsi:
            if stats.rsi >= rule["rsi_overbought"]:
                return True

        if "rsi_oversold" in rule and stats.rsi:
            if stats.rsi <= rule["rsi_oversold"]:
                return True

        return False

    async def _create_alert(
        self,
        rule: dict[str, Any],
        symbol: str,
        tick: MarketTick,
        stats: MarketStatistics,
    ) -> MarketAlert:
        """Create alert from rule and market data."""
        alert_type = AlertType(rule.get("type", "price_movement"))
        severity = rule.get("severity", "medium")

        # Generate alert message
        if alert_type == AlertType.PRICE_MOVEMENT:
            message = f"{symbol} price moved {stats.change_percent:.2f}% to ${stats.price:.2f}"
        elif alert_type == AlertType.VOLUME_SPIKE:
            volume_ratio = stats.volume / stats.avg_volume
            message = f"{symbol} volume spike: {volume_ratio:.1f}x average volume"
        elif alert_type == AlertType.VOLATILITY_SPIKE:
            message = f"{symbol} volatility spike: {stats.volatility:.2f}%"
        else:
            message = f"{symbol} alert triggered"

        alert = MarketAlert(
            alert_id=str(uuid.uuid4()),
            symbol=symbol,
            alert_type=alert_type,
            message=message,
            severity=severity,
            timestamp=tick.timestamp,
            data={
                "price": stats.price,
                "change_percent": stats.change_percent,
                "volume": stats.volume,
                "volatility": stats.volatility,
                "rule_id": rule.get("id"),
            },
        )

        return alert

    async def _trigger_alert(self, alert: MarketAlert):
        """Trigger alert and notify subscribers."""
        self.alerts[alert.alert_id] = alert
        self.alert_history.append(alert)

        # Notify subscribers
        for callback in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Error notifying alert subscriber: {e}")

        logger.info(f"Alert triggered: {alert.message}")

    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert."""
        if alert_id in self.alerts:
            self.alerts[alert_id].acknowledged = True
            logger.info(f"Alert acknowledged: {alert_id}")

    def get_active_alerts(self, symbol: str | None = None) -> list[MarketAlert]:
        """Get active (unacknowledged) alerts."""
        alerts = [alert for alert in self.alerts.values() if not alert.acknowledged]

        if symbol:
            alerts = [alert for alert in alerts if alert.symbol == symbol]

        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)


class RealTimeMarketEngine:
    """Main real-time market data and analytics engine."""

    def __init__(self):
        self.data_handlers = {}  # source -> DataFeedHandler
        self.order_book_manager = OrderBookManager()
        self.technical_calculator = TechnicalIndicatorCalculator()
        self.anomaly_detector = MarketAnomalyDetector()
        self.alert_manager = AlertManager()

        self.active_symbols = set()
        self.market_statistics = {}  # symbol -> MarketStatistics
        self.subscribers = set()

        self.db_path = "realtime_market.db"
        self._setup_database()

        # Performance metrics
        self.tick_count = 0
        self.start_time = datetime.now()
        self.last_performance_log = datetime.now()

    def _setup_database(self):
        """Setup real-time market database."""
        conn = sqlite3.connect(self.db_path)

        # Market ticks table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_ticks (
                tick_id TEXT PRIMARY KEY,
                symbol TEXT,
                timestamp TEXT,
                message_type TEXT,
                price REAL,
                size INTEGER,
                bid_price REAL,
                ask_price REAL,
                bid_size INTEGER,
                ask_size INTEGER,
                volume INTEGER,
                metadata TEXT,
                created_at TEXT
            )
        """
        )

        # Market statistics table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_statistics (
                stat_id TEXT PRIMARY KEY,
                symbol TEXT,
                timestamp TEXT,
                price REAL,
                change_amount REAL,
                change_percent REAL,
                volume INTEGER,
                avg_volume REAL,
                volatility REAL,
                rsi REAL,
                macd REAL,
                bollinger_position REAL,
                created_at TEXT
            )
        """
        )

        # Alerts table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_alerts (
                alert_id TEXT PRIMARY KEY,
                symbol TEXT,
                alert_type TEXT,
                message TEXT,
                severity TEXT,
                timestamp TEXT,
                data TEXT,
                acknowledged BOOLEAN,
                created_at TEXT
            )
        """
        )

        # Order book snapshots table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_book_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                symbol TEXT,
                timestamp TEXT,
                bids TEXT,
                asks TEXT,
                spread REAL,
                mid_price REAL,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    async def add_data_source(self, source: DataSource, **kwargs) -> bool:
        """Add a market data source."""
        try:
            if source == DataSource.YAHOO_FINANCE:
                handler = YahooFinanceHandler()
            elif source == DataSource.SIMULATED:
                handler = SimulatedDataHandler()
            else:
                logger.error(f"Unsupported data source: {source}")
                return False

            # Connect to data source
            if await handler.connect():
                self.data_handlers[source] = handler
                handler.add_subscriber(self._handle_market_tick)
                logger.info(f"Added data source: {source.value}")
                return True
            else:
                logger.error(f"Failed to connect to data source: {source.value}")
                return False

        except Exception as e:
            logger.error(f"Error adding data source {source.value}: {e}")
            return False

    async def subscribe_symbols(
        self, symbols: list[str], source: DataSource = DataSource.SIMULATED
    ):
        """Subscribe to market data for symbols."""
        if source not in self.data_handlers:
            logger.error(f"Data source {source.value} not available")
            return

        handler = self.data_handlers[source]
        await handler.subscribe(symbols, [MessageType.TRADE, MessageType.QUOTE])

        self.active_symbols.update(symbols)
        logger.info(f"Subscribed to {len(symbols)} symbols: {symbols}")

    async def unsubscribe_symbols(
        self, symbols: list[str], source: DataSource = DataSource.SIMULATED
    ):
        """Unsubscribe from market data for symbols."""
        if source not in self.data_handlers:
            return

        handler = self.data_handlers[source]
        await handler.unsubscribe(symbols)

        self.active_symbols.difference_update(symbols)
        logger.info(f"Unsubscribed from {len(symbols)} symbols")

    async def _handle_market_tick(self, tick: MarketTick):
        """Handle incoming market tick data."""
        try:
            self.tick_count += 1

            # Update technical indicators
            self.technical_calculator.update(tick.symbol, tick)

            # Update order book
            await self.order_book_manager.update_order_book(tick.symbol, tick)

            # Update anomaly detection
            self.anomaly_detector.update_training_data(tick.symbol, tick)

            # Calculate market statistics
            stats = await self._calculate_market_statistics(tick.symbol, tick)
            if stats:
                self.market_statistics[tick.symbol] = stats

                # Check for alerts
                await self.alert_manager.check_alerts(tick.symbol, tick, stats)

                # Check for anomalies
                anomaly = self.anomaly_detector.detect_anomaly(tick.symbol, tick)
                if anomaly:
                    await self._handle_anomaly(anomaly)

            # Store tick data
            await self._store_tick(tick)

            # Notify subscribers
            await self._notify_subscribers(tick, stats)

            # Log performance periodically
            await self._log_performance()

        except Exception as e:
            logger.error(f"Error handling market tick: {e}")

    async def _calculate_market_statistics(
        self, symbol: str, tick: MarketTick
    ) -> MarketStatistics | None:
        """Calculate real-time market statistics."""
        try:
            if not tick.price:
                return None

            # Get previous statistics for change calculation
            prev_stats = self.market_statistics.get(symbol)
            prev_price = prev_stats.price if prev_stats else tick.price

            # Calculate price change
            change = tick.price - prev_price
            change_percent = (change / prev_price * 100) if prev_price != 0 else 0

            # Calculate technical indicators
            rsi = self.technical_calculator.calculate_rsi(symbol)
            macd_data = self.technical_calculator.calculate_macd(symbol)
            macd = macd_data["macd"] if macd_data else None

            bollinger_data = self.technical_calculator.calculate_bollinger_bands(symbol)
            bollinger_position = (
                bollinger_data["bb_position"] if bollinger_data else None
            )

            volatility = self.technical_calculator.calculate_volatility(symbol) or 0

            # Calculate average volume (simplified)
            volume_history = list(self.technical_calculator.volume_history[symbol])
            avg_volume = np.mean(volume_history) if volume_history else tick.volume or 0

            stats = MarketStatistics(
                symbol=symbol,
                timestamp=tick.timestamp,
                price=tick.price,
                change=change,
                change_percent=change_percent,
                volume=tick.volume or 0,
                avg_volume=avg_volume,
                volatility=volatility,
                rsi=rsi,
                macd=macd,
                bollinger_position=bollinger_position,
            )

            return stats

        except Exception as e:
            logger.error(f"Error calculating market statistics for {symbol}: {e}")
            return None

    async def _handle_anomaly(self, anomaly: dict[str, Any]):
        """Handle detected market anomaly."""
        alert = MarketAlert(
            alert_id=str(uuid.uuid4()),
            symbol=anomaly["symbol"],
            alert_type=AlertType.MARKET_ANOMALY,
            message=f"Market anomaly detected for {anomaly['symbol']}: score {anomaly['anomaly_score']:.3f}",
            severity=anomaly["severity"],
            timestamp=anomaly["timestamp"],
            data=anomaly,
        )

        await self.alert_manager._trigger_alert(alert)

    async def _store_tick(self, tick: MarketTick):
        """Store market tick in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            tick_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO market_ticks
                (tick_id, symbol, timestamp, message_type, price, size,
                 bid_price, ask_price, bid_size, ask_size, volume, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    tick_id,
                    tick.symbol,
                    tick.timestamp.isoformat(),
                    tick.message_type.value,
                    tick.price,
                    tick.size,
                    tick.bid_price,
                    tick.ask_price,
                    tick.bid_size,
                    tick.ask_size,
                    tick.volume,
                    json.dumps(tick.metadata),
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing tick: {e}")

    async def _notify_subscribers(
        self, tick: MarketTick, stats: MarketStatistics | None
    ):
        """Notify subscribers of new market data."""
        for callback in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(tick, stats)
                else:
                    callback(tick, stats)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")

    async def _log_performance(self):
        """Log performance metrics."""
        now = datetime.now()
        if (now - self.last_performance_log).seconds >= 60:  # Log every minute
            elapsed = (now - self.start_time).total_seconds()
            ticks_per_second = self.tick_count / elapsed if elapsed > 0 else 0

            logger.info(
                f"Performance: {ticks_per_second:.1f} ticks/sec, "
                f"Total ticks: {self.tick_count}, "
                f"Active symbols: {len(self.active_symbols)}"
            )

            self.last_performance_log = now

    def add_subscriber(
        self, callback: Callable[[MarketTick, MarketStatistics | None], None]
    ):
        """Add market data subscriber."""
        self.subscribers.add(callback)

    def remove_subscriber(
        self, callback: Callable[[MarketTick, MarketStatistics | None], None]
    ):
        """Remove market data subscriber."""
        self.subscribers.discard(callback)

    def get_market_statistics(self, symbol: str) -> MarketStatistics | None:
        """Get current market statistics for symbol."""
        return self.market_statistics.get(symbol)

    def get_order_book(self, symbol: str) -> OrderBook | None:
        """Get current order book for symbol."""
        return self.order_book_manager.get_order_book(symbol)

    def add_alert_rule(self, rule_id: str, rule: dict[str, Any]):
        """Add alert rule."""
        self.alert_manager.add_alert_rule(rule_id, rule)

    def get_active_alerts(self, symbol: str | None = None) -> list[MarketAlert]:
        """Get active alerts."""
        return self.alert_manager.get_active_alerts(symbol)

    async def shutdown(self):
        """Shutdown the market engine."""
        logger.info("Shutting down real-time market engine...")

        # Disconnect all data handlers
        for handler in self.data_handlers.values():
            await handler.disconnect()

        logger.info("Real-time market engine shutdown complete")


# Example usage and testing
async def main():
    """Example usage of the Real-Time Market Engine."""

    # Initialize engine
    engine = RealTimeMarketEngine()

    # Add data sources
    print("Adding data sources...")
    await engine.add_data_source(DataSource.SIMULATED)

    # Define sample symbols
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]

    # Subscribe to market data
    print(f"Subscribing to {len(symbols)} symbols...")
    await engine.subscribe_symbols(symbols, DataSource.SIMULATED)

    # Add alert rules
    print("Setting up alert rules...")

    # Price movement alert
    engine.add_alert_rule(
        "price_movement",
        {
            "id": "price_movement",
            "type": "price_movement",
            "price_change_percent": 2.0,  # 2% price movement
            "severity": "medium",
            "symbols": symbols,
        },
    )

    # Volume spike alert
    engine.add_alert_rule(
        "volume_spike",
        {
            "id": "volume_spike",
            "type": "volume_spike",
            "volume_spike_ratio": 3.0,  # 3x average volume
            "severity": "high",
            "symbols": symbols,
        },
    )

    # RSI overbought/oversold alerts
    engine.add_alert_rule(
        "rsi_overbought",
        {
            "id": "rsi_overbought",
            "type": "technical_indicator",
            "rsi_overbought": 70,
            "severity": "medium",
            "symbols": symbols,
        },
    )

    engine.add_alert_rule(
        "rsi_oversold",
        {
            "id": "rsi_oversold",
            "type": "technical_indicator",
            "rsi_oversold": 30,
            "severity": "medium",
            "symbols": symbols,
        },
    )

    # Add market data subscriber
    def market_data_callback(tick: MarketTick, stats: MarketStatistics | None):
        if stats and tick.message_type == MessageType.TRADE:
            print(
                f"{tick.symbol}: ${stats.price:.2f} "
                f"({stats.change_percent:+.2f}%) "
                f"Vol: {stats.volume:,} "
                f"RSI: {stats.rsi:.1f if stats.rsi else 'N/A'}"
            )

    engine.add_subscriber(market_data_callback)

    # Add alert subscriber
    def alert_callback(alert: MarketAlert):
        print(f"🚨 ALERT [{alert.severity.upper()}]: {alert.message}")

    engine.alert_manager.add_subscriber(alert_callback)

    # Add order book subscriber
    def order_book_callback(symbol: str, book: OrderBook):
        depth = book.get_depth(3)
        if depth["bids"] and depth["asks"]:
            print(
                f"{symbol} Order Book - "
                f"Bid: ${depth['bids'][0][0]:.2f} "
                f"Ask: ${depth['asks'][0][0]:.2f} "
                f"Spread: ${depth['spread']:.4f}"
            )

    engine.order_book_manager.add_subscriber(order_book_callback)

    print("\n" + "=" * 60)
    print("REAL-TIME MARKET DATA STREAMING")
    print("=" * 60)
    print("Streaming market data... (Press Ctrl+C to stop)")

    try:
        # Run for demonstration
        await asyncio.sleep(30)  # Run for 30 seconds

        print("\n" + "=" * 60)
        print("MARKET STATISTICS SUMMARY")
        print("=" * 60)

        for symbol in symbols:
            stats = engine.get_market_statistics(symbol)
            if stats:
                print(f"\n{symbol}:")
                print(f"  Price: ${stats.price:.2f} ({stats.change_percent:+.2f}%)")
                print(f"  Volume: {stats.volume:,} (Avg: {stats.avg_volume:,.0f})")
                print(f"  Volatility: {stats.volatility:.2f}%")
                print(f"  RSI: {stats.rsi:.1f if stats.rsi else 'N/A'}")
                print(f"  MACD: {stats.macd:.4f if stats.macd else 'N/A'}")

                # Order book info
                book = engine.get_order_book(symbol)
                if book:
                    depth = book.get_depth(1)
                    print(
                        f"  Bid/Ask: ${depth['bids'][0][0]:.2f} / ${depth['asks'][0][0]:.2f}"
                    )
                    print(f"  Spread: ${depth['spread']:.4f}")

        # Show active alerts
        active_alerts = engine.get_active_alerts()
        if active_alerts:
            print("\n" + "=" * 60)
            print("ACTIVE ALERTS")
            print("=" * 60)

            for alert in active_alerts[:5]:  # Show first 5
                print(f"[{alert.severity.upper()}] {alert.symbol}: {alert.message}")
                print(f"  Time: {alert.timestamp.strftime('%H:%M:%S')}")

        print(f"\nProcessed {engine.tick_count:,} market ticks")

    except KeyboardInterrupt:
        print("\nStopping market data stream...")

    finally:
        await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
