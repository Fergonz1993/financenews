"""
Advanced Analytics Suite Module

This module provides sophisticated analytics capabilities including insider activity correlation,
alternative data integration, quantitative analysis, and market microstructure analysis.
"""

import asyncio
import json
import logging
import sqlite3
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class AnalyticsType(Enum):
    """Types of advanced analytics."""

    INSIDER_ACTIVITY = "insider_activity"
    ALTERNATIVE_DATA = "alternative_data"
    QUANTITATIVE = "quantitative"
    MARKET_MICROSTRUCTURE = "market_microstructure"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    NETWORK_ANALYSIS = "network_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    CORRELATION_ANALYSIS = "correlation_analysis"


@dataclass
class InsiderTransaction:
    """Insider trading transaction data."""

    symbol: str
    insider_name: str
    position: str
    transaction_type: str  # 'buy', 'sell'
    transaction_date: datetime
    shares: int
    price: float
    value: float
    ownership_percentage: float
    form_type: str  # '4', '5', '3'
    sentiment_impact: float = 0.0


@dataclass
class AlternativeDataPoint:
    """Alternative data point."""

    data_type: str
    symbol: str
    timestamp: datetime
    value: float
    confidence: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuantitativeSignal:
    """Quantitative trading signal."""

    signal_id: str
    strategy_name: str
    symbol: str
    signal_type: str  # 'long', 'short', 'neutral'
    strength: float  # 0-1
    confidence: float  # 0-1
    entry_price: float
    target_price: float | None
    stop_loss: float | None
    holding_period: str
    risk_metrics: dict[str, float]
    timestamp: datetime


@dataclass
class MarketMicrostructureMetrics:
    """Market microstructure analysis metrics."""

    symbol: str
    timestamp: datetime
    bid_ask_spread: float
    market_impact: float
    price_efficiency: float
    order_flow_imbalance: float
    volatility_clustering: float
    liquidity_score: float
    transaction_costs: float
    market_fragmentation: float


@dataclass
class NetworkNode:
    """Network analysis node."""

    node_id: str
    node_type: str  # 'company', 'sector', 'executive', 'analyst'
    attributes: dict[str, Any]
    centrality_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class NetworkEdge:
    """Network analysis edge."""

    source: str
    target: str
    edge_type: str  # 'correlation', 'ownership', 'partnership', 'analyst_coverage'
    weight: float
    attributes: dict[str, Any] = field(default_factory=dict)


