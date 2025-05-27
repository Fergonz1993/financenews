"""
Portfolio Management & Robo-Advisory Engine

This module provides comprehensive portfolio management capabilities including
AI-powered robo-advisory services, portfolio optimization, rebalancing,
ESG integration, and advanced risk management for modern fintech platforms.
"""

import asyncio
import json
import logging
import sqlite3
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import cvxpy as cp
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class RiskProfile(Enum):
    """Investor risk profile types."""

    CONSERVATIVE = "conservative"
    MODERATE_CONSERVATIVE = "moderate_conservative"
    MODERATE = "moderate"
    MODERATE_AGGRESSIVE = "moderate_aggressive"
    AGGRESSIVE = "aggressive"


class InvestmentGoal(Enum):
    """Investment goal types."""

    RETIREMENT = "retirement"
    WEALTH_BUILDING = "wealth_building"
    INCOME_GENERATION = "income_generation"
    CAPITAL_PRESERVATION = "capital_preservation"
    EDUCATION_FUNDING = "education_funding"
    HOME_PURCHASE = "home_purchase"
    EMERGENCY_FUND = "emergency_fund"


class AssetClass(Enum):
    """Asset class types."""

    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    REAL_ESTATE = "real_estate"
    COMMODITIES = "commodities"
    ALTERNATIVES = "alternatives"
    CASH = "cash"
    CRYPTO = "crypto"


class ESGRating(Enum):
    """ESG rating levels."""

    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    NOT_RATED = "not_rated"


class RebalanceStrategy(Enum):
    """Portfolio rebalancing strategies."""

    CALENDAR = "calendar"
    THRESHOLD = "threshold"
    VOLATILITY_TARGET = "volatility_target"
    RISK_PARITY = "risk_parity"
    MOMENTUM = "momentum"


@dataclass
class InvestorProfile:
    """Comprehensive investor profile."""

    user_id: str
    age: int
    income: float
    net_worth: float
    investment_experience: str  # beginner, intermediate, advanced
    risk_tolerance: RiskProfile
    investment_goals: list[InvestmentGoal]
    time_horizon: int  # years
    liquidity_needs: float  # percentage
    esg_preference: bool
    tax_status: str
    investment_amount: float
    monthly_contribution: float = 0.0
    risk_capacity: float = 0.0
    behavioral_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Asset:
    """Financial asset representation."""

    symbol: str
    name: str
    asset_class: AssetClass
    sector: str | None = None
    region: str | None = None
    currency: str = "USD"
    expense_ratio: float = 0.0
    esg_rating: ESGRating = ESGRating.NOT_RATED
    esg_score: float = 0.0
    market_cap: float | None = None
    dividend_yield: float = 0.0
    beta: float = 1.0
    sharpe_ratio: float | None = None
    volatility: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioHolding:
    """Portfolio holding representation."""

    asset: Asset
    weight: float
    shares: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    unrealized_pnl: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Portfolio:
    """Complete portfolio representation."""

    portfolio_id: str
    user_id: str
    name: str
    holdings: list[PortfolioHolding] = field(default_factory=list)
    total_value: float = 0.0
    cash_balance: float = 0.0
    target_allocation: dict[str, float] = field(default_factory=dict)
    actual_allocation: dict[str, float] = field(default_factory=dict)
    risk_metrics: dict[str, float] = field(default_factory=dict)
    performance_metrics: dict[str, float] = field(default_factory=dict)
    esg_score: float = 0.0
    last_rebalanced: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RebalanceRecommendation:
    """Portfolio rebalancing recommendation."""

    portfolio_id: str
    timestamp: datetime
    current_allocation: dict[str, float]
    target_allocation: dict[str, float]
    trades: list[dict[str, Any]]
    expected_cost: float
    rationale: str
    urgency: str  # low, medium, high
    estimated_impact: dict[str, float]


@dataclass
class InvestmentAdvice:
    """AI-generated investment advice."""

    advice_id: str
    user_id: str
    advice_type: str
    title: str
    content: str
    confidence_score: float
    supporting_data: dict[str, Any]
    action_items: list[str]
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False


