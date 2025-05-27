"""
Portfolio Management & Optimization Module

This module provides comprehensive portfolio management capabilities including portfolio construction,
optimization, risk analysis, performance attribution, and automated rebalancing strategies.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import cvxpy as cp
import numpy as np
import pandas as pd
import scipy.optimize as optimize
import scipy.stats as stats
import yfinance as yf
from sklearn.covariance import LedoitWolf

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class OptimizationObjective(Enum):
    """Portfolio optimization objectives."""

    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"
    BLACK_LITTERMAN = "black_litterman"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    MULTI_OBJECTIVE = "multi_objective"


class RebalancingFrequency(Enum):
    """Portfolio rebalancing frequencies."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUALLY = "semi_annually"
    ANNUALLY = "annually"
    TRIGGER_BASED = "trigger_based"
    ADAPTIVE = "adaptive"


class RiskModel(Enum):
    """Risk model types."""

    HISTORICAL = "historical"
    FACTOR = "factor"
    MONTE_CARLO = "monte_carlo"
    GARCH = "garch"
    SHRINKAGE = "shrinkage"
    ROBUST = "robust"


class PortfolioType(Enum):
    """Types of portfolios."""

    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    MIXED = "mixed"
    ALTERNATIVE = "alternative"
    MULTI_ASSET = "multi_asset"
    SECTOR_ROTATION = "sector_rotation"
    FACTOR_BASED = "factor_based"


@dataclass
class Asset:
    """Individual asset information."""

    symbol: str
    name: str
    asset_type: str
    sector: str
    market_cap: float
    currency: str
    exchange: str
    risk_free_rate: float = 0.02
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """Portfolio position."""

    asset: Asset
    weight: float
    quantity: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    realized_pnl: float
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Portfolio:
    """Portfolio definition."""

    portfolio_id: str
    name: str
    portfolio_type: PortfolioType
    positions: dict[str, Position]
    benchmark: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_value(self) -> float:
        """Calculate total portfolio value."""
        return sum(pos.market_value for pos in self.positions.values())

    @property
    def weights(self) -> dict[str, float]:
        """Get current portfolio weights."""
        total = self.total_value
        return {
            symbol: pos.market_value / total for symbol, pos in self.positions.items()
        }

    @property
    def symbols(self) -> list[str]:
        """Get list of portfolio symbols."""
        return list(self.positions.keys())


@dataclass
class OptimizationConstraints:
    """Portfolio optimization constraints."""

    min_weight: float = 0.0
    max_weight: float = 1.0
    sector_constraints: dict[str, tuple[float, float]] = field(default_factory=dict)
    asset_constraints: dict[str, tuple[float, float]] = field(default_factory=dict)
    turnover_constraint: float | None = None
    tracking_error_constraint: float | None = None
    max_assets: int | None = None
    min_assets: int | None = None
    leverage_constraint: float = 1.0


@dataclass
class PerformanceMetrics:
    """Portfolio performance metrics."""

    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    information_ratio: float
    tracking_error: float
    alpha: float
    beta: float
    var_95: float
    cvar_95: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float


@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""

    portfolio_var: float
    component_var: dict[str, float]
    marginal_var: dict[str, float]
    risk_contribution: dict[str, float]
    correlation_matrix: np.ndarray
    factor_exposures: dict[str, float] = field(default_factory=dict)
    concentration_risk: float = 0.0
    liquidity_risk: float = 0.0