class InsiderActivityAnalyzer:
    """Analyze insider trading activity and its correlation with market movements."""

    def __init__(self):
        self.db_path = "insider_activity.db"
        self._setup_database()

    def _setup_database(self):
        """Setup database for insider activity storage."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS insider_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                insider_name TEXT,
                position TEXT,
                transaction_type TEXT,
                transaction_date TEXT,
                shares INTEGER,
                price REAL,
                value REAL,
                ownership_percentage REAL,
                form_type TEXT,
                sentiment_impact REAL,
                timestamp TEXT
            )
        """
        )
        conn.commit()
        conn.close()

    async def fetch_insider_data(
        self, symbol: str, days: int = 90
    ) -> list[InsiderTransaction]:
        """Fetch insider trading data for a symbol."""
        try:
            # This would integrate with SEC EDGAR API or similar
            # For demo purposes, we'll simulate data
            transactions = []

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Simulate insider transactions
            for i in range(np.random.randint(5, 20)):
                transaction_date = start_date + timedelta(
                    days=np.random.randint(0, days)
                )

                transaction = InsiderTransaction(
                    symbol=symbol,
                    insider_name=f"Insider_{i}",
                    position=np.random.choice(["CEO", "CFO", "Director", "Officer"]),
                    transaction_type=np.random.choice(["buy", "sell"], p=[0.3, 0.7]),
                    transaction_date=transaction_date,
                    shares=np.random.randint(1000, 100000),
                    price=round(np.random.uniform(50, 300), 2),
                    value=0,  # Will calculate
                    ownership_percentage=round(np.random.uniform(0.1, 5.0), 2),
                    form_type=np.random.choice(["4", "5"], p=[0.9, 0.1]),
                )

                transaction.value = transaction.shares * transaction.price
                transactions.append(transaction)

            # Store in database
            await self._store_transactions(transactions)

            return transactions

        except Exception as e:
            logger.error(f"Error fetching insider data for {symbol}: {e}")
            return []

    async def analyze_insider_sentiment(
        self, symbol: str, transactions: list[InsiderTransaction]
    ) -> dict[str, Any]:
        """Analyze insider sentiment and its impact."""
        try:
            if not transactions:
                return {"sentiment_score": 0, "confidence": 0, "analysis": {}}

            # Calculate weighted sentiment based on transaction size and position
            total_value = 0
            weighted_sentiment = 0

            position_weights = {"CEO": 1.0, "CFO": 0.8, "Director": 0.6, "Officer": 0.4}

            for transaction in transactions:
                # Positive for buys, negative for sells
                sentiment = 1.0 if transaction.transaction_type == "buy" else -1.0

                # Weight by position importance and transaction size
                position_weight = position_weights.get(transaction.position, 0.5)
                size_weight = np.log(transaction.value + 1) / 20  # Normalize

                weight = position_weight * size_weight
                weighted_sentiment += sentiment * weight
                total_value += weight

            # Normalize sentiment score
            sentiment_score = weighted_sentiment / total_value if total_value > 0 else 0
            sentiment_score = max(-1, min(1, sentiment_score))

            # Calculate confidence based on data quality and volume
            confidence = min(
                1.0, len(transactions) / 10
            )  # More transactions = higher confidence

            # Detailed analysis
            analysis = {
                "total_transactions": len(transactions),
                "buy_transactions": sum(
                    1 for t in transactions if t.transaction_type == "buy"
                ),
                "sell_transactions": sum(
                    1 for t in transactions if t.transaction_type == "sell"
                ),
                "total_buy_value": sum(
                    t.value for t in transactions if t.transaction_type == "buy"
                ),
                "total_sell_value": sum(
                    t.value for t in transactions if t.transaction_type == "sell"
                ),
                "avg_transaction_size": np.mean([t.value for t in transactions]),
                "insider_positions": list({t.position for t in transactions}),
            }

            return {
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "analysis": analysis,
                "transactions": transactions,
            }

        except Exception as e:
            logger.error(f"Error analyzing insider sentiment for {symbol}: {e}")
            return {"sentiment_score": 0, "confidence": 0, "analysis": {}}

    async def correlate_with_price_movement(
        self, symbol: str, insider_data: dict[str, Any], price_data: pd.DataFrame
    ) -> dict[str, Any]:
        """Correlate insider activity with subsequent price movements."""
        try:
            transactions = insider_data.get("transactions", [])

            if not transactions or price_data.empty:
                return {"correlation": 0, "significance": 0, "analysis": {}}

            # Create time series of insider sentiment
            sentiment_series = []
            price_returns = []

            for transaction in transactions:
                trans_date = transaction.transaction_date

                # Find closest trading day in price data
                closest_date = min(price_data.index, key=lambda x: abs(x - trans_date))

                # Calculate return over next 5, 10, 20 trading days
                try:
                    current_idx = price_data.index.get_loc(closest_date)

                    returns = {}
                    for days in [5, 10, 20]:
                        if current_idx + days < len(price_data):
                            future_price = price_data.iloc[current_idx + days]["Close"]
                            current_price = price_data.iloc[current_idx]["Close"]
                            returns[f"{days}d"] = (
                                future_price - current_price
                            ) / current_price

                    if returns:
                        sentiment = 1 if transaction.transaction_type == "buy" else -1
                        sentiment_series.append(sentiment)
                        price_returns.append(returns)

                except (KeyError, IndexError):
                    continue

            # Calculate correlations
            correlations = {}
            if sentiment_series and price_returns:
                for period in ["5d", "10d", "20d"]:
                    period_returns = [r.get(period, 0) for r in price_returns]
                    if len(sentiment_series) > 3:  # Minimum for correlation
                        corr, p_value = stats.pearsonr(sentiment_series, period_returns)
                        correlations[period] = {
                            "correlation": corr,
                            "p_value": p_value,
                            "significance": (
                                "significant" if p_value < 0.05 else "not_significant"
                            ),
                        }

            # Overall assessment
            avg_correlation = (
                np.mean([c["correlation"] for c in correlations.values()])
                if correlations
                else 0
            )

            analysis = {
                "correlations_by_period": correlations,
                "average_correlation": avg_correlation,
                "data_points": len(sentiment_series),
                "interpretation": self._interpret_correlation(avg_correlation),
            }

            return {
                "correlation": avg_correlation,
                "significance": (
                    min([c["p_value"] for c in correlations.values()])
                    if correlations
                    else 1.0
                ),
                "analysis": analysis,
            }

        except Exception as e:
            logger.error(f"Error correlating insider activity with price movement: {e}")
            return {"correlation": 0, "significance": 0, "analysis": {}}

    def _interpret_correlation(self, correlation: float) -> str:
        """Interpret correlation strength."""
        abs_corr = abs(correlation)

        if abs_corr > 0.7:
            strength = "very strong"
        elif abs_corr > 0.5:
            strength = "strong"
        elif abs_corr > 0.3:
            strength = "moderate"
        elif abs_corr > 0.1:
            strength = "weak"
        else:
            strength = "very weak"

        direction = "positive" if correlation > 0 else "negative"

        return f"{strength} {direction} correlation"

    async def _store_transactions(self, transactions: list[InsiderTransaction]):
        """Store insider transactions in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            for transaction in transactions:
                conn.execute(
                    """
                    INSERT INTO insider_transactions
                    (symbol, insider_name, position, transaction_type, transaction_date,
                     shares, price, value, ownership_percentage, form_type, sentiment_impact, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        transaction.symbol,
                        transaction.insider_name,
                        transaction.position,
                        transaction.transaction_type,
                        transaction.transaction_date.isoformat(),
                        transaction.shares,
                        transaction.price,
                        transaction.value,
                        transaction.ownership_percentage,
                        transaction.form_type,
                        transaction.sentiment_impact,
                        datetime.now().isoformat(),
                    ),
                )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing transactions: {e}")