class RiskAssessmentEngine:
    """Advanced risk assessment and profiling engine."""

    def __init__(self):
        self.risk_questions = self._load_risk_questions()
        self.behavioral_factors = {}

    def _load_risk_questions(self) -> list[dict[str, Any]]:
        """Load comprehensive risk assessment questions."""
        return [
            {
                "id": "age_retirement",
                "question": "How many years until you plan to retire?",
                "type": "numeric",
                "weight": 0.15,
                "scoring": {"0-10": 1, "11-20": 2, "21-30": 3, "31-40": 4, "40+": 5},
            },
            {
                "id": "investment_experience",
                "question": "How would you describe your investment experience?",
                "type": "multiple_choice",
                "weight": 0.12,
                "options": {
                    "No experience": 1,
                    "Limited experience": 2,
                    "Some experience": 3,
                    "Considerable experience": 4,
                    "Extensive experience": 5,
                },
            },
            {
                "id": "market_decline_reaction",
                "question": "If your portfolio declined 20% in a month, what would you do?",
                "type": "multiple_choice",
                "weight": 0.20,
                "options": {
                    "Sell everything immediately": 1,
                    "Sell some investments": 2,
                    "Hold and wait": 3,
                    "Buy more at lower prices": 4,
                    "Significantly increase investments": 5,
                },
            },
            {
                "id": "income_stability",
                "question": "How stable is your current income?",
                "type": "multiple_choice",
                "weight": 0.10,
                "options": {
                    "Very unstable": 1,
                    "Somewhat unstable": 2,
                    "Stable": 3,
                    "Very stable": 4,
                    "Multiple stable sources": 5,
                },
            },
            {
                "id": "emergency_fund",
                "question": "How many months of expenses do you have in emergency savings?",
                "type": "multiple_choice",
                "weight": 0.08,
                "options": {
                    "Less than 1 month": 1,
                    "1-3 months": 2,
                    "3-6 months": 3,
                    "6-12 months": 4,
                    "More than 12 months": 5,
                },
            },
            {
                "id": "investment_goal",
                "question": "What is your primary investment goal?",
                "type": "multiple_choice",
                "weight": 0.15,
                "options": {
                    "Capital preservation": 1,
                    "Income generation": 2,
                    "Balanced growth": 3,
                    "Capital appreciation": 4,
                    "Aggressive growth": 5,
                },
            },
            {
                "id": "loss_tolerance",
                "question": "What's the maximum loss you could tolerate in a year?",
                "type": "multiple_choice",
                "weight": 0.20,
                "options": {
                    "Cannot tolerate any loss": 1,
                    "Up to 5% loss": 2,
                    "Up to 15% loss": 3,
                    "Up to 25% loss": 4,
                    "More than 25% loss": 5,
                },
            },
        ]

    def assess_risk_profile(
        self, responses: dict[str, Any], investor_data: dict[str, Any]
    ) -> tuple[RiskProfile, float, dict[str, Any]]:
        """Comprehensive risk profile assessment."""
        try:
            # Calculate questionnaire score
            questionnaire_score = 0.0
            total_weight = 0.0

            for question in self.risk_questions:
                if question["id"] in responses:
                    response = responses[question["id"]]

                    if question["type"] == "multiple_choice":
                        score = question["options"].get(response, 3)
                    elif question["type"] == "numeric":
                        score = self._score_numeric_response(
                            response, question["scoring"]
                        )
                    else:
                        score = 3  # Default neutral score

                    questionnaire_score += score * question["weight"]
                    total_weight += question["weight"]

            if total_weight > 0:
                questionnaire_score = questionnaire_score / total_weight

            # Adjust based on demographic factors
            demographic_adjustments = self._calculate_demographic_adjustments(
                investor_data
            )

            # Calculate behavioral score
            behavioral_score = self._assess_behavioral_factors(responses, investor_data)

            # Combine scores
            final_score = (
                questionnaire_score * 0.6
                + demographic_adjustments * 0.25
                + behavioral_score * 0.15
            )

            # Determine risk profile
            risk_profile = self._score_to_risk_profile(final_score)

            # Generate detailed analysis
            analysis = {
                "questionnaire_score": questionnaire_score,
                "demographic_score": demographic_adjustments,
                "behavioral_score": behavioral_score,
                "final_score": final_score,
                "risk_capacity": self._calculate_risk_capacity(investor_data),
                "recommendations": self._generate_risk_recommendations(
                    final_score, investor_data
                ),
            }

            return risk_profile, final_score, analysis

        except Exception as e:
            logger.error(f"Error in risk assessment: {e}")
            return RiskProfile.MODERATE, 3.0, {}

    def _score_numeric_response(
        self, response: int | float, scoring: dict[str, int]
    ) -> int:
        """Score numeric responses based on ranges."""
        for range_str, score in scoring.items():
            if "-" in range_str:
                min_val, max_val = map(int, range_str.split("-"))
                if min_val <= response <= max_val:
                    return score
            elif range_str.endswith("+"):
                min_val = int(range_str[:-1])
                if response >= min_val:
                    return score
        return 3  # Default score

    def _calculate_demographic_adjustments(
        self, investor_data: dict[str, Any]
    ) -> float:
        """Calculate risk adjustments based on demographics."""
        score = 3.0  # Base score

        # Age adjustment
        age = investor_data.get("age", 40)
        if age < 30:
            score += 0.5
        elif age > 60:
            score -= 0.5

        # Income stability adjustment
        income = investor_data.get("income", 50000)
        net_worth = investor_data.get("net_worth", 100000)

        if income > 100000 and net_worth > 500000:
            score += 0.3
        elif income < 30000 or net_worth < 10000:
            score -= 0.3

        # Investment experience adjustment
        experience = investor_data.get("investment_experience", "beginner")
        if experience == "advanced":
            score += 0.4
        elif experience == "beginner":
            score -= 0.2

        return max(1.0, min(5.0, score))

    def _assess_behavioral_factors(
        self, responses: dict[str, Any], investor_data: dict[str, Any]
    ) -> float:
        """Assess behavioral biases and tendencies."""
        score = 3.0

        # Loss aversion assessment
        if "market_decline_reaction" in responses:
            reaction = responses["market_decline_reaction"]
            if "Sell" in reaction:
                score -= 0.5  # High loss aversion
            elif "Buy more" in reaction:
                score += 0.5  # Low loss aversion

        # Overconfidence assessment
        experience = investor_data.get("investment_experience", "beginner")
        if experience == "advanced" and investor_data.get("age", 40) < 35:
            score += 0.3  # Potential overconfidence

        return max(1.0, min(5.0, score))

    def _calculate_risk_capacity(self, investor_data: dict[str, Any]) -> float:
        """Calculate objective risk capacity."""
        age = investor_data.get("age", 40)
        income = investor_data.get("income", 50000)
        net_worth = investor_data.get("net_worth", 100000)
        time_horizon = investor_data.get("time_horizon", 10)

        # Age factor (younger = higher capacity)
        age_factor = max(0.1, (65 - age) / 65)

        # Wealth factor
        wealth_factor = min(1.0, net_worth / 1000000)

        # Income factor
        income_factor = min(1.0, income / 200000)

        # Time horizon factor
        time_factor = min(1.0, time_horizon / 30)

        capacity = (
            age_factor * 0.3
            + wealth_factor * 0.3
            + income_factor * 0.2
            + time_factor * 0.2
        )

        return capacity

    def _score_to_risk_profile(self, score: float) -> RiskProfile:
        """Convert numerical score to risk profile."""
        if score <= 1.5:
            return RiskProfile.CONSERVATIVE
        elif score <= 2.5:
            return RiskProfile.MODERATE_CONSERVATIVE
        elif score <= 3.5:
            return RiskProfile.MODERATE
        elif score <= 4.5:
            return RiskProfile.MODERATE_AGGRESSIVE
        else:
            return RiskProfile.AGGRESSIVE

    def _generate_risk_recommendations(
        self, score: float, investor_data: dict[str, Any]
    ) -> list[str]:
        """Generate personalized risk recommendations."""
        recommendations = []

        if score < 2.0:
            recommendations.extend(
                [
                    "Consider building a larger emergency fund before investing",
                    "Focus on capital preservation with high-quality bonds",
                    "Gradually increase risk tolerance through education",
                ]
            )
        elif score > 4.0:
            recommendations.extend(
                [
                    "Ensure you have adequate emergency savings",
                    "Consider diversification to manage concentration risk",
                    "Regular portfolio reviews to maintain risk alignment",
                ]
            )

        age = investor_data.get("age", 40)
        if age > 55:
            recommendations.append(
                "Consider gradually reducing risk as retirement approaches"
            )

        return recommendations


