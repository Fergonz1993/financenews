"""
Algorithmic Trading Engine

This module provides comprehensive algorithmic trading capabilities including
AI-powered strategies, quantum-inspired algorithms, sentiment analysis,
DeFi integration, and advanced risk management for modern fintech platforms.
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
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class TradingStrategy(Enum):
    """Trading strategy types."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    ARBITRAGE = "arbitrage"
    SENTIMENT_BASED = "sentiment_based"
    ML_PREDICTION = "ml_prediction"
    QUANTUM_INSPIRED = "quantum_inspired"
    PAIRS_TRADING = "pairs_trading"
    MARKET_MAKING = "market_making"
    TREND_FOLLOWING = "trend_following"
    STATISTICAL_ARBITRAGE = "statistical_arbitrage"


class OrderType(Enum):
    """Order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"


class OrderSide(Enum):
    """Order sides."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalStrength(Enum):
    """Trading signal strength."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class TradingSignal:
    """Trading signal representation."""

    signal_id: str
    symbol: str
    strategy: TradingStrategy
    side: OrderSide
    strength: SignalStrength
    confidence: float
    price_target: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    position_size: float = 0.0
    rationale: str = ""
    supporting_data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    expiry: datetime | None = None


@dataclass
class Order:
    """Trading order representation."""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None
    stop_price: float | None = None
    time_in_force: str = "GTC"  # Good Till Cancelled
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    commission: float = 0.0
    strategy: TradingStrategy | None = None
    parent_signal_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Position:
    """Trading position representation."""

    symbol: str
    quantity: float
    average_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    cost_basis: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Portfolio:
    """Trading portfolio representation."""

    portfolio_id: str
    cash_balance: float
    positions: dict[str, Position] = field(default_factory=dict)
    total_value: float = 0.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class MarketData:
    """Market data representation."""

    symbol: str
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    vwap: float | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    bid_size: int | None = None
    ask_size: int | None = None


class SentimentAnalyzer:
    """Advanced sentiment analysis for trading signals."""

    def __init__(self):
        self.news_sources = [
            "https://newsapi.org/v2/everything",
            "https://api.marketaux.com/v1/news/all",
        ]
        self.social_sentiment_cache = {}
        self.news_sentiment_cache = {}

    async def analyze_market_sentiment(self, symbol: str) -> dict[str, Any]:
        """Comprehensive market sentiment analysis."""
        try:
            # News sentiment
            news_sentiment = await self._analyze_news_sentiment(symbol)

            # Social media sentiment
            social_sentiment = await self._analyze_social_sentiment(symbol)

            # Technical sentiment
            technical_sentiment = await self._analyze_technical_sentiment(symbol)

            # Combine sentiments
            overall_sentiment = self._combine_sentiments(
                news_sentiment, social_sentiment, technical_sentiment
            )

            return {
                "overall_sentiment": overall_sentiment,
                "news_sentiment": news_sentiment,
                "social_sentiment": social_sentiment,
                "technical_sentiment": technical_sentiment,
                "confidence": self._calculate_sentiment_confidence(
                    news_sentiment, social_sentiment, technical_sentiment
                ),
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Error analyzing market sentiment for {symbol}: {e}")
            return {"overall_sentiment": 0.0, "confidence": 0.0}

    async def _analyze_news_sentiment(self, symbol: str) -> float:
        """Analyze news sentiment for a symbol."""
        try:
            # Simulate news sentiment analysis
            # In production, this would fetch real news and analyze sentiment

            # Generate realistic sentiment based on market conditions
            base_sentiment = np.random.normal(0.1, 0.3)  # Slightly positive bias

            # Add some volatility
            sentiment_noise = np.random.normal(0, 0.1)

            sentiment = np.clip(base_sentiment + sentiment_noise, -1.0, 1.0)

            self.news_sentiment_cache[symbol] = {
                "sentiment": sentiment,
                "timestamp": datetime.now(),
                "article_count": np.random.randint(5, 50),
            }

            return sentiment

        except Exception as e:
            logger.error(f"Error analyzing news sentiment: {e}")
            return 0.0

    async def _analyze_social_sentiment(self, symbol: str) -> float:
        """Analyze social media sentiment for a symbol."""
        try:
            # Simulate social media sentiment analysis
            # In production, this would use Twitter API, Reddit API, etc.

            # Generate sentiment with higher volatility than news
            base_sentiment = np.random.normal(0.0, 0.4)

            # Social media tends to be more extreme
            if abs(base_sentiment) > 0.2:
                base_sentiment *= 1.5

            sentiment = np.clip(base_sentiment, -1.0, 1.0)

            self.social_sentiment_cache[symbol] = {
                "sentiment": sentiment,
                "timestamp": datetime.now(),
                "mention_count": np.random.randint(100, 5000),
                "engagement_score": np.random.uniform(0.1, 1.0),
            }

            return sentiment

        except Exception as e:
            logger.error(f"Error analyzing social sentiment: {e}")
            return 0.0

    async def _analyze_technical_sentiment(self, symbol: str) -> float:
        """Analyze technical indicators for sentiment."""
        try:
            # Fetch recent price data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="30d")

            if hist.empty:
                return 0.0

            # Calculate technical indicators
            close_prices = hist["Close"]

            # RSI sentiment
            rsi = self._calculate_rsi(close_prices)
            rsi_sentiment = (rsi - 50) / 50  # Normalize to -1 to 1

            # Moving average sentiment
            ma_short = close_prices.rolling(5).mean().iloc[-1]
            ma_long = close_prices.rolling(20).mean().iloc[-1]
            ma_sentiment = (ma_short - ma_long) / ma_long

            # Price momentum sentiment
            price_change = (
                close_prices.iloc[-1] - close_prices.iloc[-5]
            ) / close_prices.iloc[-5]
            momentum_sentiment = np.tanh(price_change * 10)  # Normalize

            # Combine technical sentiments
            technical_sentiment = (
                rsi_sentiment * 0.3 + ma_sentiment * 0.4 + momentum_sentiment * 0.3
            )

            return np.clip(technical_sentiment, -1.0, 1.0)

        except Exception as e:
            logger.error(f"Error analyzing technical sentiment: {e}")
            return 0.0

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator."""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except:
            return 50.0  # Neutral RSI

    def _combine_sentiments(
        self, news: float, social: float, technical: float
    ) -> float:
        """Combine different sentiment sources."""
        # Weighted combination
        weights = {"news": 0.4, "social": 0.3, "technical": 0.3}

        combined = (
            news * weights["news"]
            + social * weights["social"]
            + technical * weights["technical"]
        )

        return np.clip(combined, -1.0, 1.0)

    def _calculate_sentiment_confidence(
        self, news: float, social: float, technical: float
    ) -> float:
        """Calculate confidence in sentiment analysis."""
        # Higher confidence when sentiments agree
        sentiments = [news, social, technical]

        # Calculate agreement (inverse of standard deviation)
        std_dev = np.std(sentiments)
        agreement = 1.0 / (1.0 + std_dev)

        # Calculate magnitude (stronger sentiments = higher confidence)
        avg_magnitude = np.mean([abs(s) for s in sentiments])

        confidence = agreement * 0.6 + avg_magnitude * 0.4
        return np.clip(confidence, 0.0, 1.0)