class AlternativeDataIntegrator:
    """Integrate and analyze alternative data sources."""

    def __init__(self):
        self.data_sources = {}
        self.db_path = "alternative_data.db"
        self._setup_database()

    def _setup_database(self):
        """Setup database for alternative data storage."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alternative_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_type TEXT,
                symbol TEXT,
                timestamp TEXT,
                value REAL,
                confidence REAL,
                source TEXT,
                metadata TEXT
            )
        """
        )
        conn.commit()
        conn.close()

    async def collect_satellite_data(self, symbol: str) -> list[AlternativeDataPoint]:
        """Collect satellite imagery data (e.g., parking lots, shipping activity)."""
        try:
            # Simulate satellite data collection
            data_points = []

            for days_ago in range(30):  # Last 30 days
                date = datetime.now() - timedelta(days=days_ago)

                # Simulate different types of satellite data
                for data_type in [
                    "parking_lot_activity",
                    "shipping_volume",
                    "construction_activity",
                ]:
                    value = np.random.normal(0.5, 0.2)  # Normalized activity level
                    confidence = np.random.uniform(0.7, 0.95)

                    data_point = AlternativeDataPoint(
                        data_type=data_type,
                        symbol=symbol,
                        timestamp=date,
                        value=max(0, min(1, value)),
                        confidence=confidence,
                        source="satellite_imagery",
                        metadata={"location": "headquarters", "weather": "clear"},
                    )
                    data_points.append(data_point)

            await self._store_alternative_data(data_points)
            return data_points

        except Exception as e:
            logger.error(f"Error collecting satellite data for {symbol}: {e}")
            return []

    async def collect_social_media_sentiment(
        self, symbol: str
    ) -> list[AlternativeDataPoint]:
        """Collect social media sentiment data."""
        try:
            # Simulate social media sentiment collection
            data_points = []

            for hours_ago in range(24 * 7):  # Last 7 days, hourly
                timestamp = datetime.now() - timedelta(hours=hours_ago)

                # Simulate sentiment from different platforms
                for platform in ["twitter", "reddit", "stocktwits"]:
                    sentiment = np.random.normal(0, 0.3)  # Centered around neutral
                    confidence = np.random.uniform(0.6, 0.9)

                    data_point = AlternativeDataPoint(
                        data_type=f"{platform}_sentiment",
                        symbol=symbol,
                        timestamp=timestamp,
                        value=max(-1, min(1, sentiment)),
                        confidence=confidence,
                        source=platform,
                        metadata={"post_count": np.random.randint(10, 1000)},
                    )
                    data_points.append(data_point)

            await self._store_alternative_data(data_points)
            return data_points

        except Exception as e:
            logger.error(f"Error collecting social media sentiment for {symbol}: {e}")
            return []

    async def collect_economic_indicators(
        self, symbol: str
    ) -> list[AlternativeDataPoint]:
        """Collect economic indicators relevant to the symbol."""
        try:
            # Simulate economic indicator collection
            data_points = []

            indicators = [
                "consumer_confidence",
                "unemployment_rate",
                "inflation_rate",
                "gdp_growth",
                "interest_rates",
                "commodity_prices",
            ]

            for days_ago in range(90):  # Last 90 days
                date = datetime.now() - timedelta(days=days_ago)

                for indicator in indicators:
                    # Simulate indicator values
                    if indicator == "consumer_confidence":
                        value = np.random.normal(100, 10)
                    elif indicator == "unemployment_rate":
                        value = np.random.normal(4.5, 0.5)
                    elif indicator == "inflation_rate":
                        value = np.random.normal(2.5, 0.3)
                    else:
                        value = np.random.normal(0, 1)

                    data_point = AlternativeDataPoint(
                        data_type=indicator,
                        symbol=symbol,
                        timestamp=date,
                        value=value,
                        confidence=0.95,  # Economic data usually high confidence
                        source="economic_bureau",
                        metadata={
                            "unit": "percent" if "rate" in indicator else "index"
                        },
                    )
                    data_points.append(data_point)

            await self._store_alternative_data(data_points)
            return data_points

        except Exception as e:
            logger.error(f"Error collecting economic indicators for {symbol}: {e}")
            return []

    async def analyze_alternative_data_correlation(
        self, symbol: str, price_data: pd.DataFrame
    ) -> dict[str, Any]:
        """Analyze correlation between alternative data and price movements."""
        try:
            # Fetch alternative data from database
            alt_data = await self._fetch_alternative_data(symbol)

            if not alt_data or price_data.empty:
                return {"correlations": {}, "insights": []}

            # Group data by type
            data_by_type = {}
            for point in alt_data:
                if point.data_type not in data_by_type:
                    data_by_type[point.data_type] = []
                data_by_type[point.data_type].append(point)

            correlations = {}
            insights = []

            for data_type, points in data_by_type.items():
                if len(points) < 10:  # Need minimum data points
                    continue

                # Create time series
                df = pd.DataFrame(
                    [{"timestamp": p.timestamp, "value": p.value} for p in points]
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)

                # Resample to daily frequency
                daily_alt_data = df.resample("D").mean()

                # Align with price data
                aligned_data = pd.merge(
                    price_data[["Close"]].pct_change(),
                    daily_alt_data,
                    left_index=True,
                    right_index=True,
                    how="inner",
                )

                if len(aligned_data) > 10:
                    corr, p_value = stats.pearsonr(
                        aligned_data["Close"].dropna(), aligned_data["value"].dropna()
                    )

                    correlations[data_type] = {
                        "correlation": corr,
                        "p_value": p_value,
                        "significance": (
                            "significant" if p_value < 0.05 else "not_significant"
                        ),
                        "data_points": len(aligned_data),
                    }

                    # Generate insights
                    if abs(corr) > 0.3 and p_value < 0.05:
                        direction = "positively" if corr > 0 else "negatively"
                        insights.append(
                            f"{data_type.replace('_', ' ').title()} is {direction} "
                            f"correlated with price movements (r={corr:.3f})"
                        )

            return {
                "correlations": correlations,
                "insights": insights,
                "data_coverage": len(data_by_type),
            }

        except Exception as e:
            logger.error(f"Error analyzing alternative data correlation: {e}")
            return {"correlations": {}, "insights": []}

    async def _store_alternative_data(self, data_points: list[AlternativeDataPoint]):
        """Store alternative data points in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            for point in data_points:
                conn.execute(
                    """
                    INSERT INTO alternative_data
                    (data_type, symbol, timestamp, value, confidence, source, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        point.data_type,
                        point.symbol,
                        point.timestamp.isoformat(),
                        point.value,
                        point.confidence,
                        point.source,
                        json.dumps(point.metadata),
                    ),
                )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing alternative data: {e}")

    async def _fetch_alternative_data(
        self, symbol: str, days: int = 90
    ) -> list[AlternativeDataPoint]:
        """Fetch alternative data from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            cursor = conn.execute(
                """
                SELECT data_type, symbol, timestamp, value, confidence, source, metadata
                FROM alternative_data
                WHERE symbol = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """,
                (symbol, cutoff_date),
            )

            data_points = []
            for row in cursor.fetchall():
                point = AlternativeDataPoint(
                    data_type=row[0],
                    symbol=row[1],
                    timestamp=datetime.fromisoformat(row[2]),
                    value=row[3],
                    confidence=row[4],
                    source=row[5],
                    metadata=json.loads(row[6]) if row[6] else {},
                )
                data_points.append(point)

            conn.close()
            return data_points

        except Exception as e:
            logger.error(f"Error fetching alternative data: {e}")
            return []


class QuantitativeAnalyzer:
    """Advanced quantitative analysis and signal generation."""

    def __init__(self):
        self.strategies = {}
        self.signals_db = "quantitative_signals.db"
        self._setup_database()

    def _setup_database(self):
        """Setup database for quantitative signals."""
        conn = sqlite3.connect(self.signals_db)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quantitative_signals (
                signal_id TEXT PRIMARY KEY,
                strategy_name TEXT,
                symbol TEXT,
                signal_type TEXT,
                strength REAL,
                confidence REAL,
                entry_price REAL,
                target_price REAL,
                stop_loss REAL,
                holding_period TEXT,
                risk_metrics TEXT,
                timestamp TEXT
            )
        """
        )
        conn.commit()
        conn.close()

    async def momentum_strategy(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        lookback_periods: list[int] | None = None,
    ) -> QuantitativeSignal:
        """Generate momentum-based signals."""
        if lookback_periods is None:
            lookback_periods = [10, 20, 50]
        try:
            if price_data.empty or len(price_data) < max(lookback_periods):
                return None

            signals = []

            for period in lookback_periods:
                # Calculate momentum
                momentum = (
                    price_data["Close"][-1] - price_data["Close"][-period]
                ) / price_data["Close"][-period]
                signals.append(momentum)

            # Weighted average momentum (shorter periods have higher weight)
            weights = [1 / p for p in lookback_periods]
            weighted_momentum = np.average(signals, weights=weights)

            # Determine signal type and strength
            if weighted_momentum > 0.05:  # 5% momentum threshold
                signal_type = "long"
                strength = min(1.0, weighted_momentum * 10)
            elif weighted_momentum < -0.05:
                signal_type = "short"
                strength = min(1.0, abs(weighted_momentum) * 10)
            else:
                signal_type = "neutral"
                strength = 0.5

            # Calculate confidence based on momentum consistency
            momentum_std = np.std(signals)
            confidence = max(0.3, 1 - momentum_std * 5)

            # Risk metrics
            volatility = price_data["Close"].pct_change().std() * np.sqrt(252)
            max_drawdown = self._calculate_max_drawdown(price_data["Close"])

            risk_metrics = {
                "volatility": volatility,
                "max_drawdown": max_drawdown,
                "sharpe_estimate": (
                    weighted_momentum / volatility if volatility > 0 else 0
                ),
            }

            # Price targets
            current_price = price_data["Close"][-1]
            atr = self._calculate_atr(price_data)

            if signal_type == "long":
                target_price = current_price * (1 + weighted_momentum * 0.5)
                stop_loss = current_price - (2 * atr)
            elif signal_type == "short":
                target_price = current_price * (
                    1 + weighted_momentum * 0.5
                )  # negative momentum
                stop_loss = current_price + (2 * atr)
            else:
                target_price = None
                stop_loss = None

            signal = QuantitativeSignal(
                signal_id=f"momentum_{symbol}_{int(datetime.now().timestamp())}",
                strategy_name="momentum",
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence=confidence,
                entry_price=current_price,
                target_price=target_price,
                stop_loss=stop_loss,
                holding_period="5-20 days",
                risk_metrics=risk_metrics,
                timestamp=datetime.now(),
            )

            await self._store_signal(signal)
            return signal

        except Exception as e:
            logger.error(f"Error in momentum strategy for {symbol}: {e}")
            return None

    async def mean_reversion_strategy(
        self, symbol: str, price_data: pd.DataFrame, lookback_period: int = 20
    ) -> QuantitativeSignal:
        """Generate mean reversion signals."""
        try:
            if price_data.empty or len(price_data) < lookback_period * 2:
                return None

            # Calculate Bollinger Bands
            sma = price_data["Close"].rolling(lookback_period).mean()
            std = price_data["Close"].rolling(lookback_period).std()

            upper_band = sma + (2 * std)
            lower_band = sma - (2 * std)

            current_price = price_data["Close"][-1]
            current_sma = sma[-1]
            current_upper = upper_band[-1]
            current_lower = lower_band[-1]

            # Z-score calculation
            z_score = (current_price - current_sma) / std[-1]

            # Signal generation
            if z_score > 2:  # Price above upper band
                signal_type = "short"
                strength = min(1.0, (abs(z_score) - 2) / 2)
            elif z_score < -2:  # Price below lower band
                signal_type = "long"
                strength = min(1.0, (abs(z_score) - 2) / 2)
            else:
                signal_type = "neutral"
                strength = 0.5

            # Confidence based on band distance and volatility regime
            confidence = min(1.0, abs(z_score) / 3) * 0.8

            # Risk metrics
            volatility = price_data["Close"].pct_change().std() * np.sqrt(252)

            risk_metrics = {
                "volatility": volatility,
                "z_score": z_score,
                "band_width": (current_upper - current_lower) / current_sma,
            }

            # Price targets
            if signal_type == "long":
                target_price = current_sma
                stop_loss = current_lower * 0.98
            elif signal_type == "short":
                target_price = current_sma
                stop_loss = current_upper * 1.02
            else:
                target_price = None
                stop_loss = None

            signal = QuantitativeSignal(
                signal_id=f"mean_reversion_{symbol}_{int(datetime.now().timestamp())}",
                strategy_name="mean_reversion",
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence=confidence,
                entry_price=current_price,
                target_price=target_price,
                stop_loss=stop_loss,
                holding_period="1-10 days",
                risk_metrics=risk_metrics,
                timestamp=datetime.now(),
            )

            await self._store_signal(signal)
            return signal

        except Exception as e:
            logger.error(f"Error in mean reversion strategy for {symbol}: {e}")
            return None

    async def statistical_arbitrage(
        self,
        symbol_pair: tuple[str, str],
        price_data_1: pd.DataFrame,
        price_data_2: pd.DataFrame,
    ) -> tuple[QuantitativeSignal, QuantitativeSignal] | None:
        """Generate statistical arbitrage signals for a pair of symbols."""
        try:
            if price_data_1.empty or price_data_2.empty:
                return None

            # Align data
            aligned_data = pd.merge(
                price_data_1[["Close"]].rename(columns={"Close": symbol_pair[0]}),
                price_data_2[["Close"]].rename(columns={"Close": symbol_pair[1]}),
                left_index=True,
                right_index=True,
                how="inner",
            )

            if len(aligned_data) < 50:  # Need sufficient data
                return None

            # Calculate spread
            spread = aligned_data[symbol_pair[0]] - aligned_data[symbol_pair[1]]
            spread_mean = spread.mean()
            spread_std = spread.std()

            # Current spread
            current_spread = spread[-1]
            z_score = (current_spread - spread_mean) / spread_std

            # Cointegration test (simplified)
            correlation = aligned_data[symbol_pair[0]].corr(
                aligned_data[symbol_pair[1]]
            )

            if abs(correlation) < 0.7:  # Pairs must be correlated
                return None

            # Signal generation
            if z_score > 2:  # Spread too wide
                # Short symbol_1, Long symbol_2
                signal_1_type = "short"
                signal_2_type = "long"
                strength = min(1.0, (abs(z_score) - 2) / 2)
            elif z_score < -2:  # Spread too narrow
                # Long symbol_1, Short symbol_2
                signal_1_type = "long"
                signal_2_type = "short"
                strength = min(1.0, (abs(z_score) - 2) / 2)
            else:
                return None  # No signal

            confidence = min(1.0, abs(correlation) * abs(z_score) / 3)

            # Risk metrics
            spread_volatility = spread.std()
            half_life = self._calculate_half_life(spread)

            risk_metrics = {
                "correlation": correlation,
                "spread_volatility": spread_volatility,
                "z_score": z_score,
                "half_life": half_life,
            }

            # Create signals for both symbols
            current_time = datetime.now()

            signal_1 = QuantitativeSignal(
                signal_id=f"stat_arb_{symbol_pair[0]}_{int(current_time.timestamp())}",
                strategy_name="statistical_arbitrage",
                symbol=symbol_pair[0],
                signal_type=signal_1_type,
                strength=strength,
                confidence=confidence,
                entry_price=aligned_data[symbol_pair[0]][-1],
                target_price=None,  # Exit when spread normalizes
                stop_loss=None,  # Managed by spread
                holding_period=f"{int(half_life)}-{int(half_life*2)} days",
                risk_metrics=risk_metrics,
                timestamp=current_time,
            )

            signal_2 = QuantitativeSignal(
                signal_id=f"stat_arb_{symbol_pair[1]}_{int(current_time.timestamp())}",
                strategy_name="statistical_arbitrage",
                symbol=symbol_pair[1],
                signal_type=signal_2_type,
                strength=strength,
                confidence=confidence,
                entry_price=aligned_data[symbol_pair[1]][-1],
                target_price=None,
                stop_loss=None,
                holding_period=f"{int(half_life)}-{int(half_life*2)} days",
                risk_metrics=risk_metrics,
                timestamp=current_time,
            )

            await self._store_signal(signal_1)
            await self._store_signal(signal_2)

            return (signal_1, signal_2)

        except Exception as e:
            logger.error(f"Error in statistical arbitrage for {symbol_pair}: {e}")
            return None

    def _calculate_atr(self, price_data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        try:
            high_low = price_data["High"] - price_data["Low"]
            high_close = np.abs(price_data["High"] - price_data["Close"].shift())
            low_close = np.abs(price_data["Low"] - price_data["Close"].shift())

            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = true_range.rolling(period).mean()

            return atr[-1] if not np.isnan(atr[-1]) else 0

        except Exception:
            return 0

    def _calculate_max_drawdown(self, price_series: pd.Series) -> float:
        """Calculate maximum drawdown."""
        try:
            cumulative = (1 + price_series.pct_change()).cumprod()
            rolling_max = cumulative.expanding().max()
            drawdown = (cumulative - rolling_max) / rolling_max

            return abs(drawdown.min())

        except Exception:
            return 0

    def _calculate_half_life(self, spread_series: pd.Series) -> float:
        """Calculate half-life of mean reversion."""
        try:
            # Simple linear regression approach
            spread_lag = spread_series.shift(1).dropna()
            spread_current = spread_series[1:].values

            if len(spread_lag) < 2:
                return 10  # Default

            # Fit AR(1) model: spread_t = alpha + beta * spread_t-1 + error
            X = np.column_stack([np.ones(len(spread_lag)), spread_lag.values])
            y = spread_current

            coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
            beta = coeffs[1]

            if beta >= 1 or beta <= 0:
                return 10  # No mean reversion

            half_life = -np.log(2) / np.log(beta)
            return max(1, min(100, half_life))  # Bound between 1 and 100 days

        except Exception:
            return 10

    async def _store_signal(self, signal: QuantitativeSignal):
        """Store quantitative signal in database."""
        try:
            conn = sqlite3.connect(self.signals_db)
            conn.execute(
                """
                INSERT OR REPLACE INTO quantitative_signals
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    signal.signal_id,
                    signal.strategy_name,
                    signal.symbol,
                    signal.signal_type,
                    signal.strength,
                    signal.confidence,
                    signal.entry_price,
                    signal.target_price,
                    signal.stop_loss,
                    signal.holding_period,
                    json.dumps(signal.risk_metrics),
                    signal.timestamp.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing signal: {e}")


class MarketMicrostructureAnalyzer:
    """Analyze market microstructure and liquidity metrics."""

    def __init__(self):
        self.db_path = "microstructure.db"
        self._setup_database()

    def _setup_database(self):
        """Setup database for microstructure data."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS microstructure_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timestamp TEXT,
                bid_ask_spread REAL,
                market_impact REAL,
                price_efficiency REAL,
                order_flow_imbalance REAL,
                volatility_clustering REAL,
                liquidity_score REAL,
                transaction_costs REAL,
                market_fragmentation REAL
            )
        """
        )
        conn.commit()
        conn.close()

    async def analyze_microstructure(
        self, symbol: str, tick_data: pd.DataFrame = None
    ) -> MarketMicrostructureMetrics:
        """Analyze market microstructure metrics."""
        try:
            # For demo purposes, simulate tick data if not provided
            if tick_data is None or tick_data.empty:
                tick_data = self._simulate_tick_data(symbol)

            current_time = datetime.now()

            # Calculate bid-ask spread
            if "bid" in tick_data.columns and "ask" in tick_data.columns:
                bid_ask_spread = (tick_data["ask"] - tick_data["bid"]).mean()
                bid_ask_spread_pct = bid_ask_spread / tick_data["price"].mean()
            else:
                # Estimate from high-low spread
                bid_ask_spread_pct = (
                    (tick_data["high"] - tick_data["low"]).mean()
                    / tick_data["price"].mean()
                    * 0.5
                )

            # Market impact estimation
            market_impact = self._calculate_market_impact(tick_data)

            # Price efficiency (random walk test)
            price_efficiency = self._calculate_price_efficiency(tick_data)

            # Order flow imbalance
            order_flow_imbalance = self._calculate_order_flow_imbalance(tick_data)

            # Volatility clustering (GARCH effect)
            volatility_clustering = self._calculate_volatility_clustering(tick_data)

            # Liquidity score
            liquidity_score = self._calculate_liquidity_score(
                tick_data, bid_ask_spread_pct
            )

            # Transaction costs estimation
            transaction_costs = bid_ask_spread_pct + market_impact

            # Market fragmentation (simplified)
            market_fragmentation = np.random.uniform(0.1, 0.3)  # Placeholder

            metrics = MarketMicrostructureMetrics(
                symbol=symbol,
                timestamp=current_time,
                bid_ask_spread=bid_ask_spread_pct,
                market_impact=market_impact,
                price_efficiency=price_efficiency,
                order_flow_imbalance=order_flow_imbalance,
                volatility_clustering=volatility_clustering,
                liquidity_score=liquidity_score,
                transaction_costs=transaction_costs,
                market_fragmentation=market_fragmentation,
            )

            await self._store_microstructure_metrics(metrics)
            return metrics

        except Exception as e:
            logger.error(f"Error analyzing microstructure for {symbol}: {e}")
            return None

    def _simulate_tick_data(self, symbol: str, num_ticks: int = 1000) -> pd.DataFrame:
        """Simulate tick data for analysis."""
        np.random.seed(42)  # For reproducible results

        # Generate price path
        initial_price = 100
        returns = np.random.normal(0, 0.001, num_ticks)  # Small returns
        prices = initial_price * np.exp(np.cumsum(returns))

        # Generate volumes
        volumes = np.random.exponential(1000, num_ticks)

        # Generate bid-ask spreads
        spreads = np.random.exponential(0.01, num_ticks)
        bids = prices - spreads / 2
        asks = prices + spreads / 2

        # Generate highs and lows
        highs = prices + np.random.exponential(0.005, num_ticks)
        lows = prices - np.random.exponential(0.005, num_ticks)

        tick_data = pd.DataFrame(
            {
                "price": prices,
                "volume": volumes,
                "bid": bids,
                "ask": asks,
                "high": highs,
                "low": lows,
                "timestamp": pd.date_range(
                    start=datetime.now() - timedelta(hours=1),
                    periods=num_ticks,
                    freq="100ms",
                ),
            }
        )

        return tick_data

    def _calculate_market_impact(self, tick_data: pd.DataFrame) -> float:
        """Calculate market impact of trades."""
        try:
            # Simplified market impact calculation
            # Real implementation would use trade direction and size
            if "volume" in tick_data.columns:
                volume_weighted_price_change = (
                    tick_data["price"].pct_change().abs() * tick_data["volume"]
                ).sum() / tick_data["volume"].sum()

                return min(0.01, volume_weighted_price_change * 100)  # Cap at 1%
            else:
                return 0.001  # Default estimate

        except Exception:
            return 0.001

    def _calculate_price_efficiency(self, tick_data: pd.DataFrame) -> float:
        """Calculate price efficiency using variance ratio test."""
        try:
            returns = tick_data["price"].pct_change().dropna()

            if len(returns) < 50:
                return 0.5  # Default

            # Variance ratio test for random walk
            variance_1 = returns.var()
            variance_5 = returns.rolling(5).sum().var() / 5

            variance_ratio = variance_5 / variance_1 if variance_1 > 0 else 1

            # Closer to 1 means more efficient (random walk)
            efficiency = 1 - abs(variance_ratio - 1)
            return max(0, min(1, efficiency))

        except Exception:
            return 0.5

    def _calculate_order_flow_imbalance(self, tick_data: pd.DataFrame) -> float:
        """Calculate order flow imbalance."""
        try:
            if "volume" not in tick_data.columns:
                return 0

            # Classify trades as buy/sell based on price changes
            price_changes = tick_data["price"].diff()

            buy_volume = tick_data.loc[price_changes > 0, "volume"].sum()
            sell_volume = tick_data.loc[price_changes < 0, "volume"].sum()

            total_volume = buy_volume + sell_volume

            if total_volume == 0:
                return 0

            imbalance = (buy_volume - sell_volume) / total_volume
            return imbalance

        except Exception:
            return 0

    def _calculate_volatility_clustering(self, tick_data: pd.DataFrame) -> float:
        """Calculate volatility clustering (GARCH effect)."""
        try:
            returns = tick_data["price"].pct_change().dropna()

            if len(returns) < 20:
                return 0.5

            # Calculate rolling volatility
            rolling_vol = returns.rolling(10).std()

            # Check for volatility clustering using autocorrelation
            vol_autocorr = rolling_vol.autocorr(lag=1)

            # Higher autocorrelation indicates more clustering
            clustering = (
                max(0, min(1, vol_autocorr)) if not np.isnan(vol_autocorr) else 0.5
            )
            return clustering

        except Exception:
            return 0.5

    def _calculate_liquidity_score(
        self, tick_data: pd.DataFrame, bid_ask_spread: float
    ) -> float:
        """Calculate overall liquidity score."""
        try:
            # Combine multiple liquidity measures
            spread_score = max(
                0, 1 - bid_ask_spread * 1000
            )  # Lower spread = higher score

            if "volume" in tick_data.columns:
                volume_score = min(
                    1, tick_data["volume"].mean() / 10000
                )  # Higher volume = higher score
            else:
                volume_score = 0.5

            # Price impact score (lower impact = higher score)
            market_impact = self._calculate_market_impact(tick_data)
            impact_score = max(0, 1 - market_impact * 1000)

            # Weighted average
            liquidity_score = (
                spread_score * 0.4 + volume_score * 0.4 + impact_score * 0.2
            )
            return max(0, min(1, liquidity_score))

        except Exception:
            return 0.5

    async def _store_microstructure_metrics(self, metrics: MarketMicrostructureMetrics):
        """Store microstructure metrics in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO microstructure_metrics
                (symbol, timestamp, bid_ask_spread, market_impact, price_efficiency,
                 order_flow_imbalance, volatility_clustering, liquidity_score,
                 transaction_costs, market_fragmentation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metrics.symbol,
                    metrics.timestamp.isoformat(),
                    metrics.bid_ask_spread,
                    metrics.market_impact,
                    metrics.price_efficiency,
                    metrics.order_flow_imbalance,
                    metrics.volatility_clustering,
                    metrics.liquidity_score,
                    metrics.transaction_costs,
                    metrics.market_fragmentation,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing microstructure metrics: {e}")


# Example usage and testing
async def main():
    """Example usage of the advanced analytics suite."""

    # Test Insider Activity Analyzer
    print("Testing Insider Activity Analyzer...")
    insider_analyzer = InsiderActivityAnalyzer()

    symbol = "AAPL"
    transactions = await insider_analyzer.fetch_insider_data(symbol)
    print(f"Fetched {len(transactions)} insider transactions")

    insider_sentiment = await insider_analyzer.analyze_insider_sentiment(
        symbol, transactions
    )
    print(f"Insider sentiment: {insider_sentiment}")

    # Test Alternative Data Integrator
    print("\nTesting Alternative Data Integrator...")
    alt_data_integrator = AlternativeDataIntegrator()

    satellite_data = await alt_data_integrator.collect_satellite_data(symbol)
    social_data = await alt_data_integrator.collect_social_media_sentiment(symbol)
    economic_data = await alt_data_integrator.collect_economic_indicators(symbol)

    print(f"Collected {len(satellite_data)} satellite data points")
    print(f"Collected {len(social_data)} social media data points")
    print(f"Collected {len(economic_data)} economic data points")

    # Test Quantitative Analyzer
    print("\nTesting Quantitative Analyzer...")
    quant_analyzer = QuantitativeAnalyzer()

    # Get sample price data
    ticker = yf.Ticker(symbol)
    price_data = ticker.history(period="6mo")

    momentum_signal = await quant_analyzer.momentum_strategy(symbol, price_data)
    mean_reversion_signal = await quant_analyzer.mean_reversion_strategy(
        symbol, price_data
    )

    print(f"Momentum signal: {momentum_signal}")
    print(f"Mean reversion signal: {mean_reversion_signal}")

    # Test Market Microstructure Analyzer
    print("\nTesting Market Microstructure Analyzer...")
    microstructure_analyzer = MarketMicrostructureAnalyzer()

    microstructure_metrics = await microstructure_analyzer.analyze_microstructure(
        symbol
    )
    print(f"Microstructure metrics: {microstructure_metrics}")


if __name__ == "__main__":
    asyncio.run(main())