class AssetUniverseManager:
    """Manages the universe of investable assets."""

    def __init__(self):
        self.assets = {}
        self.asset_data = {}
        self.esg_data = {}
        self._initialize_asset_universe()

    def _initialize_asset_universe(self):
        """Initialize comprehensive asset universe."""
        # ETF universe covering major asset classes
        etf_universe = [
            # US Equity
            {
                "symbol": "VTI",
                "name": "Vanguard Total Stock Market ETF",
                "asset_class": AssetClass.EQUITY,
                "sector": "US Total Market",
                "expense_ratio": 0.03,
                "esg_rating": ESGRating.GOOD,
            },
            {
                "symbol": "VOO",
                "name": "Vanguard S&P 500 ETF",
                "asset_class": AssetClass.EQUITY,
                "sector": "US Large Cap",
                "expense_ratio": 0.03,
                "esg_rating": ESGRating.GOOD,
            },
            {
                "symbol": "VEA",
                "name": "Vanguard FTSE Developed Markets ETF",
                "asset_class": AssetClass.EQUITY,
                "sector": "International Developed",
                "expense_ratio": 0.05,
                "esg_rating": ESGRating.GOOD,
            },
            {
                "symbol": "VWO",
                "name": "Vanguard FTSE Emerging Markets ETF",
                "asset_class": AssetClass.EQUITY,
                "sector": "Emerging Markets",
                "expense_ratio": 0.10,
                "esg_rating": ESGRating.AVERAGE,
            },
            # Fixed Income
            {
                "symbol": "BND",
                "name": "Vanguard Total Bond Market ETF",
                "asset_class": AssetClass.FIXED_INCOME,
                "sector": "US Aggregate",
                "expense_ratio": 0.03,
                "esg_rating": ESGRating.GOOD,
            },
            {
                "symbol": "VGIT",
                "name": "Vanguard Intermediate-Term Treasury ETF",
                "asset_class": AssetClass.FIXED_INCOME,
                "sector": "US Treasury",
                "expense_ratio": 0.04,
                "esg_rating": ESGRating.EXCELLENT,
            },
            {
                "symbol": "VTEB",
                "name": "Vanguard Tax-Exempt Bond ETF",
                "asset_class": AssetClass.FIXED_INCOME,
                "sector": "Municipal",
                "expense_ratio": 0.05,
                "esg_rating": ESGRating.GOOD,
            },
            # Real Estate
            {
                "symbol": "VNQ",
                "name": "Vanguard Real Estate ETF",
                "asset_class": AssetClass.REAL_ESTATE,
                "sector": "US REITs",
                "expense_ratio": 0.12,
                "esg_rating": ESGRating.AVERAGE,
            },
            # Commodities
            {
                "symbol": "VDE",
                "name": "Vanguard Energy ETF",
                "asset_class": AssetClass.COMMODITIES,
                "sector": "Energy",
                "expense_ratio": 0.10,
                "esg_rating": ESGRating.POOR,
            },
            {
                "symbol": "GLD",
                "name": "SPDR Gold Shares",
                "asset_class": AssetClass.COMMODITIES,
                "sector": "Gold",
                "expense_ratio": 0.40,
                "esg_rating": ESGRating.NOT_RATED,
            },
            # ESG Focused
            {
                "symbol": "ESG",
                "name": "FlexShares STOXX US ESG Select Index Fund",
                "asset_class": AssetClass.EQUITY,
                "sector": "US ESG",
                "expense_ratio": 0.46,
                "esg_rating": ESGRating.EXCELLENT,
            },
            {
                "symbol": "ESGD",
                "name": "iShares MSCI EAFE ESG Select ETF",
                "asset_class": AssetClass.EQUITY,
                "sector": "International ESG",
                "expense_ratio": 0.20,
                "esg_rating": ESGRating.EXCELLENT,
            },
        ]

        for etf_data in etf_universe:
            asset = Asset(**etf_data)
            self.assets[asset.symbol] = asset

    async def update_asset_data(self, symbols: list[str] | None = None):
        """Update market data for assets."""
        if symbols is None:
            symbols = list(self.assets.keys())

        try:
            # Fetch market data
            tickers = yf.Tickers(" ".join(symbols))

            for symbol in symbols:
                if symbol in self.assets:
                    try:
                        ticker = tickers.tickers[symbol]
                        info = ticker.info
                        hist = ticker.history(period="1y")

                        if not hist.empty:
                            # Calculate metrics
                            returns = hist["Close"].pct_change().dropna()
                            volatility = returns.std() * np.sqrt(252)

                            # Update asset data
                            asset = self.assets[symbol]
                            asset.volatility = volatility
                            asset.dividend_yield = info.get("dividendYield", 0.0) or 0.0
                            asset.market_cap = info.get("totalAssets", 0.0) or 0.0

                            # Store historical data
                            self.asset_data[symbol] = {
                                "prices": hist["Close"],
                                "returns": returns,
                                "volatility": volatility,
                                "last_updated": datetime.now(),
                            }

                    except Exception as e:
                        logger.warning(f"Error updating data for {symbol}: {e}")

        except Exception as e:
            logger.error(f"Error updating asset data: {e}")

    def get_assets_by_criteria(
        self,
        asset_classes: list[AssetClass] | None = None,
        esg_rating: ESGRating = None,
        max_expense_ratio: float | None = None,
    ) -> list[Asset]:
        """Filter assets by criteria."""
        filtered_assets = []

        for asset in self.assets.values():
            # Asset class filter
            if asset_classes and asset.asset_class not in asset_classes:
                continue

            # ESG filter
            if esg_rating and asset.esg_rating != esg_rating:
                continue

            # Expense ratio filter
            if max_expense_ratio and asset.expense_ratio > max_expense_ratio:
                continue

            filtered_assets.append(asset)

        return filtered_assets

    def calculate_correlation_matrix(
        self, symbols: list[str], period: str = "1y"
    ) -> pd.DataFrame:
        """Calculate correlation matrix for assets."""
        try:
            returns_data = {}

            for symbol in symbols:
                if symbol in self.asset_data:
                    returns_data[symbol] = self.asset_data[symbol]["returns"]

            if returns_data:
                returns_df = pd.DataFrame(returns_data)
                return returns_df.corr()

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            return pd.DataFrame()