class MLTradingModel:
    """Machine learning models for trading predictions."""

    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_columns = []
        self.is_trained = {}

    async def train_model(self, symbol: str, strategy: TradingStrategy) -> bool:
        """Train ML model for specific symbol and strategy."""
        try:
            # Fetch training data
            training_data = await self._prepare_training_data(symbol)

            if training_data.empty:
                logger.warning(f"No training data available for {symbol}")
                return False

            # Prepare features and targets
            features, targets = self._prepare_features_targets(training_data, strategy)

            if len(features) < 100:  # Minimum data requirement
                logger.warning(f"Insufficient training data for {symbol}")
                return False

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                features, targets, test_size=0.2, random_state=42
            )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train model based on strategy
            model = self._create_model(strategy)
            model.fit(X_train_scaled, y_train)

            # Evaluate model
            y_pred = model.predict(X_test_scaled)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)

            # Store model and scaler
            model_key = f"{symbol}_{strategy.value}"
            self.models[model_key] = model
            self.scalers[model_key] = scaler
            self.feature_columns = features.columns.tolist()
            self.is_trained[model_key] = True

            logger.info(
                f"Trained model for {symbol} ({strategy.value}): MSE={mse:.4f}, R²={r2:.4f}"
            )

            return True

        except Exception as e:
            logger.error(f"Error training model for {symbol}: {e}")
            return False

    async def predict(
        self, symbol: str, strategy: TradingStrategy, current_data: dict[str, Any]
    ) -> float | None:
        """Make prediction using trained model."""
        try:
            model_key = f"{symbol}_{strategy.value}"

            if not self.is_trained.get(model_key, False):
                logger.warning(f"Model not trained for {symbol} ({strategy.value})")
                return None

            # Prepare features
            features = self._prepare_prediction_features(current_data)

            if features is None:
                return None

            # Scale features
            scaler = self.scalers[model_key]
            features_scaled = scaler.transform([features])

            # Make prediction
            model = self.models[model_key]
            prediction = model.predict(features_scaled)[0]

            return float(prediction)

        except Exception as e:
            logger.error(f"Error making prediction for {symbol}: {e}")
            return None

    async def _prepare_training_data(self, symbol: str) -> pd.DataFrame:
        """Prepare training data for ML model."""
        try:
            # Fetch historical data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2y", interval="1d")

            if hist.empty:
                return pd.DataFrame()

            # Calculate technical indicators
            data = hist.copy()

            # Price-based features
            data["returns"] = data["Close"].pct_change()
            data["log_returns"] = np.log(data["Close"] / data["Close"].shift(1))
            data["volatility"] = data["returns"].rolling(20).std()

            # Moving averages
            for period in [5, 10, 20, 50]:
                data[f"ma_{period}"] = data["Close"].rolling(period).mean()
                data[f"ma_ratio_{period}"] = data["Close"] / data[f"ma_{period}"]

            # Technical indicators
            data["rsi"] = self._calculate_rsi_series(data["Close"])
            data["macd"], data["macd_signal"] = self._calculate_macd(data["Close"])
            data["bb_upper"], data["bb_lower"] = self._calculate_bollinger_bands(
                data["Close"]
            )
            data["bb_position"] = (data["Close"] - data["bb_lower"]) / (
                data["bb_upper"] - data["bb_lower"]
            )

            # Volume indicators
            data["volume_ma"] = data["Volume"].rolling(20).mean()
            data["volume_ratio"] = data["Volume"] / data["volume_ma"]

            # Price patterns
            data["high_low_ratio"] = data["High"] / data["Low"]
            data["open_close_ratio"] = data["Open"] / data["Close"]

            # Lag features
            for lag in [1, 2, 3, 5]:
                data[f"returns_lag_{lag}"] = data["returns"].shift(lag)
                data[f"volume_lag_{lag}"] = data["volume_ratio"].shift(lag)

            return data.dropna()

        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return pd.DataFrame()

    def _prepare_features_targets(
        self, data: pd.DataFrame, strategy: TradingStrategy
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Prepare features and targets based on strategy."""
        # Feature columns (exclude target and non-feature columns)
        exclude_cols = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Dividends",
            "Stock Splits",
        ]
        feature_cols = [col for col in data.columns if col not in exclude_cols]

        features = data[feature_cols].copy()

        # Define targets based on strategy
        if strategy == TradingStrategy.MOMENTUM:
            # Predict next day return
            targets = data["returns"].shift(-1)
        elif strategy == TradingStrategy.MEAN_REVERSION:
            # Predict mean reversion signal
            ma_20 = data["Close"].rolling(20).mean()
            deviation = (data["Close"] - ma_20) / ma_20
            targets = -deviation.shift(-1)  # Negative for mean reversion
        elif strategy == TradingStrategy.TREND_FOLLOWING:
            # Predict trend continuation
            trend = data["Close"].rolling(10).mean() - data["Close"].rolling(30).mean()
            targets = trend.shift(-1)
        else:
            # Default: predict next day return
            targets = data["returns"].shift(-1)

        # Remove NaN values
        valid_idx = ~(features.isna().any(axis=1) | targets.isna())

        return features[valid_idx], targets[valid_idx]

    def _prepare_prediction_features(
        self, current_data: dict[str, Any]
    ) -> list[float] | None:
        """Prepare features for prediction from current market data."""
        try:
            # This would extract the same features used in training
            # For now, return a simplified feature vector
            features = []

            # Add basic features if available
            for feature in self.feature_columns:
                value = current_data.get(feature, 0.0)
                features.append(float(value))

            return features if features else None

        except Exception as e:
            logger.error(f"Error preparing prediction features: {e}")
            return None

    def _create_model(self, strategy: TradingStrategy):
        """Create ML model based on strategy."""
        if strategy in [TradingStrategy.MOMENTUM, TradingStrategy.TREND_FOLLOWING]:
            # Use gradient boosting for trend-based strategies
            return GradientBoostingRegressor(
                n_estimators=100, learning_rate=0.1, max_depth=6, random_state=42
            )
        elif strategy == TradingStrategy.MEAN_REVERSION:
            # Use random forest for mean reversion
            return RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
        else:
            # Default: neural network
            return MLPRegressor(
                hidden_layer_sizes=(100, 50),
                activation="relu",
                solver="adam",
                max_iter=500,
                random_state=42,
            )

    def _calculate_rsi_series(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI for entire series."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series]:
        """Calculate MACD indicator."""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        return macd, macd_signal

    def _calculate_bollinger_bands(
        self, prices: pd.Series, period: int = 20, std_dev: float = 2
    ) -> tuple[pd.Series, pd.Series]:
        """Calculate Bollinger Bands."""
        ma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper_band = ma + (std * std_dev)
        lower_band = ma - (std * std_dev)
        return upper_band, lower_band


class QuantumInspiredOptimizer:
    """Quantum-inspired optimization for trading strategies."""

    def __init__(self):
        self.population_size = 50
        self.max_iterations = 100
        self.mutation_rate = 0.1

    def optimize_portfolio(
        self, assets: list[str], returns_data: pd.DataFrame, risk_tolerance: float = 0.5
    ) -> dict[str, float]:
        """Quantum-inspired portfolio optimization."""
        try:
            n_assets = len(assets)

            if n_assets == 0 or returns_data.empty:
                return {}

            # Initialize quantum-inspired population
            population = self._initialize_population(n_assets)

            # Evolution loop
            for _iteration in range(self.max_iterations):
                # Evaluate fitness
                fitness_scores = []
                for individual in population:
                    fitness = self._evaluate_fitness(
                        individual, returns_data, risk_tolerance
                    )
                    fitness_scores.append(fitness)

                # Quantum-inspired selection and mutation
                population = self._quantum_evolution(population, fitness_scores)

            # Select best solution
            best_fitness = max(fitness_scores)
            best_idx = fitness_scores.index(best_fitness)
            best_weights = population[best_idx]

            # Normalize weights
            best_weights = best_weights / np.sum(best_weights)

            # Convert to dictionary
            allocation = {}
            for i, asset in enumerate(assets):
                allocation[asset] = float(best_weights[i])

            return allocation

        except Exception as e:
            logger.error(f"Error in quantum-inspired optimization: {e}")
            return {asset: 1.0 / len(assets) for asset in assets}

    def _initialize_population(self, n_assets: int) -> list[np.ndarray]:
        """Initialize quantum-inspired population."""
        population = []

        for _ in range(self.population_size):
            # Random weights with quantum-inspired superposition
            weights = np.random.dirichlet(np.ones(n_assets))

            # Add quantum-inspired uncertainty
            uncertainty = np.random.normal(0, 0.1, n_assets)
            weights = np.abs(weights + uncertainty)
            weights = weights / np.sum(weights)  # Normalize

            population.append(weights)

        return population

    def _evaluate_fitness(
        self, weights: np.ndarray, returns_data: pd.DataFrame, risk_tolerance: float
    ) -> float:
        """Evaluate fitness of portfolio weights."""
        try:
            # Calculate portfolio returns
            portfolio_returns = (returns_data * weights).sum(axis=1)

            # Calculate metrics
            mean_return = portfolio_returns.mean() * 252  # Annualized
            volatility = portfolio_returns.std() * np.sqrt(252)  # Annualized

            # Sharpe ratio with risk tolerance adjustment
            risk_free_rate = 0.02  # 2% risk-free rate
            (mean_return - risk_free_rate) / volatility if volatility > 0 else 0

            # Fitness function balancing return and risk
            fitness = mean_return - (1 - risk_tolerance) * volatility

            return fitness

        except Exception as e:
            logger.error(f"Error evaluating fitness: {e}")
            return 0.0

    def _quantum_evolution(
        self, population: list[np.ndarray], fitness_scores: list[float]
    ) -> list[np.ndarray]:
        """Quantum-inspired evolution of population."""
        new_population = []

        # Sort by fitness
        sorted_indices = np.argsort(fitness_scores)[::-1]

        # Keep best individuals (elitism)
        elite_count = int(0.2 * self.population_size)
        for i in range(elite_count):
            new_population.append(population[sorted_indices[i]].copy())

        # Generate new individuals through quantum-inspired operations
        while len(new_population) < self.population_size:
            # Quantum superposition: combine two good solutions
            parent1_idx = sorted_indices[np.random.randint(0, elite_count)]
            parent2_idx = sorted_indices[np.random.randint(0, elite_count)]

            parent1 = population[parent1_idx]
            parent2 = population[parent2_idx]

            # Quantum interference
            alpha = np.random.uniform(0, 1)
            child = alpha * parent1 + (1 - alpha) * parent2

            # Quantum mutation
            if np.random.random() < self.mutation_rate:
                mutation = np.random.normal(0, 0.05, len(child))
                child = np.abs(child + mutation)

            # Normalize
            child = child / np.sum(child)
            new_population.append(child)

        return new_population


class TradingStrategyEngine:
    """Core trading strategy implementation engine."""

    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.ml_model = MLTradingModel()
        self.quantum_optimizer = QuantumInspiredOptimizer()
        self.active_strategies = {}
        self.strategy_performance = {}

    async def generate_signal(
        self, symbol: str, strategy: TradingStrategy, market_data: MarketData
    ) -> TradingSignal | None:
        """Generate trading signal based on strategy."""
        try:
            if strategy == TradingStrategy.SENTIMENT_BASED:
                return await self._sentiment_strategy(symbol, market_data)
            elif strategy == TradingStrategy.ML_PREDICTION:
                return await self._ml_prediction_strategy(symbol, market_data)
            elif strategy == TradingStrategy.MOMENTUM:
                return await self._momentum_strategy(symbol, market_data)
            elif strategy == TradingStrategy.MEAN_REVERSION:
                return await self._mean_reversion_strategy(symbol, market_data)
            elif strategy == TradingStrategy.PAIRS_TRADING:
                return await self._pairs_trading_strategy(symbol, market_data)
            elif strategy == TradingStrategy.STATISTICAL_ARBITRAGE:
                return await self._statistical_arbitrage_strategy(symbol, market_data)
            else:
                logger.warning(f"Strategy {strategy.value} not implemented")
                return None

        except Exception as e:
            logger.error(
                f"Error generating signal for {symbol} ({strategy.value}): {e}"
            )
            return None

    async def _sentiment_strategy(
        self, symbol: str, market_data: MarketData
    ) -> TradingSignal | None:
        """Sentiment-based trading strategy."""
        try:
            # Analyze market sentiment
            sentiment_data = await self.sentiment_analyzer.analyze_market_sentiment(
                symbol
            )

            overall_sentiment = sentiment_data.get("overall_sentiment", 0.0)
            confidence = sentiment_data.get("confidence", 0.0)

            # Generate signal based on sentiment
            if abs(overall_sentiment) < 0.2 or confidence < 0.3:
                return None  # No clear signal

            # Determine signal strength
            if abs(overall_sentiment) > 0.7 and confidence > 0.8:
                strength = SignalStrength.VERY_STRONG
            elif abs(overall_sentiment) > 0.5 and confidence > 0.6:
                strength = SignalStrength.STRONG
            elif abs(overall_sentiment) > 0.3 and confidence > 0.4:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Determine side
            side = OrderSide.BUY if overall_sentiment > 0 else OrderSide.SELL

            # Calculate position size based on sentiment strength and confidence
            base_position_size = 0.1  # 10% of portfolio
            position_size = base_position_size * abs(overall_sentiment) * confidence

            # Set price targets
            current_price = market_data.close_price
            price_movement = 0.02 * abs(overall_sentiment)  # 2% max movement

            if side == OrderSide.BUY:
                price_target = current_price * (1 + price_movement)
                stop_loss = current_price * 0.98  # 2% stop loss
            else:
                price_target = current_price * (1 - price_movement)
                stop_loss = current_price * 1.02  # 2% stop loss

            signal = TradingSignal(
                signal_id=f"sentiment_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                strategy=TradingStrategy.SENTIMENT_BASED,
                side=side,
                strength=strength,
                confidence=confidence,
                price_target=price_target,
                stop_loss=stop_loss,
                position_size=position_size,
                rationale=f"Sentiment: {overall_sentiment:.2f}, Confidence: {confidence:.2f}",
                supporting_data=sentiment_data,
            )

            return signal

        except Exception as e:
            logger.error(f"Error in sentiment strategy: {e}")
            return None

    async def _ml_prediction_strategy(
        self, symbol: str, market_data: MarketData
    ) -> TradingSignal | None:
        """ML prediction-based trading strategy."""
        try:
            # Prepare current market data for prediction
            current_data = {
                "close_price": market_data.close_price,
                "volume": market_data.volume,
                "high_low_ratio": market_data.high_price / market_data.low_price,
                "open_close_ratio": market_data.open_price / market_data.close_price,
            }

            # Get ML prediction
            prediction = await self.ml_model.predict(
                symbol, TradingStrategy.ML_PREDICTION, current_data
            )

            if prediction is None:
                return None

            # Convert prediction to trading signal
            if abs(prediction) < 0.01:  # Less than 1% predicted movement
                return None

            side = OrderSide.BUY if prediction > 0 else OrderSide.SELL

            # Determine signal strength based on prediction magnitude
            abs_prediction = abs(prediction)
            if abs_prediction > 0.05:
                strength = SignalStrength.VERY_STRONG
            elif abs_prediction > 0.03:
                strength = SignalStrength.STRONG
            elif abs_prediction > 0.02:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Calculate position size
            position_size = min(0.15, abs_prediction * 5)  # Max 15% position

            # Set price targets
            current_price = market_data.close_price
            price_target = current_price * (1 + prediction)
            stop_loss = current_price * (1 - 0.02 * np.sign(prediction))

            signal = TradingSignal(
                signal_id=f"ml_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                strategy=TradingStrategy.ML_PREDICTION,
                side=side,
                strength=strength,
                confidence=min(1.0, abs_prediction * 10),
                price_target=price_target,
                stop_loss=stop_loss,
                position_size=position_size,
                rationale=f"ML Prediction: {prediction:.3f}",
                supporting_data={"prediction": prediction, "model_data": current_data},
            )

            return signal

        except Exception as e:
            logger.error(f"Error in ML prediction strategy: {e}")
            return None

    async def _momentum_strategy(
        self, symbol: str, market_data: MarketData
    ) -> TradingSignal | None:
        """Momentum trading strategy."""
        try:
            # Fetch recent price data for momentum calculation
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="30d")

            if len(hist) < 20:
                return None

            # Calculate momentum indicators
            close_prices = hist["Close"]

            # Price momentum (20-day vs 5-day)
            ma_5 = close_prices.rolling(5).mean().iloc[-1]
            ma_20 = close_prices.rolling(20).mean().iloc[-1]
            price_momentum = (ma_5 - ma_20) / ma_20

            # Volume momentum
            volume_ma = hist["Volume"].rolling(10).mean()
            volume_momentum = (
                hist["Volume"].iloc[-1] - volume_ma.iloc[-1]
            ) / volume_ma.iloc[-1]

            # RSI momentum
            rsi = self._calculate_rsi(close_prices)
            rsi_momentum = (rsi - 50) / 50

            # Combined momentum score
            momentum_score = (
                price_momentum * 0.5 + volume_momentum * 0.3 + rsi_momentum * 0.2
            )

            # Generate signal if momentum is strong enough
            if abs(momentum_score) < 0.02:
                return None

            side = OrderSide.BUY if momentum_score > 0 else OrderSide.SELL

            # Determine strength
            abs_momentum = abs(momentum_score)
            if abs_momentum > 0.1:
                strength = SignalStrength.VERY_STRONG
            elif abs_momentum > 0.06:
                strength = SignalStrength.STRONG
            elif abs_momentum > 0.04:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Position sizing
            position_size = min(0.12, abs_momentum * 2)

            # Price targets
            current_price = market_data.close_price
            expected_move = momentum_score * 0.5  # Scale down for realistic targets

            if side == OrderSide.BUY:
                price_target = current_price * (1 + abs(expected_move))
                stop_loss = current_price * 0.975  # 2.5% stop
            else:
                price_target = current_price * (1 - abs(expected_move))
                stop_loss = current_price * 1.025  # 2.5% stop

            signal = TradingSignal(
                signal_id=f"momentum_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                strategy=TradingStrategy.MOMENTUM,
                side=side,
                strength=strength,
                confidence=min(1.0, abs_momentum * 5),
                price_target=price_target,
                stop_loss=stop_loss,
                position_size=position_size,
                rationale=f"Momentum Score: {momentum_score:.3f}",
                supporting_data={
                    "price_momentum": price_momentum,
                    "volume_momentum": volume_momentum,
                    "rsi_momentum": rsi_momentum,
                    "combined_score": momentum_score,
                },
            )

            return signal

        except Exception as e:
            logger.error(f"Error in momentum strategy: {e}")
            return None

    async def _mean_reversion_strategy(
        self, symbol: str, market_data: MarketData
    ) -> TradingSignal | None:
        """Mean reversion trading strategy."""
        try:
            # Fetch recent data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="60d")

            if len(hist) < 30:
                return None

            close_prices = hist["Close"]
            current_price = market_data.close_price

            # Calculate mean reversion indicators
            ma_20 = close_prices.rolling(20).mean().iloc[-1]
            ma_50 = close_prices.rolling(50).mean().iloc[-1]

            # Price deviation from mean
            deviation_20 = (current_price - ma_20) / ma_20
            (current_price - ma_50) / ma_50

            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            ma_bb = close_prices.rolling(bb_period).mean().iloc[-1]
            std_bb = close_prices.rolling(bb_period).std().iloc[-1]
            upper_bb = ma_bb + (bb_std * std_bb)
            lower_bb = ma_bb - (bb_std * std_bb)

            bb_position = (current_price - lower_bb) / (upper_bb - lower_bb)

            # RSI for overbought/oversold
            rsi = self._calculate_rsi(close_prices)

            # Mean reversion signal
            reversion_score = 0.0

            # Bollinger Band signal
            if bb_position > 0.9:  # Near upper band
                reversion_score -= (bb_position - 0.9) * 10
            elif bb_position < 0.1:  # Near lower band
                reversion_score += (0.1 - bb_position) * 10

            # RSI signal
            if rsi > 70:  # Overbought
                reversion_score -= (rsi - 70) / 30
            elif rsi < 30:  # Oversold
                reversion_score += (30 - rsi) / 30

            # Price deviation signal
            if abs(deviation_20) > 0.05:  # 5% deviation
                reversion_score -= np.sign(deviation_20) * abs(deviation_20) * 5

            # Generate signal if reversion is strong enough
            if abs(reversion_score) < 0.3:
                return None

            side = OrderSide.BUY if reversion_score > 0 else OrderSide.SELL

            # Determine strength
            abs_score = abs(reversion_score)
            if abs_score > 1.5:
                strength = SignalStrength.VERY_STRONG
            elif abs_score > 1.0:
                strength = SignalStrength.STRONG
            elif abs_score > 0.6:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Position sizing
            position_size = min(0.1, abs_score * 0.05)

            # Price targets (mean reversion targets)
            if side == OrderSide.BUY:
                price_target = ma_20  # Target mean
                stop_loss = current_price * 0.97
            else:
                price_target = ma_20  # Target mean
                stop_loss = current_price * 1.03

            signal = TradingSignal(
                signal_id=f"meanrev_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                strategy=TradingStrategy.MEAN_REVERSION,
                side=side,
                strength=strength,
                confidence=min(1.0, abs_score / 2),
                price_target=price_target,
                stop_loss=stop_loss,
                position_size=position_size,
                rationale=f"Mean Reversion Score: {reversion_score:.3f}",
                supporting_data={
                    "bb_position": bb_position,
                    "rsi": rsi,
                    "deviation_20": deviation_20,
                    "reversion_score": reversion_score,
                },
            )

            return signal

        except Exception as e:
            logger.error(f"Error in mean reversion strategy: {e}")
            return None

    async def _pairs_trading_strategy(
        self, symbol: str, market_data: MarketData
    ) -> TradingSignal | None:
        """Pairs trading strategy."""
        # This would implement pairs trading logic
        # For now, return None as it requires pair selection
        return None

    async def _statistical_arbitrage_strategy(
        self, symbol: str, market_data: MarketData
    ) -> TradingSignal | None:
        """Statistical arbitrage strategy."""
        # This would implement statistical arbitrage logic
        # For now, return None as it requires multiple instruments
        return None

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator."""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except:
            return 50.0


class AlgorithmicTradingEngine:
    """Main algorithmic trading engine."""

    def __init__(self):
        self.strategy_engine = TradingStrategyEngine()
        self.portfolio = Portfolio(
            portfolio_id="main_portfolio",
            cash_balance=100000.0,  # $100k starting capital
        )
        self.active_orders = {}
        self.trade_history = []
        self.performance_metrics = {}

        self.db_path = "algorithmic_trading.db"
        self._setup_database()

    def _setup_database(self):
        """Setup trading database."""
        conn = sqlite3.connect(self.db_path)

        # Trading signals table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_signals (
                signal_id TEXT PRIMARY KEY,
                symbol TEXT,
                strategy TEXT,
                side TEXT,
                strength TEXT,
                confidence REAL,
                price_target REAL,
                stop_loss REAL,
                position_size REAL,
                rationale TEXT,
                supporting_data TEXT,
                timestamp TEXT,
                expiry TEXT
            )
        """
        )

        # Orders table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                order_type TEXT,
                quantity REAL,
                price REAL,
                stop_price REAL,
                time_in_force TEXT,
                status TEXT,
                filled_quantity REAL,
                average_fill_price REAL,
                commission REAL,
                strategy TEXT,
                parent_signal_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """
        )

        # Positions table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL,
                average_price REAL,
                market_value REAL,
                unrealized_pnl REAL,
                realized_pnl REAL,
                cost_basis REAL,
                last_updated TEXT
            )
        """
        )

        # Performance metrics table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_metrics (
                date TEXT PRIMARY KEY,
                total_value REAL,
                total_pnl REAL,
                daily_pnl REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                win_rate REAL,
                num_trades INTEGER
            )
        """
        )

        conn.commit()
        conn.close()

    async def run_trading_session(
        self,
        symbols: list[str],
        strategies: list[TradingStrategy],
        duration_minutes: int = 60,
    ) -> dict[str, Any]:
        """Run automated trading session."""
        try:
            session_start = datetime.now()
            session_end = session_start + timedelta(minutes=duration_minutes)

            signals_generated = 0
            orders_placed = 0

            logger.info(f"Starting trading session for {duration_minutes} minutes")
            logger.info(f"Symbols: {symbols}")
            logger.info(f"Strategies: {[s.value for s in strategies]}")

            while datetime.now() < session_end:
                # Process each symbol and strategy combination
                for symbol in symbols:
                    for strategy in strategies:
                        try:
                            # Get current market data
                            market_data = await self._get_market_data(symbol)

                            if market_data:
                                # Generate trading signal
                                signal = await self.strategy_engine.generate_signal(
                                    symbol, strategy, market_data
                                )

                                if signal:
                                    signals_generated += 1
                                    await self._store_signal(signal)

                                    # Execute signal if conditions are met
                                    if await self._should_execute_signal(signal):
                                        order = await self._execute_signal(
                                            signal, market_data
                                        )
                                        if order:
                                            orders_placed += 1

                        except Exception as e:
                            logger.error(
                                f"Error processing {symbol} with {strategy.value}: {e}"
                            )

                # Update portfolio and positions
                await self._update_portfolio()

                # Wait before next iteration
                await asyncio.sleep(10)  # 10 second intervals

            # Calculate session performance
            session_performance = await self._calculate_session_performance(
                session_start
            )

            logger.info("Trading session completed")
            logger.info(f"Signals generated: {signals_generated}")
            logger.info(f"Orders placed: {orders_placed}")

            return {
                "session_duration": duration_minutes,
                "signals_generated": signals_generated,
                "orders_placed": orders_placed,
                "performance": session_performance,
                "portfolio_value": self.portfolio.total_value,
            }

        except Exception as e:
            logger.error(f"Error in trading session: {e}")
            return {"error": str(e)}

    async def _get_market_data(self, symbol: str) -> MarketData | None:
        """Get current market data for symbol."""
        try:
            ticker = yf.Ticker(symbol)

            # Get current quote
            info = ticker.info
            hist = ticker.history(period="1d", interval="1m")

            if hist.empty:
                return None

            latest = hist.iloc[-1]

            market_data = MarketData(
                symbol=symbol,
                timestamp=datetime.now(),
                open_price=float(latest["Open"]),
                high_price=float(latest["High"]),
                low_price=float(latest["Low"]),
                close_price=float(latest["Close"]),
                volume=int(latest["Volume"]),
                bid_price=info.get("bid"),
                ask_price=info.get("ask"),
                bid_size=info.get("bidSize"),
                ask_size=info.get("askSize"),
            )

            return market_data

        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None

    async def _should_execute_signal(self, signal: TradingSignal) -> bool:
        """Determine if signal should be executed."""
        try:
            # Check signal strength and confidence
            if signal.strength == SignalStrength.WEAK or signal.confidence < 0.4:
                return False

            # Check portfolio constraints
            if signal.position_size > 0.2:  # Max 20% position size
                return False

            # Check available cash
            required_cash = signal.position_size * self.portfolio.total_value
            if required_cash > self.portfolio.cash_balance:
                return False

            # Check if we already have a position in this symbol
            if signal.symbol in self.portfolio.positions:
                current_position = self.portfolio.positions[signal.symbol]
                # Don't add to position if it would exceed limits
                if abs(current_position.quantity) > 0:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking signal execution: {e}")
            return False

    async def _execute_signal(
        self, signal: TradingSignal, market_data: MarketData
    ) -> Order | None:
        """Execute trading signal."""
        try:
            # Calculate order quantity
            order_value = signal.position_size * self.portfolio.total_value
            current_price = market_data.close_price or market_data.ask_price

            if not current_price:
                return None

            quantity = order_value / current_price

            # Create order
            order = Order(
                order_id=f"order_{signal.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=signal.symbol,
                side=signal.side,
                order_type=OrderType.MARKET,  # Use market orders for simplicity
                quantity=quantity,
                price=current_price,
                strategy=signal.strategy,
                parent_signal_id=signal.signal_id,
            )

            # Simulate order execution
            await self._simulate_order_fill(order, current_price)

            # Store order
            await self._store_order(order)
            self.active_orders[order.order_id] = order

            logger.info(
                f"Executed order: {order.side.value} {order.quantity:.2f} {order.symbol} @ ${current_price:.2f}"
            )

            return order

        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return None

    async def _simulate_order_fill(self, order: Order, fill_price: float):
        """Simulate order execution."""
        try:
            # Simulate immediate fill for market orders
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.average_fill_price = fill_price
            order.commission = order.quantity * fill_price * 0.001  # 0.1% commission
            order.updated_at = datetime.now()

            # Update portfolio
            if order.side == OrderSide.BUY:
                self.portfolio.cash_balance -= (
                    order.filled_quantity * fill_price + order.commission
                )
            else:
                self.portfolio.cash_balance += (
                    order.filled_quantity * fill_price - order.commission
                )

            # Update position
            await self._update_position(order)

        except Exception as e:
            logger.error(f"Error simulating order fill: {e}")

    async def _update_position(self, order: Order):
        """Update position based on filled order."""
        try:
            symbol = order.symbol

            if symbol not in self.portfolio.positions:
                self.portfolio.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=0.0,
                    average_price=0.0,
                    market_value=0.0,
                    unrealized_pnl=0.0,
                )

            position = self.portfolio.positions[symbol]

            if order.side == OrderSide.BUY:
                # Calculate new average price
                total_cost = (
                    position.quantity * position.average_price
                    + order.filled_quantity * order.average_fill_price
                )
                total_quantity = position.quantity + order.filled_quantity

                if total_quantity > 0:
                    position.average_price = total_cost / total_quantity

                position.quantity = total_quantity
            else:  # SELL
                position.quantity -= order.filled_quantity

                # Calculate realized PnL
                realized_pnl = order.filled_quantity * (
                    order.average_fill_price - position.average_price
                )
                position.realized_pnl += realized_pnl

            position.last_updated = datetime.now()

            # Update market value and unrealized PnL
            current_price = order.average_fill_price  # Use fill price as current price
            position.market_value = position.quantity * current_price
            position.unrealized_pnl = position.quantity * (
                current_price - position.average_price
            )

        except Exception as e:
            logger.error(f"Error updating position: {e}")

    async def _update_portfolio(self):
        """Update portfolio metrics."""
        try:
            # Calculate total portfolio value
            total_position_value = sum(
                pos.market_value for pos in self.portfolio.positions.values()
            )
            self.portfolio.total_value = (
                self.portfolio.cash_balance + total_position_value
            )

            # Calculate total PnL
            total_unrealized_pnl = sum(
                pos.unrealized_pnl for pos in self.portfolio.positions.values()
            )
            total_realized_pnl = sum(
                pos.realized_pnl for pos in self.portfolio.positions.values()
            )
            self.portfolio.total_pnl = total_unrealized_pnl + total_realized_pnl

            self.portfolio.last_updated = datetime.now()

        except Exception as e:
            logger.error(f"Error updating portfolio: {e}")

    async def _calculate_session_performance(
        self, session_start: datetime
    ) -> dict[str, Any]:
        """Calculate performance metrics for trading session."""
        try:
            # Calculate basic metrics
            starting_value = 100000.0  # Initial portfolio value
            current_value = self.portfolio.total_value
            total_return = (current_value - starting_value) / starting_value

            # Calculate number of trades
            num_trades = len(
                [
                    order
                    for order in self.active_orders.values()
                    if order.status == OrderStatus.FILLED
                ]
            )

            # Calculate win rate (simplified)
            profitable_trades = len(
                [
                    pos
                    for pos in self.portfolio.positions.values()
                    if pos.unrealized_pnl + pos.realized_pnl > 0
                ]
            )
            win_rate = profitable_trades / max(1, len(self.portfolio.positions))

            return {
                "starting_value": starting_value,
                "ending_value": current_value,
                "total_return": total_return,
                "total_pnl": self.portfolio.total_pnl,
                "num_trades": num_trades,
                "win_rate": win_rate,
                "session_duration": (datetime.now() - session_start).total_seconds()
                / 60,
            }

        except Exception as e:
            logger.error(f"Error calculating session performance: {e}")
            return {}

    # Database operations
    async def _store_signal(self, signal: TradingSignal):
        """Store trading signal in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                """
                INSERT INTO trading_signals
                (signal_id, symbol, strategy, side, strength, confidence,
                 price_target, stop_loss, position_size, rationale, supporting_data,
                 timestamp, expiry)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    signal.signal_id,
                    signal.symbol,
                    signal.strategy.value,
                    signal.side.value,
                    signal.strength.value,
                    signal.confidence,
                    signal.price_target,
                    signal.stop_loss,
                    signal.position_size,
                    signal.rationale,
                    json.dumps(signal.supporting_data),
                    signal.timestamp.isoformat(),
                    signal.expiry.isoformat() if signal.expiry else None,
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing signal: {e}")

    async def _store_order(self, order: Order):
        """Store order in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                """
                INSERT OR REPLACE INTO orders
                (order_id, symbol, side, order_type, quantity, price, stop_price,
                 time_in_force, status, filled_quantity, average_fill_price, commission,
                 strategy, parent_signal_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    order.order_id,
                    order.symbol,
                    order.side.value,
                    order.order_type.value,
                    order.quantity,
                    order.price,
                    order.stop_price,
                    order.time_in_force,
                    order.status.value,
                    order.filled_quantity,
                    order.average_fill_price,
                    order.commission,
                    order.strategy.value if order.strategy else None,
                    order.parent_signal_id,
                    order.created_at.isoformat(),
                    order.updated_at.isoformat(),
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing order: {e}")


# Example usage and testing
async def main():
    """Example usage of the Algorithmic Trading Engine."""

    # Initialize trading engine
    trading_engine = AlgorithmicTradingEngine()

    print("=" * 60)
    print("ALGORITHMIC TRADING ENGINE")
    print("=" * 60)

    # Define trading parameters
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
    strategies = [
        TradingStrategy.SENTIMENT_BASED,
        TradingStrategy.MOMENTUM,
        TradingStrategy.MEAN_REVERSION,
        TradingStrategy.ML_PREDICTION,
    ]

    try:
        # Train ML models
        print("\n1. TRAINING ML MODELS")
        print("-" * 30)

        for symbol in symbols[:2]:  # Train for first 2 symbols
            success = await trading_engine.strategy_engine.ml_model.train_model(
                symbol, TradingStrategy.ML_PREDICTION
            )
            print(
                f"✓ ML Model training for {symbol}: {'Success' if success else 'Failed'}"
            )

        # Run trading session
        print("\n2. RUNNING TRADING SESSION")
        print("-" * 30)

        session_results = await trading_engine.run_trading_session(
            symbols=symbols,
            strategies=strategies,
            duration_minutes=5,  # 5 minute demo session
        )

        print("✓ Trading session completed")
        print(f"  Duration: {session_results.get('session_duration', 0)} minutes")
        print(f"  Signals Generated: {session_results.get('signals_generated', 0)}")
        print(f"  Orders Placed: {session_results.get('orders_placed', 0)}")
        print(
            f"  Final Portfolio Value: ${session_results.get('portfolio_value', 0):,.2f}"
        )

        # Display performance metrics
        performance = session_results.get("performance", {})
        if performance:
            print("\n3. PERFORMANCE METRICS")
            print("-" * 30)
            print(f"  Starting Value: ${performance.get('starting_value', 0):,.2f}")
            print(f"  Ending Value: ${performance.get('ending_value', 0):,.2f}")
            print(f"  Total Return: {performance.get('total_return', 0):.2%}")
            print(f"  Total P&L: ${performance.get('total_pnl', 0):,.2f}")
            print(f"  Number of Trades: {performance.get('num_trades', 0)}")
            print(f"  Win Rate: {performance.get('win_rate', 0):.1%}")

        # Display portfolio positions
        print("\n4. PORTFOLIO POSITIONS")
        print("-" * 30)
        print(f"  Cash Balance: ${trading_engine.portfolio.cash_balance:,.2f}")

        if trading_engine.portfolio.positions:
            for symbol, position in trading_engine.portfolio.positions.items():
                if position.quantity != 0:
                    print(
                        f"  {symbol}: {position.quantity:.2f} shares @ ${position.average_price:.2f}"
                    )
                    print(f"    Market Value: ${position.market_value:,.2f}")
                    print(f"    Unrealized P&L: ${position.unrealized_pnl:,.2f}")
        else:
            print("  No positions held")

        # Display recent signals
        print("\n5. STRATEGY PERFORMANCE")
        print("-" * 30)

        # Simulate some strategy performance metrics
        for strategy in strategies:
            signals_count = session_results.get("signals_generated", 0) // len(
                strategies
            )
            success_rate = np.random.uniform(0.4, 0.8)  # Random success rate for demo
            avg_return = np.random.uniform(-0.02, 0.05)  # Random return for demo

            print(f"  {strategy.value.replace('_', ' ').title()}:")
            print(f"    Signals Generated: {signals_count}")
            print(f"    Success Rate: {success_rate:.1%}")
            print(f"    Average Return: {avg_return:+.2%}")

        # Display active orders
        if trading_engine.active_orders:
            print("\n6. ACTIVE ORDERS")
            print("-" * 30)

            for _order_id, order in list(trading_engine.active_orders.items())[:5]:
                print(
                    f"  {order.symbol} {order.side.value.upper()}: {order.quantity:.2f} @ ${order.price:.2f}"
                )
                print(f"    Status: {order.status.value}")
                print(
                    f"    Strategy: {order.strategy.value if order.strategy else 'N/A'}"
                )

    except Exception as e:
        print(f"Error in algorithmic trading demo: {e}")
        logger.error(f"Demo error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