class DataProvider:
    """Financial data provider interface."""

    def __init__(self):
        self.cache = {}
        self.cache_expiry = timedelta(hours=1)

    async def get_price_data(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """Get historical price data for symbols."""
        try:
            cache_key = (
                f"prices_{'-'.join(symbols)}_{start_date}_{end_date}_{frequency}"
            )

            # Check cache
            if cache_key in self.cache:
                cached_time, data = self.cache[cache_key]
                if datetime.now() - cached_time < self.cache_expiry:
                    return data

            # Fetch data
            data = yf.download(
                symbols,
                start=start_date,
                end=end_date,
                interval=frequency,
                progress=False,
            )

            if len(symbols) == 1:
                data.columns = symbols
            else:
                data = data["Adj Close"]

            # Cache data
            self.cache[cache_key] = (datetime.now(), data)

            return data

        except Exception as e:
            logger.error(f"Error fetching price data: {e}")
            return pd.DataFrame()

    async def get_fundamental_data(self, symbols: list[str]) -> dict[str, dict]:
        """Get fundamental data for symbols."""
        fundamental_data = {}

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                fundamental_data[symbol] = {
                    "market_cap": info.get("marketCap", 0),
                    "pe_ratio": info.get("trailingPE", 0),
                    "pb_ratio": info.get("priceToBook", 0),
                    "dividend_yield": info.get("dividendYield", 0),
                    "sector": info.get("sector", "Unknown"),
                    "industry": info.get("industry", "Unknown"),
                    "beta": info.get("beta", 1.0),
                    "revenue_growth": info.get("revenueGrowth", 0),
                    "profit_margin": info.get("profitMargins", 0),
                }

            except Exception as e:
                logger.error(f"Error fetching fundamental data for {symbol}: {e}")
                fundamental_data[symbol] = {}

        return fundamental_data

    async def get_risk_factors(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Get risk factor returns (Fama-French factors simulation)."""
        try:
            # Simulate factor returns for demo
            dates = pd.date_range(start=start_date, end=end_date, freq="D")

            np.random.seed(42)
            factors = pd.DataFrame(
                {
                    "Market": np.random.normal(0.0008, 0.02, len(dates)),
                    "SMB": np.random.normal(
                        0.0002, 0.01, len(dates)
                    ),  # Small minus Big
                    "HML": np.random.normal(0.0001, 0.01, len(dates)),  # High minus Low
                    "RMW": np.random.normal(
                        0.0001, 0.008, len(dates)
                    ),  # Robust minus Weak
                    "CMA": np.random.normal(
                        -0.0001, 0.008, len(dates)
                    ),  # Conservative minus Aggressive
                    "Momentum": np.random.normal(0.0003, 0.015, len(dates)),
                },
                index=dates,
            )

            return factors

        except Exception as e:
            logger.error(f"Error generating risk factors: {e}")
            return pd.DataFrame()


class RiskAnalyzer:
    """Advanced risk analysis for portfolios."""

    def __init__(self, data_provider: DataProvider):
        self.data_provider = data_provider

    async def calculate_portfolio_risk(
        self, portfolio: Portfolio, lookback_days: int = 252
    ) -> RiskMetrics:
        """Calculate comprehensive portfolio risk metrics."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            # Get price data
            price_data = await self.data_provider.get_price_data(
                portfolio.symbols, start_date, end_date
            )

            if price_data.empty:
                raise ValueError("No price data available")

            # Calculate returns
            returns = price_data.pct_change().dropna()

            # Portfolio weights
            weights = np.array(
                [portfolio.weights[symbol] for symbol in portfolio.symbols]
            )

            # Covariance matrix with shrinkage
            cov_estimator = LedoitWolf()
            cov_matrix = cov_estimator.fit(returns).covariance_

            # Portfolio variance
            portfolio_var = np.dot(weights, np.dot(cov_matrix, weights))

            # Component VaR
            component_var = {}
            marginal_var = {}
            risk_contribution = {}

            for i, symbol in enumerate(portfolio.symbols):
                # Marginal VaR
                marginal_var[symbol] = np.dot(cov_matrix[i], weights)

                # Component VaR
                component_var[symbol] = weights[i] * marginal_var[symbol]

                # Risk contribution (%)
                risk_contribution[symbol] = component_var[symbol] / portfolio_var

            # Concentration risk (Herfindahl index)
            concentration_risk = sum(w**2 for w in weights)

            return RiskMetrics(
                portfolio_var=portfolio_var,
                component_var=component_var,
                marginal_var=marginal_var,
                risk_contribution=risk_contribution,
                correlation_matrix=returns.corr().values,
                concentration_risk=concentration_risk,
                liquidity_risk=self._calculate_liquidity_risk(portfolio),
            )

        except Exception as e:
            logger.error(f"Error calculating portfolio risk: {e}")
            raise

    def _calculate_liquidity_risk(self, portfolio: Portfolio) -> float:
        """Calculate portfolio liquidity risk score."""
        # Simplified liquidity risk based on market cap
        total_value = portfolio.total_value
        liquidity_score = 0.0

        for position in portfolio.positions.values():
            weight = position.market_value / total_value
            market_cap = position.asset.market_cap

            # Liquidity penalty based on market cap
            if market_cap > 100e9:  # Large cap
                liquidity_penalty = 0.01
            elif market_cap > 10e9:  # Mid cap
                liquidity_penalty = 0.03
            elif market_cap > 1e9:  # Small cap
                liquidity_penalty = 0.05
            else:  # Micro cap
                liquidity_penalty = 0.10

            liquidity_score += weight * liquidity_penalty

        return liquidity_score

    async def calculate_var_cvar(
        self,
        portfolio: Portfolio,
        confidence_level: float = 0.95,
        holding_period: int = 1,
        method: str = "historical",
    ) -> tuple[float, float]:
        """Calculate Value at Risk and Conditional VaR."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=500)

            # Get price data
            price_data = await self.data_provider.get_price_data(
                portfolio.symbols, start_date, end_date
            )

            # Calculate returns
            returns = price_data.pct_change().dropna()

            # Portfolio weights
            weights = np.array(
                [portfolio.weights[symbol] for symbol in portfolio.symbols]
            )

            # Portfolio returns
            portfolio_returns = returns.dot(weights)

            if method == "historical":
                # Historical VaR
                var = np.percentile(portfolio_returns, (1 - confidence_level) * 100)
                cvar = portfolio_returns[portfolio_returns <= var].mean()

            elif method == "parametric":
                # Parametric VaR (assumes normal distribution)
                mu = portfolio_returns.mean()
                sigma = portfolio_returns.std()
                var = stats.norm.ppf(1 - confidence_level, mu, sigma)
                cvar = mu - sigma * stats.norm.pdf(
                    stats.norm.ppf(1 - confidence_level)
                ) / (1 - confidence_level)

            elif method == "monte_carlo":
                # Monte Carlo VaR
                simulated_returns = self._monte_carlo_simulation(
                    portfolio_returns, n_simulations=10000
                )
                var = np.percentile(simulated_returns, (1 - confidence_level) * 100)
                cvar = simulated_returns[simulated_returns <= var].mean()

            # Scale for holding period
            var *= np.sqrt(holding_period)
            cvar *= np.sqrt(holding_period)

            return abs(var), abs(cvar)

        except Exception as e:
            logger.error(f"Error calculating VaR/CVaR: {e}")
            return 0.0, 0.0

    def _monte_carlo_simulation(
        self, returns: pd.Series, n_simulations: int = 10000
    ) -> np.ndarray:
        """Perform Monte Carlo simulation for returns."""
        mu = returns.mean()
        sigma = returns.std()

        # Generate random returns
        simulated_returns = np.random.normal(mu, sigma, n_simulations)

        return simulated_returns


class PerformanceAnalyzer:
    """Portfolio performance analysis and attribution."""

    def __init__(self, data_provider: DataProvider):
        self.data_provider = data_provider

    async def calculate_performance_metrics(
        self,
        portfolio: Portfolio,
        benchmark_symbol: str = "^GSPC",
        lookback_days: int = 252,
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            # Get portfolio and benchmark data
            symbols = [*portfolio.symbols, benchmark_symbol]
            price_data = await self.data_provider.get_price_data(
                symbols, start_date, end_date
            )

            # Calculate returns
            returns = price_data.pct_change().dropna()

            # Portfolio returns
            weights = np.array(
                [portfolio.weights[symbol] for symbol in portfolio.symbols]
            )
            portfolio_returns = returns[portfolio.symbols].dot(weights)

            # Benchmark returns
            benchmark_returns = returns[benchmark_symbol]

            # Align returns
            common_dates = portfolio_returns.index.intersection(benchmark_returns.index)
            portfolio_returns = portfolio_returns.loc[common_dates]
            benchmark_returns = benchmark_returns.loc[common_dates]

            # Calculate metrics
            total_return = (1 + portfolio_returns).prod() - 1
            annualized_return = (1 + total_return) ** (252 / len(portfolio_returns)) - 1
            volatility = portfolio_returns.std() * np.sqrt(252)

            # Risk-adjusted metrics
            excess_returns = (
                portfolio_returns - 0.02 / 252
            )  # Assuming 2% risk-free rate
            sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252)

            # Sortino ratio
            downside_returns = portfolio_returns[portfolio_returns < 0]
            downside_deviation = downside_returns.std() * np.sqrt(252)
            sortino_ratio = (
                annualized_return / downside_deviation if downside_deviation > 0 else 0
            )

            # Drawdown
            cumulative_returns = (1 + portfolio_returns).cumprod()
            rolling_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - rolling_max) / rolling_max
            max_drawdown = drawdown.min()

            # Calmar ratio
            calmar_ratio = (
                annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
            )

            # Tracking error and information ratio
            active_returns = portfolio_returns - benchmark_returns
            tracking_error = active_returns.std() * np.sqrt(252)
            information_ratio = (
                active_returns.mean() / active_returns.std() * np.sqrt(252)
            )

            # Alpha and beta
            beta = np.cov(portfolio_returns, benchmark_returns)[0, 1] / np.var(
                benchmark_returns
            )
            alpha = annualized_return - (
                0.02 + beta * (benchmark_returns.mean() * 252 - 0.02)
            )

            # VaR
            var_95 = np.percentile(portfolio_returns, 5)
            cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()

            # Win/Loss metrics
            winning_returns = portfolio_returns[portfolio_returns > 0]
            losing_returns = portfolio_returns[portfolio_returns < 0]

            win_rate = len(winning_returns) / len(portfolio_returns)
            avg_win = winning_returns.mean() if len(winning_returns) > 0 else 0
            avg_loss = losing_returns.mean() if len(losing_returns) > 0 else 0
            profit_factor = (
                abs(avg_win * len(winning_returns))
                / abs(avg_loss * len(losing_returns))
                if len(losing_returns) > 0 and avg_loss != 0
                else float("inf")
            )

            return PerformanceMetrics(
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=max_drawdown,
                calmar_ratio=calmar_ratio,
                information_ratio=information_ratio,
                tracking_error=tracking_error,
                alpha=alpha,
                beta=beta,
                var_95=var_95,
                cvar_95=cvar_95,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
            )

        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            raise

    async def performance_attribution(
        self,
        portfolio: Portfolio,
        benchmark_weights: dict[str, float],
        lookback_days: int = 252,
    ) -> dict[str, Any]:
        """Perform Brinson-Fachler performance attribution."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            # Get price data
            price_data = await self.data_provider.get_price_data(
                portfolio.symbols, start_date, end_date
            )

            # Calculate returns
            returns = price_data.pct_change().dropna().mean()

            attribution = {}
            total_allocation_effect = 0
            total_selection_effect = 0
            total_interaction_effect = 0

            # Get sector information
            fundamental_data = await self.data_provider.get_fundamental_data(
                portfolio.symbols
            )

            # Group by sectors
            sectors = {}
            for symbol in portfolio.symbols:
                sector = fundamental_data.get(symbol, {}).get("sector", "Unknown")
                if sector not in sectors:
                    sectors[sector] = []
                sectors[sector].append(symbol)

            benchmark_return = sum(
                benchmark_weights.get(symbol, 0) * returns[symbol]
                for symbol in portfolio.symbols
            )

            for sector, symbols in sectors.items():
                # Portfolio weights in sector
                portfolio_sector_weight = sum(
                    portfolio.weights.get(symbol, 0) for symbol in symbols
                )
                benchmark_sector_weight = sum(
                    benchmark_weights.get(symbol, 0) for symbol in symbols
                )

                # Sector returns
                portfolio_sector_return = (
                    sum(
                        portfolio.weights.get(symbol, 0)
                        * returns[symbol]
                        / portfolio_sector_weight
                        for symbol in symbols
                    )
                    if portfolio_sector_weight > 0
                    else 0
                )

                benchmark_sector_return = (
                    sum(
                        benchmark_weights.get(symbol, 0)
                        * returns[symbol]
                        / benchmark_sector_weight
                        for symbol in symbols
                    )
                    if benchmark_sector_weight > 0
                    else 0
                )

                # Attribution effects
                allocation_effect = (
                    portfolio_sector_weight - benchmark_sector_weight
                ) * (benchmark_sector_return - benchmark_return)

                selection_effect = benchmark_sector_weight * (
                    portfolio_sector_return - benchmark_sector_return
                )

                interaction_effect = (
                    portfolio_sector_weight - benchmark_sector_weight
                ) * (portfolio_sector_return - benchmark_sector_return)

                attribution[sector] = {
                    "allocation_effect": allocation_effect,
                    "selection_effect": selection_effect,
                    "interaction_effect": interaction_effect,
                    "total_effect": allocation_effect
                    + selection_effect
                    + interaction_effect,
                }

                total_allocation_effect += allocation_effect
                total_selection_effect += selection_effect
                total_interaction_effect += interaction_effect

            attribution["total"] = {
                "allocation_effect": total_allocation_effect,
                "selection_effect": total_selection_effect,
                "interaction_effect": total_interaction_effect,
                "total_effect": total_allocation_effect
                + total_selection_effect
                + total_interaction_effect,
            }

            return attribution

        except Exception as e:
            logger.error(f"Error in performance attribution: {e}")
            return {}


class PortfolioOptimizer:
    """Advanced portfolio optimization engine."""

    def __init__(self, data_provider: DataProvider):
        self.data_provider = data_provider

    async def optimize_portfolio(
        self,
        symbols: list[str],
        objective: OptimizationObjective,
        constraints: OptimizationConstraints,
        lookback_days: int = 252,
        **kwargs,
    ) -> dict[str, float]:
        """Optimize portfolio weights based on objective and constraints."""
        try:
            # Get historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            price_data = await self.data_provider.get_price_data(
                symbols, start_date, end_date
            )

            returns = price_data.pct_change().dropna()

            if objective == OptimizationObjective.MAX_SHARPE:
                return await self._max_sharpe_optimization(returns, constraints)
            elif objective == OptimizationObjective.MIN_VARIANCE:
                return await self._min_variance_optimization(returns, constraints)
            elif objective == OptimizationObjective.RISK_PARITY:
                return await self._risk_parity_optimization(returns, constraints)
            elif objective == OptimizationObjective.BLACK_LITTERMAN:
                return await self._black_litterman_optimization(
                    returns, constraints, **kwargs
                )
            elif objective == OptimizationObjective.HIERARCHICAL_RISK_PARITY:
                return await self._hierarchical_risk_parity(returns, constraints)
            elif objective == OptimizationObjective.EQUAL_WEIGHT:
                return {symbol: 1.0 / len(symbols) for symbol in symbols}
            else:
                raise ValueError(f"Unsupported optimization objective: {objective}")

        except Exception as e:
            logger.error(f"Error in portfolio optimization: {e}")
            raise

    async def _max_sharpe_optimization(
        self, returns: pd.DataFrame, constraints: OptimizationConstraints
    ) -> dict[str, float]:
        """Maximize Sharpe ratio optimization."""
        mu = returns.mean() * 252  # Annualized returns
        cov = returns.cov() * 252  # Annualized covariance

        n = len(returns.columns)
        weights = cp.Variable(n)

        # Objective: maximize Sharpe ratio (quadratic approximation)
        portfolio_return = mu.T @ weights
        portfolio_risk = cp.quad_form(weights, cov.values)

        # Constraints
        constraints_list = [
            cp.sum(weights) == 1,  # Weights sum to 1
            weights >= constraints.min_weight,  # Minimum weight
            weights <= constraints.max_weight,  # Maximum weight
        ]

        # Additional constraints
        if constraints.max_assets:
            # Cardinality constraint (approximation using regularization)
            constraints_list.append(
                cp.norm(weights, 1) <= constraints.max_assets * constraints.max_weight
            )

        # Solve optimization
        objective = cp.Maximize(portfolio_return - 0.5 * portfolio_risk)
        problem = cp.Problem(objective, constraints_list)

        try:
            problem.solve()

            if weights.value is not None:
                optimal_weights = weights.value
                # Normalize to ensure sum equals 1
                optimal_weights = optimal_weights / optimal_weights.sum()

                return {
                    symbol: float(weight)
                    for symbol, weight in zip(
                        returns.columns, optimal_weights, strict=False
                    )
                }
            else:
                # Fallback to equal weights
                return {
                    symbol: 1.0 / len(returns.columns) for symbol in returns.columns
                }

        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            return {symbol: 1.0 / len(returns.columns) for symbol in returns.columns}

    async def _min_variance_optimization(
        self, returns: pd.DataFrame, constraints: OptimizationConstraints
    ) -> dict[str, float]:
        """Minimum variance optimization."""
        cov = returns.cov() * 252

        n = len(returns.columns)
        weights = cp.Variable(n)

        # Objective: minimize portfolio variance
        portfolio_risk = cp.quad_form(weights, cov.values)

        # Constraints
        constraints_list = [
            cp.sum(weights) == 1,
            weights >= constraints.min_weight,
            weights <= constraints.max_weight,
        ]

        # Solve optimization
        objective = cp.Minimize(portfolio_risk)
        problem = cp.Problem(objective, constraints_list)

        try:
            problem.solve()

            if weights.value is not None:
                optimal_weights = weights.value
                optimal_weights = optimal_weights / optimal_weights.sum()

                return {
                    symbol: float(weight)
                    for symbol, weight in zip(
                        returns.columns, optimal_weights, strict=False
                    )
                }
            else:
                return {
                    symbol: 1.0 / len(returns.columns) for symbol in returns.columns
                }

        except Exception as e:
            logger.error(f"Min variance optimization failed: {e}")
            return {symbol: 1.0 / len(returns.columns) for symbol in returns.columns}

    async def _risk_parity_optimization(
        self, returns: pd.DataFrame, constraints: OptimizationConstraints
    ) -> dict[str, float]:
        """Risk parity optimization."""
        cov = returns.cov() * 252

        def risk_parity_objective(weights):
            """Risk parity objective function."""
            weights = np.array(weights)
            portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov.values, weights)))

            # Risk contributions
            marginal_contrib = np.dot(cov.values, weights) / portfolio_vol
            contrib = weights * marginal_contrib

            # Target equal risk contribution
            target_contrib = portfolio_vol / len(weights)

            # Sum of squared deviations from target
            return np.sum((contrib - target_contrib) ** 2)

        # Initial guess (equal weights)
        initial_weights = np.ones(len(returns.columns)) / len(returns.columns)

        # Constraints
        constraints_scipy = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},  # Weights sum to 1
        ]

        # Bounds
        bounds = [
            (constraints.min_weight, constraints.max_weight)
            for _ in range(len(returns.columns))
        ]

        # Optimize
        try:
            result = optimize.minimize(
                risk_parity_objective,
                initial_weights,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints_scipy,
                options={"maxiter": 1000},
            )

            if result.success:
                optimal_weights = result.x
                return {
                    symbol: float(weight)
                    for symbol, weight in zip(
                        returns.columns, optimal_weights, strict=False
                    )
                }
            else:
                return {
                    symbol: 1.0 / len(returns.columns) for symbol in returns.columns
                }

        except Exception as e:
            logger.error(f"Risk parity optimization failed: {e}")
            return {symbol: 1.0 / len(returns.columns) for symbol in returns.columns}

    async def _black_litterman_optimization(
        self,
        returns: pd.DataFrame,
        constraints: OptimizationConstraints,
        views: dict[str, float] | None = None,
        confidence: float = 0.5,
    ) -> dict[str, float]:
        """Black-Litterman optimization with investor views."""
        # Market cap weights as prior (simplified)
        market_weights = np.ones(len(returns.columns)) / len(returns.columns)

        # Historical parameters
        returns.mean() * 252
        cov = returns.cov() * 252

        # Risk aversion parameter (estimated from market)
        risk_aversion = 3.0

        # Prior expected returns (reverse optimization)
        pi = risk_aversion * np.dot(cov.values, market_weights)

        if views:
            # Views matrix P and views vector Q
            P = np.zeros((len(views), len(returns.columns)))
            Q = np.zeros(len(views))

            for i, (symbol, view) in enumerate(views.items()):
                if symbol in returns.columns:
                    symbol_idx = returns.columns.get_loc(symbol)
                    P[i, symbol_idx] = 1
                    Q[i] = view

            # Uncertainty in views (diagonal matrix)
            omega = np.eye(len(views)) * (1 - confidence)

            # Black-Litterman formula
            tau = 0.05  # Scaling factor

            M1 = np.linalg.inv(tau * cov.values)
            M2 = np.dot(P.T, np.dot(np.linalg.inv(omega), P))
            M3 = np.dot(np.linalg.inv(tau * cov.values), pi)
            M4 = np.dot(P.T, np.dot(np.linalg.inv(omega), Q))

            # New expected returns
            mu_bl = np.dot(np.linalg.inv(M1 + M2), M3 + M4)

            # New covariance matrix
            cov_bl = np.linalg.inv(M1 + M2)

        else:
            mu_bl = pi
            cov_bl = cov.values

        # Optimize with Black-Litterman inputs
        n = len(returns.columns)
        weights = cp.Variable(n)

        portfolio_return = mu_bl.T @ weights
        portfolio_risk = cp.quad_form(weights, cov_bl)

        constraints_list = [
            cp.sum(weights) == 1,
            weights >= constraints.min_weight,
            weights <= constraints.max_weight,
        ]

        objective = cp.Maximize(portfolio_return - 0.5 * risk_aversion * portfolio_risk)
        problem = cp.Problem(objective, constraints_list)

        try:
            problem.solve()

            if weights.value is not None:
                optimal_weights = weights.value
                optimal_weights = optimal_weights / optimal_weights.sum()

                return {
                    symbol: float(weight)
                    for symbol, weight in zip(
                        returns.columns, optimal_weights, strict=False
                    )
                }
            else:
                return {
                    symbol: 1.0 / len(returns.columns) for symbol in returns.columns
                }

        except Exception as e:
            logger.error(f"Black-Litterman optimization failed: {e}")
            return {symbol: 1.0 / len(returns.columns) for symbol in returns.columns}

    async def _hierarchical_risk_parity(
        self, returns: pd.DataFrame, constraints: OptimizationConstraints
    ) -> dict[str, float]:
        """Hierarchical Risk Parity optimization."""
        from scipy.cluster.hierarchy import cut_tree, linkage
        from scipy.spatial.distance import squareform

        # Calculate correlation matrix
        corr = returns.corr()

        # Convert correlation to distance
        distance = np.sqrt(0.5 * (1 - corr))

        # Hierarchical clustering
        linkage_matrix = linkage(squareform(distance.values), method="ward")

        # Cut tree to get clusters
        n_clusters = min(5, len(returns.columns) // 2)  # Adaptive number of clusters
        clusters = cut_tree(linkage_matrix, n_clusters=n_clusters).flatten()

        # Calculate weights for each cluster using inverse variance
        cluster_weights = {}
        for cluster_id in np.unique(clusters):
            cluster_symbols = returns.columns[clusters == cluster_id]
            cluster_returns = returns[cluster_symbols]

            # Inverse variance weights within cluster
            inv_var = 1 / cluster_returns.var()
            cluster_weights[cluster_id] = inv_var / inv_var.sum()

        # Allocate between clusters (equal allocation for simplicity)
        n_clusters_actual = len(cluster_weights)
        cluster_allocation = 1.0 / n_clusters_actual

        # Final weights
        final_weights = {}
        for cluster_id, weights_dict in cluster_weights.items():
            for symbol, weight in weights_dict.items():
                final_weights[symbol] = weight * cluster_allocation

        return final_weights


class RebalancingEngine:
    """Portfolio rebalancing engine with multiple strategies."""

    def __init__(self, optimizer: PortfolioOptimizer):
        self.optimizer = optimizer

    async def should_rebalance(
        self,
        portfolio: Portfolio,
        target_weights: dict[str, float],
        threshold: float = 0.05,
    ) -> tuple[bool, dict[str, float]]:
        """Determine if portfolio should be rebalanced."""
        current_weights = portfolio.weights

        # Calculate deviations
        deviations = {}
        max_deviation = 0.0

        for symbol in target_weights:
            current_weight = current_weights.get(symbol, 0.0)
            target_weight = target_weights[symbol]
            deviation = abs(current_weight - target_weight)

            deviations[symbol] = deviation
            max_deviation = max(max_deviation, deviation)

        should_rebalance = max_deviation > threshold

        return should_rebalance, deviations

    async def calculate_trades(
        self,
        portfolio: Portfolio,
        target_weights: dict[str, float],
        transaction_cost_rate: float = 0.001,
    ) -> dict[str, dict[str, float]]:
        """Calculate required trades for rebalancing."""
        current_weights = portfolio.weights
        total_value = portfolio.total_value

        trades = {}
        total_transaction_cost = 0.0

        for symbol in target_weights:
            current_weight = current_weights.get(symbol, 0.0)
            target_weight = target_weights[symbol]

            # Calculate trade size
            weight_diff = target_weight - current_weight
            trade_value = weight_diff * total_value

            if abs(trade_value) > 100:  # Minimum trade size
                current_position = portfolio.positions.get(symbol)
                current_price = (
                    current_position.market_value / current_position.quantity
                    if current_position
                    else 0
                )

                if current_price > 0:
                    trade_quantity = trade_value / current_price
                    transaction_cost = abs(trade_value) * transaction_cost_rate

                    trades[symbol] = {
                        "quantity": trade_quantity,
                        "value": trade_value,
                        "transaction_cost": transaction_cost,
                        "direction": "buy" if trade_value > 0 else "sell",
                    }

                    total_transaction_cost += transaction_cost

        trades["summary"] = {
            "total_transaction_cost": total_transaction_cost,
            "cost_as_percentage": total_transaction_cost / total_value * 100,
        }

        return trades

    async def adaptive_rebalancing(
        self, portfolio: Portfolio, volatility_threshold: float = 0.25
    ) -> dict[str, Any]:
        """Adaptive rebalancing based on market conditions."""
        # Calculate recent volatility
        symbols = portfolio.symbols
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        price_data = await self.optimizer.data_provider.get_price_data(
            symbols, start_date, end_date
        )

        returns = price_data.pct_change().dropna()
        recent_volatility = returns.std().mean() * np.sqrt(252)

        # Determine rebalancing frequency based on volatility
        if recent_volatility > volatility_threshold:
            frequency = RebalancingFrequency.WEEKLY
            threshold = 0.03  # Lower threshold for high volatility
        else:
            frequency = RebalancingFrequency.MONTHLY
            threshold = 0.05  # Normal threshold

        return {
            "recommended_frequency": frequency,
            "rebalancing_threshold": threshold,
            "market_volatility": recent_volatility,
            "volatility_regime": (
                "high" if recent_volatility > volatility_threshold else "normal"
            ),
        }


class PortfolioManager:
    """Main portfolio management system."""

    def __init__(self):
        self.data_provider = DataProvider()
        self.risk_analyzer = RiskAnalyzer(self.data_provider)
        self.performance_analyzer = PerformanceAnalyzer(self.data_provider)
        self.optimizer = PortfolioOptimizer(self.data_provider)
        self.rebalancing_engine = RebalancingEngine(self.optimizer)
        self.portfolios = {}
        self.db_path = "portfolio_management.db"
        self._setup_database()

    def _setup_database(self):
        """Setup portfolio management database."""
        conn = sqlite3.connect(self.db_path)

        # Portfolios table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolios (
                portfolio_id TEXT PRIMARY KEY,
                name TEXT,
                portfolio_type TEXT,
                benchmark TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """
        )

        # Positions table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                portfolio_id TEXT,
                symbol TEXT,
                weight REAL,
                quantity REAL,
                market_value REAL,
                cost_basis REAL,
                unrealized_pnl REAL,
                realized_pnl REAL,
                last_updated TEXT
            )
        """
        )

        # Rebalancing history table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rebalancing_history (
                rebalance_id TEXT PRIMARY KEY,
                portfolio_id TEXT,
                rebalance_date TEXT,
                trigger_reason TEXT,
                trades TEXT,
                transaction_costs REAL,
                performance_impact REAL
            )
        """
        )

        conn.commit()
        conn.close()

    async def create_portfolio(
        self,
        name: str,
        portfolio_type: PortfolioType,
        initial_positions: dict[str, dict[str, float]],
        benchmark: str | None = None,
    ) -> Portfolio:
        """Create a new portfolio."""
        portfolio_id = str(uuid.uuid4())

        # Create asset objects
        positions = {}
        for symbol, pos_data in initial_positions.items():
            asset = Asset(
                symbol=symbol,
                name=symbol,  # Simplified
                asset_type="equity",
                sector="Unknown",
                market_cap=1e9,  # Default
                currency="USD",
                exchange="NYSE",
            )

            position = Position(
                asset=asset,
                weight=pos_data.get("weight", 0.0),
                quantity=pos_data.get("quantity", 0.0),
                market_value=pos_data.get("market_value", 0.0),
                cost_basis=pos_data.get("cost_basis", 0.0),
                unrealized_pnl=0.0,
                realized_pnl=0.0,
            )

            positions[symbol] = position

        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            name=name,
            portfolio_type=portfolio_type,
            positions=positions,
            benchmark=benchmark,
        )

        # Store in database
        await self._store_portfolio(portfolio)

        self.portfolios[portfolio_id] = portfolio
        return portfolio

    async def optimize_and_rebalance(
        self,
        portfolio_id: str,
        optimization_objective: OptimizationObjective,
        constraints: OptimizationConstraints,
        force_rebalance: bool = False,
    ) -> dict[str, Any]:
        """Optimize portfolio and execute rebalancing if needed."""
        portfolio = self.portfolios.get(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        # Optimize portfolio
        target_weights = await self.optimizer.optimize_portfolio(
            portfolio.symbols, optimization_objective, constraints
        )

        # Check if rebalancing is needed
        should_rebalance, deviations = await self.rebalancing_engine.should_rebalance(
            portfolio, target_weights
        )

        result = {
            "portfolio_id": portfolio_id,
            "optimization_objective": optimization_objective.value,
            "target_weights": target_weights,
            "current_weights": portfolio.weights,
            "weight_deviations": deviations,
            "should_rebalance": should_rebalance or force_rebalance,
            "rebalancing_executed": False,
        }

        if should_rebalance or force_rebalance:
            # Calculate trades
            trades = await self.rebalancing_engine.calculate_trades(
                portfolio, target_weights
            )

            result["trades"] = trades
            result["rebalancing_executed"] = True

            # Store rebalancing record
            await self._store_rebalancing_record(
                portfolio_id,
                "optimization" if force_rebalance else "threshold_breach",
                trades,
            )

            logger.info(
                f"Portfolio {portfolio_id} rebalanced with {len(trades)-1} trades"
            )

        return result

    async def generate_portfolio_report(self, portfolio_id: str) -> dict[str, Any]:
        """Generate comprehensive portfolio report."""
        portfolio = self.portfolios.get(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        # Calculate performance metrics
        performance = await self.performance_analyzer.calculate_performance_metrics(
            portfolio, portfolio.benchmark or "^GSPC"
        )

        # Calculate risk metrics
        risk_metrics = await self.risk_analyzer.calculate_portfolio_risk(portfolio)

        # Calculate VaR and CVaR
        var_95, cvar_95 = await self.risk_analyzer.calculate_var_cvar(portfolio)

        # Get adaptive rebalancing recommendation
        rebalancing_rec = await self.rebalancing_engine.adaptive_rebalancing(portfolio)

        report = {
            "portfolio_info": {
                "id": portfolio.portfolio_id,
                "name": portfolio.name,
                "type": portfolio.portfolio_type.value,
                "total_value": portfolio.total_value,
                "number_of_positions": len(portfolio.positions),
                "benchmark": portfolio.benchmark,
                "last_updated": portfolio.updated_at.isoformat(),
            },
            "performance_metrics": {
                "total_return": performance.total_return,
                "annualized_return": performance.annualized_return,
                "volatility": performance.volatility,
                "sharpe_ratio": performance.sharpe_ratio,
                "sortino_ratio": performance.sortino_ratio,
                "max_drawdown": performance.max_drawdown,
                "calmar_ratio": performance.calmar_ratio,
                "information_ratio": performance.information_ratio,
                "alpha": performance.alpha,
                "beta": performance.beta,
            },
            "risk_metrics": {
                "portfolio_variance": risk_metrics.portfolio_var,
                "var_95": var_95,
                "cvar_95": cvar_95,
                "concentration_risk": risk_metrics.concentration_risk,
                "liquidity_risk": risk_metrics.liquidity_risk,
                "risk_contributions": risk_metrics.risk_contribution,
            },
            "positions": [
                {
                    "symbol": symbol,
                    "weight": pos.weight,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "sector": pos.asset.sector,
                }
                for symbol, pos in portfolio.positions.items()
            ],
            "rebalancing_recommendation": rebalancing_rec,
        }

        return report

    async def _store_portfolio(self, portfolio: Portfolio):
        """Store portfolio in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Store portfolio
            conn.execute(
                """
                INSERT OR REPLACE INTO portfolios
                (portfolio_id, name, portfolio_type, benchmark, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    portfolio.portfolio_id,
                    portfolio.name,
                    portfolio.portfolio_type.value,
                    portfolio.benchmark,
                    portfolio.created_at.isoformat(),
                    portfolio.updated_at.isoformat(),
                    json.dumps(portfolio.metadata),
                ),
            )

            # Store positions
            for symbol, position in portfolio.positions.items():
                position_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT OR REPLACE INTO positions
                    (position_id, portfolio_id, symbol, weight, quantity, market_value,
                     cost_basis, unrealized_pnl, realized_pnl, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        position_id,
                        portfolio.portfolio_id,
                        symbol,
                        position.weight,
                        position.quantity,
                        position.market_value,
                        position.cost_basis,
                        position.unrealized_pnl,
                        position.realized_pnl,
                        position.last_updated.isoformat(),
                    ),
                )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing portfolio: {e}")

    async def _store_rebalancing_record(
        self, portfolio_id: str, trigger_reason: str, trades: dict[str, Any]
    ):
        """Store rebalancing record in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            rebalance_id = str(uuid.uuid4())
            transaction_costs = trades.get("summary", {}).get(
                "total_transaction_cost", 0.0
            )

            conn.execute(
                """
                INSERT INTO rebalancing_history
                (rebalance_id, portfolio_id, rebalance_date, trigger_reason,
                 trades, transaction_costs, performance_impact)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    rebalance_id,
                    portfolio_id,
                    datetime.now().isoformat(),
                    trigger_reason,
                    json.dumps(trades),
                    transaction_costs,
                    0.0,  # Performance impact calculation would be added here
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing rebalancing record: {e}")


# Example usage and testing
async def main():
    """Example usage of the portfolio management system."""

    # Initialize portfolio manager
    manager = PortfolioManager()

    # Create a sample portfolio
    initial_positions = {
        "AAPL": {
            "weight": 0.3,
            "quantity": 100,
            "market_value": 15000,
            "cost_basis": 14000,
        },
        "GOOGL": {
            "weight": 0.25,
            "quantity": 50,
            "market_value": 12500,
            "cost_basis": 12000,
        },
        "MSFT": {
            "weight": 0.2,
            "quantity": 80,
            "market_value": 10000,
            "cost_basis": 9500,
        },
        "AMZN": {
            "weight": 0.15,
            "quantity": 30,
            "market_value": 7500,
            "cost_basis": 7000,
        },
        "TSLA": {
            "weight": 0.1,
            "quantity": 40,
            "market_value": 5000,
            "cost_basis": 4800,
        },
    }

    portfolio = await manager.create_portfolio(
        name="Tech Growth Portfolio",
        portfolio_type=PortfolioType.EQUITY,
        initial_positions=initial_positions,
        benchmark="^GSPC",
    )

    print(f"Created portfolio: {portfolio.name}")
    print(f"Total value: ${portfolio.total_value:,.2f}")

    # Set up optimization constraints
    constraints = OptimizationConstraints(
        min_weight=0.05, max_weight=0.4, max_assets=10
    )

    # Optimize and rebalance
    optimization_result = await manager.optimize_and_rebalance(
        portfolio.portfolio_id,
        OptimizationObjective.MAX_SHARPE,
        constraints,
        force_rebalance=True,
    )

    print("\nOptimization Results:")
    print(f"Should rebalance: {optimization_result['should_rebalance']}")
    print("\nTarget weights:")
    for symbol, weight in optimization_result["target_weights"].items():
        print(f"  {symbol}: {weight:.3f}")

    # Generate comprehensive report
    report = await manager.generate_portfolio_report(portfolio.portfolio_id)

    print("\n" + "=" * 60)
    print("PORTFOLIO PERFORMANCE REPORT")
    print("=" * 60)

    perf = report["performance_metrics"]
    print("\nPerformance Metrics:")
    print(f"  Total Return: {perf['total_return']:.2%}")
    print(f"  Annualized Return: {perf['annualized_return']:.2%}")
    print(f"  Volatility: {perf['volatility']:.2%}")
    print(f"  Sharpe Ratio: {perf['sharpe_ratio']:.3f}")
    print(f"  Max Drawdown: {perf['max_drawdown']:.2%}")

    risk = report["risk_metrics"]
    print("\nRisk Metrics:")
    print(f"  VaR (95%): {risk['var_95']:.2%}")
    print(f"  CVaR (95%): {risk['cvar_95']:.2%}")
    print(f"  Concentration Risk: {risk['concentration_risk']:.3f}")

    print("\nRebalancing Recommendation:")
    rebal = report["rebalancing_recommendation"]
    print(f"  Frequency: {rebal['recommended_frequency'].value}")
    print(f"  Threshold: {rebal['rebalancing_threshold']:.1%}")
    print(f"  Market Volatility: {rebal['market_volatility']:.2%}")

    # Test different optimization objectives
    print("\n" + "=" * 60)
    print("OPTIMIZATION COMPARISON")
    print("=" * 60)

    objectives = [
        OptimizationObjective.MAX_SHARPE,
        OptimizationObjective.MIN_VARIANCE,
        OptimizationObjective.RISK_PARITY,
    ]

    for objective in objectives:
        weights = await manager.optimizer.optimize_portfolio(
            portfolio.symbols, objective, constraints
        )

        print(f"\n{objective.value.upper()} Optimization:")
        for symbol, weight in weights.items():
            print(f"  {symbol}: {weight:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