class PortfolioOptimizer:
    """Advanced portfolio optimization engine."""

    def __init__(self):
        self.optimization_methods = {
            "mean_variance": self._mean_variance_optimization,
            "risk_parity": self._risk_parity_optimization,
            "black_litterman": self._black_litterman_optimization,
            "hierarchical_risk_parity": self._hrp_optimization,
            "minimum_variance": self._minimum_variance_optimization,
        }

    def optimize_portfolio(
        self,
        assets: list[Asset],
        returns_data: pd.DataFrame,
        risk_profile: RiskProfile,
        constraints: dict[str, Any] | None = None,
        method: str = "mean_variance",
    ) -> dict[str, float]:
        """Optimize portfolio allocation."""
        try:
            if method not in self.optimization_methods:
                method = "mean_variance"

            # Prepare data
            returns = returns_data.dropna()
            if returns.empty:
                return self._equal_weight_allocation(assets)

            # Apply optimization method
            weights = self.optimization_methods[method](
                returns, risk_profile, constraints
            )

            # Ensure weights sum to 1 and are non-negative
            weights = np.maximum(weights, 0)
            weights = weights / np.sum(weights)

            # Convert to dictionary
            allocation = {}
            for i, asset in enumerate(assets):
                if i < len(weights):
                    allocation[asset.symbol] = float(weights[i])

            return allocation

        except Exception as e:
            logger.error(f"Error in portfolio optimization: {e}")
            return self._equal_weight_allocation(assets)

    def _mean_variance_optimization(
        self,
        returns: pd.DataFrame,
        risk_profile: RiskProfile,
        constraints: dict[str, Any] | None = None,
    ) -> np.ndarray:
        """Mean-variance optimization."""
        try:
            n_assets = len(returns.columns)

            # Calculate expected returns and covariance
            mu = returns.mean() * 252  # Annualized
            cov = returns.cov() * 252  # Annualized

            # Risk aversion parameter based on risk profile
            risk_aversion = self._get_risk_aversion(risk_profile)

            # Define optimization variables
            w = cp.Variable(n_assets)

            # Objective: maximize utility (return - risk penalty)
            portfolio_return = mu.values @ w
            portfolio_risk = cp.quad_form(w, cov.values)
            utility = portfolio_return - 0.5 * risk_aversion * portfolio_risk

            # Constraints
            constraints_list = [cp.sum(w) == 1, w >= 0]  # Weights sum to 1  # Long-only

            # Additional constraints
            if constraints:
                if "max_weight" in constraints:
                    constraints_list.append(w <= constraints["max_weight"])
                if "min_weight" in constraints:
                    constraints_list.append(w >= constraints["min_weight"])

            # Solve optimization
            problem = cp.Problem(cp.Maximize(utility), constraints_list)
            problem.solve()

            if w.value is not None:
                return w.value
            else:
                return np.ones(n_assets) / n_assets

        except Exception as e:
            logger.error(f"Error in mean-variance optimization: {e}")
            return np.ones(len(returns.columns)) / len(returns.columns)

    def _risk_parity_optimization(
        self,
        returns: pd.DataFrame,
        risk_profile: RiskProfile,
        constraints: dict[str, Any] | None = None,
    ) -> np.ndarray:
        """Risk parity optimization."""
        try:
            cov = returns.cov() * 252  # Annualized covariance
            n_assets = len(returns.columns)

            def risk_parity_objective(weights):
                portfolio_vol = np.sqrt(weights @ cov @ weights)
                marginal_contrib = cov @ weights / portfolio_vol
                contrib = weights * marginal_contrib
                target_contrib = portfolio_vol / n_assets
                return np.sum((contrib - target_contrib) ** 2)

            # Constraints
            constraints_list = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

            bounds = [(0.01, 0.5) for _ in range(n_assets)]

            # Initial guess
            x0 = np.ones(n_assets) / n_assets

            # Optimize
            result = minimize(
                risk_parity_objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints_list,
            )

            if result.success:
                return result.x
            else:
                return np.ones(n_assets) / n_assets

        except Exception as e:
            logger.error(f"Error in risk parity optimization: {e}")
            return np.ones(len(returns.columns)) / len(returns.columns)

    def _black_litterman_optimization(
        self,
        returns: pd.DataFrame,
        risk_profile: RiskProfile,
        constraints: dict[str, Any] | None = None,
    ) -> np.ndarray:
        """Black-Litterman optimization with market views."""
        try:
            # Simplified Black-Litterman implementation
            # In practice, this would incorporate market views and uncertainty

            cov = returns.cov() * 252
            n_assets = len(returns.columns)

            # Market capitalization weights (simplified)
            market_weights = np.ones(n_assets) / n_assets

            # Risk aversion
            risk_aversion = self._get_risk_aversion(risk_profile)

            # Implied equilibrium returns
            pi = risk_aversion * cov @ market_weights

            # Black-Litterman formula (without views for simplicity)
            tau = 0.025  # Scaling factor
            tau * cov  # Uncertainty matrix

            # Posterior expected returns
            mu_bl = pi  # Without views, equals implied returns

            # Optimal weights
            weights = np.linalg.inv(risk_aversion * cov) @ mu_bl
            weights = weights / np.sum(weights)

            return np.maximum(weights, 0)

        except Exception as e:
            logger.error(f"Error in Black-Litterman optimization: {e}")
            return np.ones(len(returns.columns)) / len(returns.columns)

    def _hrp_optimization(
        self,
        returns: pd.DataFrame,
        risk_profile: RiskProfile,
        constraints: dict[str, Any] | None = None,
    ) -> np.ndarray:
        """Hierarchical Risk Parity optimization."""
        try:
            # Calculate correlation matrix
            corr = returns.corr()

            # Hierarchical clustering
            from scipy.cluster.hierarchy import linkage
            from scipy.spatial.distance import squareform

            # Distance matrix
            distance = np.sqrt(0.5 * (1 - corr))

            # Hierarchical clustering
            linkage_matrix = linkage(squareform(distance), method="ward")

            # Recursive bisection for weight allocation
            weights = self._recursive_bisection(corr, linkage_matrix)

            return weights

        except Exception as e:
            logger.error(f"Error in HRP optimization: {e}")
            return np.ones(len(returns.columns)) / len(returns.columns)

    def _minimum_variance_optimization(
        self,
        returns: pd.DataFrame,
        risk_profile: RiskProfile,
        constraints: dict[str, Any] | None = None,
    ) -> np.ndarray:
        """Minimum variance optimization."""
        try:
            cov = returns.cov() * 252
            n_assets = len(returns.columns)

            # Define optimization variables
            w = cp.Variable(n_assets)

            # Objective: minimize portfolio variance
            portfolio_variance = cp.quad_form(w, cov.values)

            # Constraints
            constraints_list = [cp.sum(w) == 1, w >= 0]

            # Solve optimization
            problem = cp.Problem(cp.Minimize(portfolio_variance), constraints_list)
            problem.solve()

            if w.value is not None:
                return w.value
            else:
                return np.ones(n_assets) / n_assets

        except Exception as e:
            logger.error(f"Error in minimum variance optimization: {e}")
            return np.ones(len(returns.columns)) / len(returns.columns)

    def _recursive_bisection(
        self, corr: pd.DataFrame, linkage_matrix: np.ndarray
    ) -> np.ndarray:
        """Recursive bisection for HRP."""
        # Simplified implementation
        n_assets = len(corr)
        weights = np.ones(n_assets) / n_assets
        return weights

    def _get_risk_aversion(self, risk_profile: RiskProfile) -> float:
        """Get risk aversion parameter based on risk profile."""
        risk_aversion_map = {
            RiskProfile.CONSERVATIVE: 10.0,
            RiskProfile.MODERATE_CONSERVATIVE: 7.5,
            RiskProfile.MODERATE: 5.0,
            RiskProfile.MODERATE_AGGRESSIVE: 2.5,
            RiskProfile.AGGRESSIVE: 1.0,
        }
        return risk_aversion_map.get(risk_profile, 5.0)

    def _equal_weight_allocation(self, assets: list[Asset]) -> dict[str, float]:
        """Fallback equal weight allocation."""
        weight = 1.0 / len(assets)
        return {asset.symbol: weight for asset in assets}


class RoboAdvisorEngine:
    """AI-powered robo-advisory engine."""

    def __init__(self):
        self.risk_assessor = RiskAssessmentEngine()
        self.asset_manager = AssetUniverseManager()
        self.optimizer = PortfolioOptimizer()
        self.portfolios = {}
        self.advice_history = {}

        self.db_path = "portfolio_management.db"
        self._setup_database()

    def _setup_database(self):
        """Setup portfolio management database."""
        conn = sqlite3.connect(self.db_path)

        # Investor profiles table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS investor_profiles (
                user_id TEXT PRIMARY KEY,
                age INTEGER,
                income REAL,
                net_worth REAL,
                investment_experience TEXT,
                risk_tolerance TEXT,
                investment_goals TEXT,
                time_horizon INTEGER,
                liquidity_needs REAL,
                esg_preference BOOLEAN,
                tax_status TEXT,
                investment_amount REAL,
                monthly_contribution REAL,
                risk_capacity REAL,
                behavioral_score REAL,
                created_at TEXT
            )
        """
        )

        # Portfolios table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolios (
                portfolio_id TEXT PRIMARY KEY,
                user_id TEXT,
                name TEXT,
                holdings TEXT,
                total_value REAL,
                cash_balance REAL,
                target_allocation TEXT,
                actual_allocation TEXT,
                risk_metrics TEXT,
                performance_metrics TEXT,
                esg_score REAL,
                last_rebalanced TEXT,
                created_at TEXT
            )
        """
        )

        # Investment advice table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS investment_advice (
                advice_id TEXT PRIMARY KEY,
                user_id TEXT,
                advice_type TEXT,
                title TEXT,
                content TEXT,
                confidence_score REAL,
                supporting_data TEXT,
                action_items TEXT,
                timestamp TEXT,
                acknowledged BOOLEAN
            )
        """
        )

        # Rebalancing recommendations table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rebalance_recommendations (
                recommendation_id TEXT PRIMARY KEY,
                portfolio_id TEXT,
                timestamp TEXT,
                current_allocation TEXT,
                target_allocation TEXT,
                trades TEXT,
                expected_cost REAL,
                rationale TEXT,
                urgency TEXT,
                estimated_impact TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    async def onboard_investor(
        self,
        user_id: str,
        questionnaire_responses: dict[str, Any],
        demographic_data: dict[str, Any],
    ) -> InvestorProfile:
        """Complete investor onboarding process."""
        try:
            # Assess risk profile
            risk_profile, risk_score, analysis = self.risk_assessor.assess_risk_profile(
                questionnaire_responses, demographic_data
            )

            # Create investor profile
            profile = InvestorProfile(
                user_id=user_id,
                age=demographic_data.get("age", 35),
                income=demographic_data.get("income", 75000),
                net_worth=demographic_data.get("net_worth", 150000),
                investment_experience=demographic_data.get(
                    "investment_experience", "intermediate"
                ),
                risk_tolerance=risk_profile,
                investment_goals=[
                    InvestmentGoal(goal)
                    for goal in demographic_data.get(
                        "investment_goals", ["wealth_building"]
                    )
                ],
                time_horizon=demographic_data.get("time_horizon", 15),
                liquidity_needs=demographic_data.get("liquidity_needs", 0.1),
                esg_preference=demographic_data.get("esg_preference", False),
                tax_status=demographic_data.get("tax_status", "taxable"),
                investment_amount=demographic_data.get("investment_amount", 10000),
                monthly_contribution=demographic_data.get("monthly_contribution", 500),
                risk_capacity=analysis.get("risk_capacity", 0.5),
                behavioral_score=analysis.get("behavioral_score", 3.0),
            )

            # Store in database
            await self._store_investor_profile(profile)

            # Generate initial investment advice
            await self._generate_onboarding_advice(profile, analysis)

            logger.info(
                f"Onboarded investor {user_id} with risk profile {risk_profile.value}"
            )

            return profile

        except Exception as e:
            logger.error(f"Error in investor onboarding: {e}")
            raise

    async def create_portfolio(
        self, user_id: str, portfolio_name: str = "Main Portfolio"
    ) -> Portfolio:
        """Create optimized portfolio for investor."""
        try:
            # Get investor profile
            profile = await self._get_investor_profile(user_id)
            if not profile:
                raise ValueError(f"Investor profile not found for user {user_id}")

            # Update asset data
            await self.asset_manager.update_asset_data()

            # Select appropriate assets
            assets = self._select_assets_for_profile(profile)

            # Get returns data
            returns_data = self._prepare_returns_data(assets)

            # Optimize portfolio
            allocation = self.optimizer.optimize_portfolio(
                assets, returns_data, profile.risk_tolerance
            )

            # Create portfolio
            portfolio = Portfolio(
                portfolio_id=f"{user_id}_portfolio_{datetime.now().strftime('%Y%m%d')}",
                user_id=user_id,
                name=portfolio_name,
                target_allocation=allocation,
                total_value=profile.investment_amount,
                cash_balance=profile.investment_amount * 0.05,  # 5% cash buffer
            )

            # Create holdings
            portfolio.holdings = self._create_holdings(
                assets, allocation, portfolio.total_value
            )

            # Calculate metrics
            portfolio.risk_metrics = self._calculate_portfolio_risk_metrics(
                portfolio, returns_data
            )
            portfolio.esg_score = self._calculate_portfolio_esg_score(portfolio)

            # Store portfolio
            await self._store_portfolio(portfolio)
            self.portfolios[portfolio.portfolio_id] = portfolio

            logger.info(
                f"Created portfolio {portfolio.portfolio_id} for user {user_id}"
            )

            return portfolio

        except Exception as e:
            logger.error(f"Error creating portfolio: {e}")
            raise

    async def generate_investment_advice(self, user_id: str) -> list[InvestmentAdvice]:
        """Generate AI-powered investment advice."""
        try:
            profile = await self._get_investor_profile(user_id)
            if not profile:
                return []

            advice_list = []

            # Market outlook advice
            market_advice = await self._generate_market_outlook_advice(profile)
            if market_advice:
                advice_list.append(market_advice)

            # Portfolio rebalancing advice
            rebalance_advice = await self._generate_rebalancing_advice(user_id)
            if rebalance_advice:
                advice_list.append(rebalance_advice)

            # Tax optimization advice
            tax_advice = await self._generate_tax_optimization_advice(profile)
            if tax_advice:
                advice_list.append(tax_advice)

            # Goal tracking advice
            goal_advice = await self._generate_goal_tracking_advice(profile)
            if goal_advice:
                advice_list.append(goal_advice)

            # Store advice
            for advice in advice_list:
                await self._store_investment_advice(advice)

            return advice_list

        except Exception as e:
            logger.error(f"Error generating investment advice: {e}")
            return []

    async def rebalance_portfolio(self, portfolio_id: str) -> RebalanceRecommendation:
        """Generate portfolio rebalancing recommendation."""
        try:
            portfolio = self.portfolios.get(portfolio_id)
            if not portfolio:
                portfolio = await self._load_portfolio(portfolio_id)

            if not portfolio:
                raise ValueError(f"Portfolio {portfolio_id} not found")

            # Calculate current allocation
            current_allocation = self._calculate_current_allocation(portfolio)

            # Get updated target allocation
            profile = await self._get_investor_profile(portfolio.user_id)
            assets = [holding.asset for holding in portfolio.holdings]
            returns_data = self._prepare_returns_data(assets)

            target_allocation = self.optimizer.optimize_portfolio(
                assets, returns_data, profile.risk_tolerance
            )

            # Calculate rebalancing trades
            trades = self._calculate_rebalancing_trades(
                portfolio, current_allocation, target_allocation
            )

            # Estimate costs
            expected_cost = self._estimate_rebalancing_cost(trades)

            # Determine urgency
            urgency = self._assess_rebalancing_urgency(
                current_allocation, target_allocation
            )

            # Create recommendation
            recommendation = RebalanceRecommendation(
                portfolio_id=portfolio_id,
                timestamp=datetime.now(),
                current_allocation=current_allocation,
                target_allocation=target_allocation,
                trades=trades,
                expected_cost=expected_cost,
                rationale=self._generate_rebalancing_rationale(
                    current_allocation, target_allocation
                ),
                urgency=urgency,
                estimated_impact=self._estimate_rebalancing_impact(trades),
            )

            # Store recommendation
            await self._store_rebalance_recommendation(recommendation)

            return recommendation

        except Exception as e:
            logger.error(f"Error in portfolio rebalancing: {e}")
            raise

    def _select_assets_for_profile(self, profile: InvestorProfile) -> list[Asset]:
        """Select appropriate assets based on investor profile."""
        # Base asset classes
        asset_classes = [AssetClass.EQUITY, AssetClass.FIXED_INCOME]

        # Add additional asset classes based on risk profile
        if profile.risk_tolerance in [
            RiskProfile.MODERATE_AGGRESSIVE,
            RiskProfile.AGGRESSIVE,
        ]:
            asset_classes.extend([AssetClass.REAL_ESTATE, AssetClass.COMMODITIES])

        # ESG filter
        esg_rating = ESGRating.GOOD if profile.esg_preference else None

        # Get filtered assets
        assets = self.asset_manager.get_assets_by_criteria(
            asset_classes=asset_classes, esg_rating=esg_rating, max_expense_ratio=0.5
        )

        return assets[:12]  # Limit to 12 assets for diversification

    def _prepare_returns_data(self, assets: list[Asset]) -> pd.DataFrame:
        """Prepare returns data for optimization."""
        returns_data = {}

        for asset in assets:
            if asset.symbol in self.asset_manager.asset_data:
                returns_data[asset.symbol] = self.asset_manager.asset_data[
                    asset.symbol
                ]["returns"]

        if returns_data:
            return pd.DataFrame(returns_data).dropna()
        else:
            # Generate synthetic returns for demonstration
            np.random.seed(42)
            dates = pd.date_range(start="2023-01-01", end="2024-01-01", freq="D")
            synthetic_returns = {}

            for asset in assets:
                # Generate returns based on asset class
                if asset.asset_class == AssetClass.EQUITY:
                    returns = np.random.normal(
                        0.0008, 0.02, len(dates)
                    )  # Higher volatility
                elif asset.asset_class == AssetClass.FIXED_INCOME:
                    returns = np.random.normal(
                        0.0002, 0.005, len(dates)
                    )  # Lower volatility
                else:
                    returns = np.random.normal(
                        0.0005, 0.015, len(dates)
                    )  # Medium volatility

                synthetic_returns[asset.symbol] = returns

            return pd.DataFrame(synthetic_returns, index=dates)

    def _create_holdings(
        self, assets: list[Asset], allocation: dict[str, float], total_value: float
    ) -> list[PortfolioHolding]:
        """Create portfolio holdings from allocation."""
        holdings = []

        for asset in assets:
            if asset.symbol in allocation:
                weight = allocation[asset.symbol]
                market_value = total_value * weight

                holding = PortfolioHolding(
                    asset=asset,
                    weight=weight,
                    market_value=market_value,
                    cost_basis=market_value,
                    shares=market_value / 100,  # Simplified share calculation
                )

                holdings.append(holding)

        return holdings

    def _calculate_portfolio_risk_metrics(
        self, portfolio: Portfolio, returns_data: pd.DataFrame
    ) -> dict[str, float]:
        """Calculate portfolio risk metrics."""
        try:
            # Get portfolio weights
            weights = np.array([holding.weight for holding in portfolio.holdings])
            symbols = [holding.asset.symbol for holding in portfolio.holdings]

            # Filter returns data
            portfolio_returns = returns_data[symbols]

            if portfolio_returns.empty:
                return {}

            # Calculate portfolio returns
            portfolio_return_series = (portfolio_returns * weights).sum(axis=1)

            # Risk metrics
            volatility = portfolio_return_series.std() * np.sqrt(252)
            sharpe_ratio = (
                (portfolio_return_series.mean() * 252) / volatility
                if volatility > 0
                else 0
            )
            max_drawdown = self._calculate_max_drawdown(portfolio_return_series)
            var_95 = np.percentile(portfolio_return_series, 5)

            return {
                "volatility": volatility,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "var_95": var_95,
                "beta": self._calculate_portfolio_beta(
                    portfolio_return_series, returns_data
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {}

    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()

    def _calculate_portfolio_beta(
        self, portfolio_returns: pd.Series, market_returns: pd.DataFrame
    ) -> float:
        """Calculate portfolio beta against market."""
        try:
            # Use first asset as market proxy (simplified)
            if not market_returns.empty:
                market_proxy = market_returns.iloc[:, 0]
                covariance = np.cov(portfolio_returns, market_proxy)[0, 1]
                market_variance = np.var(market_proxy)
                return covariance / market_variance if market_variance > 0 else 1.0
            return 1.0
        except:
            return 1.0

    def _calculate_portfolio_esg_score(self, portfolio: Portfolio) -> float:
        """Calculate weighted ESG score for portfolio."""
        total_score = 0.0
        total_weight = 0.0

        esg_score_map = {
            ESGRating.EXCELLENT: 5.0,
            ESGRating.GOOD: 4.0,
            ESGRating.AVERAGE: 3.0,
            ESGRating.POOR: 2.0,
            ESGRating.NOT_RATED: 0.0,
        }

        for holding in portfolio.holdings:
            if holding.asset.esg_rating != ESGRating.NOT_RATED:
                score = esg_score_map.get(holding.asset.esg_rating, 0.0)
                total_score += score * holding.weight
                total_weight += holding.weight

        return total_score / total_weight if total_weight > 0 else 0.0

    async def _generate_market_outlook_advice(
        self, profile: InvestorProfile
    ) -> InvestmentAdvice | None:
        """Generate market outlook advice."""
        try:
            # Simplified market analysis
            advice_content = f"""
            Based on current market conditions and your {profile.risk_tolerance.value} risk profile:

            • Market volatility remains elevated, suggesting a cautious approach
            • Diversification across asset classes continues to be important
            • Consider maintaining {20 + profile.age}% allocation to bonds for stability
            • ESG investments show strong momentum and align with long-term trends
            """

            return InvestmentAdvice(
                advice_id=f"market_outlook_{profile.user_id}_{datetime.now().strftime('%Y%m%d')}",
                user_id=profile.user_id,
                advice_type="market_outlook",
                title="Current Market Outlook",
                content=advice_content.strip(),
                confidence_score=0.75,
                supporting_data={
                    "market_volatility": 0.18,
                    "economic_indicators": "mixed",
                },
                action_items=[
                    "Review portfolio allocation",
                    "Consider rebalancing if significantly off-target",
                    "Maintain emergency fund",
                ],
            )

        except Exception as e:
            logger.error(f"Error generating market outlook advice: {e}")
            return None

    async def _generate_rebalancing_advice(
        self, user_id: str
    ) -> InvestmentAdvice | None:
        """Generate rebalancing advice."""
        # Implementation would analyze portfolio drift and recommend rebalancing
        return None

    async def _generate_tax_optimization_advice(
        self, profile: InvestorProfile
    ) -> InvestmentAdvice | None:
        """Generate tax optimization advice."""
        if profile.tax_status == "taxable":
            return InvestmentAdvice(
                advice_id=f"tax_opt_{profile.user_id}_{datetime.now().strftime('%Y%m%d')}",
                user_id=profile.user_id,
                advice_type="tax_optimization",
                title="Tax Optimization Opportunities",
                content="Consider tax-loss harvesting and municipal bonds for tax efficiency.",
                confidence_score=0.8,
                supporting_data={"tax_bracket": "estimated_high"},
                action_items=[
                    "Review tax-loss harvesting opportunities",
                    "Consider municipal bonds",
                ],
            )
        return None

    async def _generate_goal_tracking_advice(
        self, profile: InvestorProfile
    ) -> InvestmentAdvice | None:
        """Generate goal tracking advice."""
        # Implementation would track progress toward investment goals
        return None

    def _calculate_current_allocation(self, portfolio: Portfolio) -> dict[str, float]:
        """Calculate current portfolio allocation."""
        total_value = sum(holding.market_value for holding in portfolio.holdings)

        if total_value == 0:
            return {}

        return {
            holding.asset.symbol: holding.market_value / total_value
            for holding in portfolio.holdings
        }

    def _calculate_rebalancing_trades(
        self,
        portfolio: Portfolio,
        current_allocation: dict[str, float],
        target_allocation: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Calculate trades needed for rebalancing."""
        trades = []
        total_value = portfolio.total_value

        for symbol in target_allocation:
            current_weight = current_allocation.get(symbol, 0.0)
            target_weight = target_allocation[symbol]

            weight_diff = target_weight - current_weight

            if abs(weight_diff) > 0.01:  # 1% threshold
                trade_value = weight_diff * total_value

                trades.append(
                    {
                        "symbol": symbol,
                        "action": "buy" if trade_value > 0 else "sell",
                        "value": abs(trade_value),
                        "weight_change": weight_diff,
                    }
                )

        return trades

    def _estimate_rebalancing_cost(self, trades: list[dict[str, Any]]) -> float:
        """Estimate cost of rebalancing trades."""
        total_cost = 0.0

        for trade in trades:
            # Simplified cost calculation
            trade_cost = trade["value"] * 0.001  # 0.1% transaction cost
            total_cost += trade_cost

        return total_cost

    def _assess_rebalancing_urgency(
        self, current: dict[str, float], target: dict[str, float]
    ) -> str:
        """Assess urgency of rebalancing."""
        max_deviation = 0.0

        for symbol in target:
            current_weight = current.get(symbol, 0.0)
            target_weight = target[symbol]
            deviation = abs(current_weight - target_weight)
            max_deviation = max(max_deviation, deviation)

        if max_deviation > 0.1:  # 10%
            return "high"
        elif max_deviation > 0.05:  # 5%
            return "medium"
        else:
            return "low"

    def _generate_rebalancing_rationale(
        self, current: dict[str, float], target: dict[str, float]
    ) -> str:
        """Generate rationale for rebalancing."""
        deviations = []

        for symbol in target:
            current_weight = current.get(symbol, 0.0)
            target_weight = target[symbol]
            deviation = abs(current_weight - target_weight)

            if deviation > 0.02:  # 2% threshold
                deviations.append(f"{symbol}: {deviation:.1%} deviation")

        if deviations:
            return f"Rebalancing recommended due to: {', '.join(deviations[:3])}"
        else:
            return "Portfolio is well-balanced, minimal rebalancing needed"

    def _estimate_rebalancing_impact(
        self, trades: list[dict[str, Any]]
    ) -> dict[str, float]:
        """Estimate impact of rebalancing."""
        return {
            "expected_risk_reduction": 0.02,
            "expected_return_improvement": 0.005,
            "transaction_cost_impact": -0.001,
        }

    # Database operations
    async def _store_investor_profile(self, profile: InvestorProfile):
        """Store investor profile in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                """
                INSERT OR REPLACE INTO investor_profiles
                (user_id, age, income, net_worth, investment_experience, risk_tolerance,
                 investment_goals, time_horizon, liquidity_needs, esg_preference, tax_status,
                 investment_amount, monthly_contribution, risk_capacity, behavioral_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    profile.user_id,
                    profile.age,
                    profile.income,
                    profile.net_worth,
                    profile.investment_experience,
                    profile.risk_tolerance.value,
                    json.dumps([goal.value for goal in profile.investment_goals]),
                    profile.time_horizon,
                    profile.liquidity_needs,
                    profile.esg_preference,
                    profile.tax_status,
                    profile.investment_amount,
                    profile.monthly_contribution,
                    profile.risk_capacity,
                    profile.behavioral_score,
                    profile.created_at.isoformat(),
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing investor profile: {e}")

    async def _get_investor_profile(self, user_id: str) -> InvestorProfile | None:
        """Retrieve investor profile from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT * FROM investor_profiles WHERE user_id = ?", (user_id,)
            )

            row = cursor.fetchone()
            conn.close()

            if row:
                # Reconstruct profile from database row
                # This is a simplified version - full implementation would handle all fields
                return InvestorProfile(
                    user_id=row[0],
                    age=row[1],
                    income=row[2],
                    net_worth=row[3],
                    investment_experience=row[4],
                    risk_tolerance=RiskProfile(row[5]),
                    investment_goals=[
                        InvestmentGoal(goal) for goal in json.loads(row[6])
                    ],
                    time_horizon=row[7],
                    liquidity_needs=row[8],
                    esg_preference=bool(row[9]),
                    tax_status=row[10],
                    investment_amount=row[11],
                    monthly_contribution=row[12],
                    risk_capacity=row[13],
                    behavioral_score=row[14],
                )

            return None

        except Exception as e:
            logger.error(f"Error retrieving investor profile: {e}")
            return None

    async def _store_portfolio(self, portfolio: Portfolio):
        """Store portfolio in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Serialize complex data
            holdings_data = []
            for holding in portfolio.holdings:
                holdings_data.append(
                    {
                        "symbol": holding.asset.symbol,
                        "weight": holding.weight,
                        "shares": holding.shares,
                        "market_value": holding.market_value,
                        "cost_basis": holding.cost_basis,
                    }
                )

            conn.execute(
                """
                INSERT OR REPLACE INTO portfolios
                (portfolio_id, user_id, name, holdings, total_value, cash_balance,
                 target_allocation, actual_allocation, risk_metrics, performance_metrics,
                 esg_score, last_rebalanced, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    portfolio.portfolio_id,
                    portfolio.user_id,
                    portfolio.name,
                    json.dumps(holdings_data),
                    portfolio.total_value,
                    portfolio.cash_balance,
                    json.dumps(portfolio.target_allocation),
                    json.dumps(portfolio.actual_allocation),
                    json.dumps(portfolio.risk_metrics),
                    json.dumps(portfolio.performance_metrics),
                    portfolio.esg_score,
                    (
                        portfolio.last_rebalanced.isoformat()
                        if portfolio.last_rebalanced
                        else None
                    ),
                    portfolio.created_at.isoformat(),
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing portfolio: {e}")

    async def _load_portfolio(self, portfolio_id: str) -> Portfolio | None:
        """Load portfolio from database."""
        # Implementation would reconstruct portfolio from database
        return None

    async def _store_investment_advice(self, advice: InvestmentAdvice):
        """Store investment advice in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                """
                INSERT INTO investment_advice
                (advice_id, user_id, advice_type, title, content, confidence_score,
                 supporting_data, action_items, timestamp, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    advice.advice_id,
                    advice.user_id,
                    advice.advice_type,
                    advice.title,
                    advice.content,
                    advice.confidence_score,
                    json.dumps(advice.supporting_data),
                    json.dumps(advice.action_items),
                    advice.timestamp.isoformat(),
                    advice.acknowledged,
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing investment advice: {e}")

    async def _store_rebalance_recommendation(
        self, recommendation: RebalanceRecommendation
    ):
        """Store rebalancing recommendation in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                """
                INSERT INTO rebalance_recommendations
                (recommendation_id, portfolio_id, timestamp, current_allocation,
                 target_allocation, trades, expected_cost, rationale, urgency, estimated_impact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"rebal_{recommendation.portfolio_id}_{recommendation.timestamp.strftime('%Y%m%d')}",
                    recommendation.portfolio_id,
                    recommendation.timestamp.isoformat(),
                    json.dumps(recommendation.current_allocation),
                    json.dumps(recommendation.target_allocation),
                    json.dumps(recommendation.trades),
                    recommendation.expected_cost,
                    recommendation.rationale,
                    recommendation.urgency,
                    json.dumps(recommendation.estimated_impact),
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing rebalance recommendation: {e}")


# Example usage and testing
async def main():
    """Example usage of the Portfolio Management & Robo-Advisory Engine."""

    # Initialize robo-advisor
    robo_advisor = RoboAdvisorEngine()

    print("=" * 60)
    print("PORTFOLIO MANAGEMENT & ROBO-ADVISORY ENGINE")
    print("=" * 60)

    # Sample investor data
    user_id = "investor_001"

    # Questionnaire responses
    questionnaire_responses = {
        "age_retirement": 25,
        "investment_experience": "Some experience",
        "market_decline_reaction": "Hold and wait",
        "income_stability": "Very stable",
        "emergency_fund": "6-12 months",
        "investment_goal": "Capital appreciation",
        "loss_tolerance": "Up to 15% loss",
    }

    # Demographic data
    demographic_data = {
        "age": 32,
        "income": 85000,
        "net_worth": 200000,
        "investment_experience": "intermediate",
        "investment_goals": ["wealth_building", "retirement"],
        "time_horizon": 20,
        "liquidity_needs": 0.1,
        "esg_preference": True,
        "tax_status": "taxable",
        "investment_amount": 50000,
        "monthly_contribution": 1000,
    }

    try:
        # Step 1: Onboard investor
        print("\n1. INVESTOR ONBOARDING")
        print("-" * 30)

        profile = await robo_advisor.onboard_investor(
            user_id, questionnaire_responses, demographic_data
        )

        print(f"✓ Onboarded investor: {profile.user_id}")
        print(f"  Risk Profile: {profile.risk_tolerance.value}")
        print(
            f"  Investment Goals: {[goal.value for goal in profile.investment_goals]}"
        )
        print(f"  Time Horizon: {profile.time_horizon} years")
        print(f"  ESG Preference: {profile.esg_preference}")
        print(f"  Risk Capacity: {profile.risk_capacity:.2f}")

        # Step 2: Create optimized portfolio
        print("\n2. PORTFOLIO CREATION")
        print("-" * 30)

        portfolio = await robo_advisor.create_portfolio(user_id, "Growth Portfolio")

        print(f"✓ Created portfolio: {portfolio.portfolio_id}")
        print(f"  Total Value: ${portfolio.total_value:,.2f}")
        print(f"  Number of Holdings: {len(portfolio.holdings)}")
        print(f"  ESG Score: {portfolio.esg_score:.2f}/5.0")

        print("\n  Target Allocation:")
        for symbol, weight in portfolio.target_allocation.items():
            asset_name = next(
                (h.asset.name for h in portfolio.holdings if h.asset.symbol == symbol),
                symbol,
            )
            print(f"    {symbol} ({asset_name[:30]}): {weight:.1%}")

        print("\n  Risk Metrics:")
        for metric, value in portfolio.risk_metrics.items():
            print(f"    {metric.replace('_', ' ').title()}: {value:.3f}")

        # Step 3: Generate investment advice
        print("\n3. INVESTMENT ADVICE")
        print("-" * 30)

        advice_list = await robo_advisor.generate_investment_advice(user_id)

        for advice in advice_list:
            print(f"\n✓ {advice.title}")
            print(f"  Type: {advice.advice_type}")
            print(f"  Confidence: {advice.confidence_score:.1%}")
            print(f"  Content: {advice.content[:200]}...")
            if advice.action_items:
                print("  Action Items:")
                for item in advice.action_items[:3]:
                    print(f"    • {item}")

        # Step 4: Simulate portfolio drift and rebalancing
        print("\n4. PORTFOLIO REBALANCING")
        print("-" * 30)

        # Simulate some market movement (portfolio drift)
        for holding in portfolio.holdings:
            # Random market movement
            price_change = np.random.normal(0, 0.05)  # 5% volatility
            holding.market_value *= 1 + price_change

        # Update total value
        portfolio.total_value = sum(h.market_value for h in portfolio.holdings)

        # Generate rebalancing recommendation
        rebalance_rec = await robo_advisor.rebalance_portfolio(portfolio.portfolio_id)

        print("✓ Rebalancing Analysis Complete")
        print(f"  Urgency: {rebalance_rec.urgency}")
        print(f"  Expected Cost: ${rebalance_rec.expected_cost:.2f}")
        print(f"  Rationale: {rebalance_rec.rationale}")

        print("\n  Recommended Trades:")
        for trade in rebalance_rec.trades[:5]:  # Show first 5 trades
            print(
                f"    {trade['action'].upper()} {trade['symbol']}: "
                f"${trade['value']:,.2f} ({trade['weight_change']:+.1%})"
            )

        print("\n  Estimated Impact:")
        for metric, impact in rebalance_rec.estimated_impact.items():
            print(f"    {metric.replace('_', ' ').title()}: {impact:+.1%}")

        # Step 5: Performance summary
        print("\n5. PERFORMANCE SUMMARY")
        print("-" * 30)

        print(f"Portfolio Value: ${portfolio.total_value:,.2f}")
        print(f"Cash Balance: ${portfolio.cash_balance:,.2f}")
        print(f"ESG Score: {portfolio.esg_score:.2f}/5.0")

        if portfolio.risk_metrics:
            print(
                f"Portfolio Volatility: {portfolio.risk_metrics.get('volatility', 0):.1%}"
            )
            print(f"Sharpe Ratio: {portfolio.risk_metrics.get('sharpe_ratio', 0):.2f}")
            print(
                f"Maximum Drawdown: {portfolio.risk_metrics.get('max_drawdown', 0):.1%}"
            )

        print(f"\nAdvice Generated: {len(advice_list)} recommendations")
        print(
            f"Last Rebalancing Check: {rebalance_rec.timestamp.strftime('%Y-%m-%d %H:%M')}"
        )

    except Exception as e:
        print(f"Error in robo-advisor demo: {e}")
        logger.error(f"Demo error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
