"""
Economic Indicators & Macro Analysis Engine

This module provides comprehensive economic indicators analysis, macro-economic modeling,
scenario analysis, and forecasting capabilities for financial platforms. It integrates
with multiple economic data sources and provides advanced analytical tools.
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

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yfinance as yf
from scipy import stats
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.vector_ar.var_model import VAR

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class IndicatorType(Enum):
    """Economic indicator types."""

    GROWTH = "growth"
    INFLATION = "inflation"
    EMPLOYMENT = "employment"
    MONETARY = "monetary"
    FISCAL = "fiscal"
    TRADE = "trade"
    CONSUMER = "consumer"
    BUSINESS = "business"
    HOUSING = "housing"
    FINANCIAL = "financial"
    COMMODITY = "commodity"
    MARKET = "market"


class IndicatorFrequency(Enum):
    """Data frequency types."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class TrendDirection(Enum):
    """Trend direction classifications."""

    STRONGLY_RISING = "strongly_rising"
    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"
    STRONGLY_DECLINING = "strongly_declining"


class EconomicRegime(Enum):
    """Economic regime classifications."""

    EXPANSION = "expansion"
    PEAK = "peak"
    RECESSION = "recession"
    TROUGH = "trough"
    RECOVERY = "recovery"
    STAGFLATION = "stagflation"
    DEFLATION = "deflation"


class RiskLevel(Enum):
    """Risk level classifications."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class EconomicIndicator:
    """Economic indicator data structure."""

    indicator_id: str
    name: str
    indicator_type: IndicatorType
    frequency: IndicatorFrequency
    unit: str
    source: str
    description: str
    data: pd.Series
    last_updated: datetime = field(default_factory=datetime.now)
    seasonal_adjustment: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendAnalysis:
    """Trend analysis result."""

    indicator_id: str
    trend_direction: TrendDirection
    trend_strength: float
    change_rate: float
    momentum: float
    volatility: float
    confidence_level: float
    breakpoints: list[datetime] = field(default_factory=list)
    forecast: pd.Series | None = None


@dataclass
class CorrelationAnalysis:
    """Correlation analysis between indicators."""

    indicator_pairs: list[tuple[str, str]]
    correlation_matrix: np.ndarray
    lag_correlations: dict[tuple[str, str], dict[int, float]]
    granger_causality: dict[tuple[str, str], dict[str, float]]
    cointegration_tests: dict[tuple[str, str], dict[str, Any]]


@dataclass
class EconomicScenario:
    """Economic scenario definition."""

    scenario_id: str
    name: str
    description: str
    probability: float
    key_assumptions: dict[str, Any]
    indicator_projections: dict[str, pd.Series]
    risk_factors: list[str]
    market_implications: dict[str, str]
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class MacroForecast:
    """Macroeconomic forecast result."""

    forecast_id: str
    forecast_horizon: int  # months
    base_scenario: EconomicScenario
    alternative_scenarios: list[EconomicScenario]
    key_metrics: dict[str, float]
    confidence_intervals: dict[str, tuple[float, float]]
    risk_assessment: dict[str, RiskLevel]
    policy_implications: list[str]
    generated_at: datetime = field(default_factory=datetime.now)


class EconomicDataProvider:
    """Economic data provider interface with multiple sources."""

    def __init__(self):
        self.cache = {}
        self.cache_expiry = timedelta(hours=6)
        self.fred_api_key = None  # Set your FRED API key
        self.bea_api_key = None  # Set your BEA API key

    async def get_fred_data(
        self, series_id: str, start_date: datetime, end_date: datetime
    ) -> pd.Series:
        """Get data from FRED (Federal Reserve Economic Data)."""
        try:
            cache_key = f"fred_{series_id}_{start_date}_{end_date}"

            # Check cache
            if cache_key in self.cache:
                cached_time, data = self.cache[cache_key]
                if datetime.now() - cached_time < self.cache_expiry:
                    return data

            # Simulate FRED API call (replace with actual API implementation)
            {
                "series_id": series_id,
                "api_key": self.fred_api_key or "demo_key",
                "file_type": "json",
                "observation_start": start_date.strftime("%Y-%m-%d"),
                "observation_end": end_date.strftime("%Y-%m-%d"),
            }

            # For demo, generate synthetic data
            dates = pd.date_range(start=start_date, end=end_date, freq="M")

            # Generate realistic economic data patterns
            if "GDP" in series_id.upper():
                # GDP-like data (quarterly growth)
                base_value = 20000
                trend = np.linspace(0, len(dates) * 0.02, len(dates))
                cycle = 0.01 * np.sin(2 * np.pi * np.arange(len(dates)) / 40)
                noise = np.random.normal(0, 0.005, len(dates))
                values = base_value * (1 + trend + cycle + noise)

            elif "INFLATION" in series_id.upper() or "CPI" in series_id.upper():
                # Inflation-like data
                base_value = 100
                trend = np.linspace(0, len(dates) * 0.02, len(dates))
                values = base_value * np.exp(
                    trend + np.random.normal(0, 0.01, len(dates))
                )

            elif "UNEMPLOYMENT" in series_id.upper():
                # Unemployment rate data
                base_rate = 5.0
                cycle = 2.0 * np.sin(2 * np.pi * np.arange(len(dates)) / 60)
                noise = np.random.normal(0, 0.3, len(dates))
                values = np.maximum(1.0, base_rate + cycle + noise)

            elif "RATE" in series_id.upper():
                # Interest rate data
                base_rate = 2.0
                trend = np.linspace(0, 3.0, len(dates))
                noise = np.random.normal(0, 0.2, len(dates))
                values = np.maximum(0, base_rate + trend + noise)

            else:
                # Generic economic indicator
                values = 100 + np.cumsum(np.random.normal(0.1, 1.0, len(dates)))

            data = pd.Series(values, index=dates, name=series_id)

            # Cache data
            self.cache[cache_key] = (datetime.now(), data)

            return data

        except Exception as e:
            logger.error(f"Error fetching FRED data for {series_id}: {e}")
            return pd.Series(dtype=float)

    async def get_bea_data(
        self, dataset: str, table: str, start_year: int, end_year: int
    ) -> pd.DataFrame:
        """Get data from BEA (Bureau of Economic Analysis)."""
        try:
            # Simulate BEA API call
            years = range(start_year, end_year + 1)

            if dataset.upper() == "NIPA":  # National Income and Product Accounts
                # Generate GDP components data
                data = {}
                for year in years:
                    data[year] = {
                        "GDP": 20000 + year * 500 + np.random.normal(0, 200),
                        "Consumption": 14000 + year * 300 + np.random.normal(0, 150),
                        "Investment": 3500 + year * 100 + np.random.normal(0, 100),
                        "Government": 3500 + year * 50 + np.random.normal(0, 50),
                        "NetExports": -1000 + year * 10 + np.random.normal(0, 50),
                    }

                df = pd.DataFrame(data).T
                df.index.name = "Year"
                return df

            else:
                # Generic economic data
                data = {}
                for year in years:
                    data[year] = {"Value": 1000 + year * 20 + np.random.normal(0, 50)}

                df = pd.DataFrame(data).T
                df.index.name = "Year"
                return df

        except Exception as e:
            logger.error(f"Error fetching BEA data: {e}")
            return pd.DataFrame()

    async def get_market_data(
        self, symbols: list[str], start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Get market data for economic analysis."""
        try:
            # Market indicators relevant to economic analysis
            market_data = {}

            for symbol in symbols:
                if symbol == "^VIX":
                    # VIX (volatility index)
                    dates = pd.date_range(start=start_date, end=end_date, freq="D")
                    base_vix = 20
                    values = np.maximum(
                        10, base_vix + np.random.normal(0, 5, len(dates))
                    )
                    market_data[symbol] = pd.Series(values, index=dates)

                elif symbol == "^TNX":
                    # 10-year Treasury yield
                    dates = pd.date_range(start=start_date, end=end_date, freq="D")
                    base_yield = 2.5
                    trend = np.linspace(0, 1.0, len(dates))
                    values = base_yield + trend + np.random.normal(0, 0.1, len(dates))
                    market_data[symbol] = pd.Series(values, index=dates)

                else:
                    # Use yfinance for actual market data
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(start=start_date, end=end_date)
                    if not hist.empty:
                        market_data[symbol] = hist["Close"]

            return pd.DataFrame(market_data)

        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return pd.DataFrame()


class TrendAnalyzer:
    """Advanced trend analysis for economic indicators."""

    def __init__(self):
        self.min_periods = 12  # Minimum periods for trend analysis

    async def analyze_trend(
        self, indicator: EconomicIndicator, lookback_periods: int = 24
    ) -> TrendAnalysis:
        """Perform comprehensive trend analysis on an economic indicator."""
        try:
            data = indicator.data.dropna().tail(lookback_periods)

            if len(data) < self.min_periods:
                raise ValueError(
                    f"Insufficient data for trend analysis: {len(data)} periods"
                )

            # Calculate trend direction and strength
            trend_direction, trend_strength = self._calculate_trend_direction(data)

            # Calculate change rate (annualized)
            change_rate = self._calculate_change_rate(data, indicator.frequency)

            # Calculate momentum
            momentum = self._calculate_momentum(data)

            # Calculate volatility
            volatility = self._calculate_volatility(data)

            # Detect structural breaks
            breakpoints = self._detect_breakpoints(data)

            # Calculate confidence level
            confidence_level = self._calculate_confidence(data, trend_strength)

            # Generate forecast
            forecast = await self._generate_trend_forecast(data, periods=6)

            return TrendAnalysis(
                indicator_id=indicator.indicator_id,
                trend_direction=trend_direction,
                trend_strength=trend_strength,
                change_rate=change_rate,
                momentum=momentum,
                volatility=volatility,
                confidence_level=confidence_level,
                breakpoints=breakpoints,
                forecast=forecast,
            )

        except Exception as e:
            logger.error(f"Error in trend analysis for {indicator.indicator_id}: {e}")
            raise

    def _calculate_trend_direction(
        self, data: pd.Series
    ) -> tuple[TrendDirection, float]:
        """Calculate trend direction and strength using multiple methods."""
        # Linear regression trend
        x = np.arange(len(data))
        y = data.values
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        # Normalize slope by data scale
        normalized_slope = slope / (data.mean() / len(data))

        # Calculate trend strength (R-squared)
        trend_strength = r_value**2

        # Classify trend direction
        if abs(normalized_slope) < 0.001:
            direction = TrendDirection.STABLE
        elif normalized_slope >= 0.005:
            direction = TrendDirection.STRONGLY_RISING
        elif normalized_slope >= 0.001:
            direction = TrendDirection.RISING
        elif normalized_slope <= -0.005:
            direction = TrendDirection.STRONGLY_DECLINING
        else:
            direction = TrendDirection.DECLINING

        return direction, trend_strength

    def _calculate_change_rate(
        self, data: pd.Series, frequency: IndicatorFrequency
    ) -> float:
        """Calculate annualized change rate."""
        if len(data) < 2:
            return 0.0

        # Calculate compound annual growth rate (CAGR)
        start_value = data.iloc[0]
        end_value = data.iloc[-1]

        if start_value <= 0:
            return 0.0

        periods_per_year = {
            IndicatorFrequency.MONTHLY: 12,
            IndicatorFrequency.QUARTERLY: 4,
            IndicatorFrequency.ANNUALLY: 1,
            IndicatorFrequency.WEEKLY: 52,
            IndicatorFrequency.DAILY: 252,
        }

        freq_multiplier = periods_per_year.get(frequency, 12)
        years = len(data) / freq_multiplier

        if years <= 0:
            return 0.0

        cagr = (end_value / start_value) ** (1 / years) - 1
        return cagr

    def _calculate_momentum(self, data: pd.Series) -> float:
        """Calculate momentum using rate of change."""
        if len(data) < 4:
            return 0.0

        # 3-month momentum vs 6-month momentum
        short_periods = min(3, len(data) // 3)
        long_periods = min(6, len(data) // 2)

        short_change = (
            (data.iloc[-1] / data.iloc[-short_periods] - 1)
            if data.iloc[-short_periods] != 0
            else 0
        )
        long_change = (
            (data.iloc[-1] / data.iloc[-long_periods] - 1)
            if data.iloc[-long_periods] != 0
            else 0
        )

        momentum = short_change - long_change
        return momentum

    def _calculate_volatility(self, data: pd.Series) -> float:
        """Calculate volatility using rolling standard deviation."""
        returns = data.pct_change().dropna()
        if len(returns) < 2:
            return 0.0

        volatility = returns.std()
        return volatility

    def _detect_breakpoints(self, data: pd.Series) -> list[datetime]:
        """Detect structural breakpoints in the time series."""
        breakpoints = []

        if len(data) < 20:  # Need sufficient data for breakpoint detection
            return breakpoints

        # Simple change-point detection using rolling correlation
        window = min(10, len(data) // 4)

        for i in range(window, len(data) - window):
            before = data.iloc[i - window : i]
            after = data.iloc[i : i + window]

            # Test for significant change in mean
            t_stat, p_value = stats.ttest_ind(before, after)

            if p_value < 0.05:  # Significant change
                breakpoints.append(data.index[i])

        return breakpoints

    def _calculate_confidence(self, data: pd.Series, trend_strength: float) -> float:
        """Calculate confidence level for trend analysis."""
        # Base confidence on trend strength and data quality
        base_confidence = trend_strength

        # Adjust for data length
        length_factor = min(1.0, len(data) / 24)

        # Adjust for data consistency (fewer missing values = higher confidence)
        consistency_factor = 1.0 - (data.isna().sum() / len(data))

        confidence = base_confidence * length_factor * consistency_factor
        return min(confidence, 1.0)

    async def _generate_trend_forecast(
        self, data: pd.Series, periods: int = 6
    ) -> pd.Series:
        """Generate simple trend-based forecast."""
        try:
            # Fit ARIMA model for forecasting
            model = ARIMA(data, order=(1, 1, 1))
            fitted_model = model.fit()

            # Generate forecast
            forecast = fitted_model.forecast(steps=periods)

            # Create future dates
            last_date = data.index[-1]
            future_dates = pd.date_range(
                start=last_date + (last_date - data.index[-2]),
                periods=periods,
                freq=pd.infer_freq(data.index),
            )

            forecast_series = pd.Series(forecast, index=future_dates)
            return forecast_series

        except Exception as e:
            logger.warning(f"Error generating forecast: {e}")
            # Fallback to linear extrapolation
            x = np.arange(len(data))
            y = data.values
            slope, intercept = np.polyfit(x, y, 1)

            future_x = np.arange(len(data), len(data) + periods)
            future_y = slope * future_x + intercept

            last_date = data.index[-1]
            future_dates = pd.date_range(
                start=last_date + (last_date - data.index[-2]),
                periods=periods,
                freq=pd.infer_freq(data.index) or "M",
            )

            return pd.Series(future_y, index=future_dates)


class CorrelationAnalyzer:
    """Advanced correlation and causality analysis between economic indicators."""

    def __init__(self):
        self.max_lags = 12

    async def analyze_correlations(
        self, indicators: list[EconomicIndicator], max_lags: int = 12
    ) -> CorrelationAnalysis:
        """Perform comprehensive correlation analysis between indicators."""
        try:
            # Prepare data
            data_dict = {}
            for indicator in indicators:
                data_dict[indicator.indicator_id] = indicator.data

            df = pd.DataFrame(data_dict).dropna()

            if df.empty or len(df.columns) < 2:
                raise ValueError("Insufficient data for correlation analysis")

            # Calculate correlation matrix
            corr_matrix = df.corr().values

            # Calculate lag correlations
            lag_correlations = await self._calculate_lag_correlations(df, max_lags)

            # Perform Granger causality tests
            granger_results = await self._granger_causality_tests(df)

            # Test for cointegration
            cointegration_results = await self._cointegration_tests(df)

            # Create indicator pairs
            indicator_pairs = []
            n_indicators = len(indicators)
            for i in range(n_indicators):
                for j in range(i + 1, n_indicators):
                    pair = (indicators[i].indicator_id, indicators[j].indicator_id)
                    indicator_pairs.append(pair)

            return CorrelationAnalysis(
                indicator_pairs=indicator_pairs,
                correlation_matrix=corr_matrix,
                lag_correlations=lag_correlations,
                granger_causality=granger_results,
                cointegration_tests=cointegration_results,
            )

        except Exception as e:
            logger.error(f"Error in correlation analysis: {e}")
            raise

    async def _calculate_lag_correlations(
        self, df: pd.DataFrame, max_lags: int
    ) -> dict[tuple[str, str], dict[int, float]]:
        """Calculate cross-correlations at different lags."""
        lag_correlations = {}

        columns = df.columns.tolist()
        for i, col1 in enumerate(columns):
            for j, col2 in enumerate(columns):
                if i != j:
                    pair = (col1, col2)
                    lag_correlations[pair] = {}

                    series1 = df[col1].dropna()
                    series2 = df[col2].dropna()

                    # Align series
                    common_index = series1.index.intersection(series2.index)
                    series1 = series1.loc[common_index]
                    series2 = series2.loc[common_index]

                    for lag in range(max_lags + 1):
                        if len(series1) > lag and len(series2) > lag:
                            if lag == 0:
                                corr = series1.corr(series2)
                            else:
                                # series1 leads series2 by lag periods
                                corr = series1.iloc[:-lag].corr(series2.iloc[lag:])

                            lag_correlations[pair][lag] = (
                                corr if not np.isnan(corr) else 0.0
                            )

        return lag_correlations

    async def _granger_causality_tests(
        self, df: pd.DataFrame
    ) -> dict[tuple[str, str], dict[str, float]]:
        """Perform Granger causality tests between pairs of variables."""
        granger_results = {}

        columns = df.columns.tolist()
        for i, col1 in enumerate(columns):
            for j, col2 in enumerate(columns):
                if i != j:
                    pair = (col1, col2)

                    try:
                        # Prepare data for VAR model
                        series1 = df[col1].dropna()
                        series2 = df[col2].dropna()

                        # Align series
                        common_index = series1.index.intersection(series2.index)
                        if len(common_index) < 20:  # Need sufficient data
                            continue

                        var_data = pd.DataFrame(
                            {
                                col1: series1.loc[common_index],
                                col2: series2.loc[common_index],
                            }
                        ).dropna()

                        if len(var_data) < 20:
                            continue

                        # Fit VAR model
                        model = VAR(var_data)
                        lag_order = model.select_order(
                            maxlags=min(4, len(var_data) // 5)
                        )
                        optimal_lags = lag_order.aic

                        fitted_model = model.fit(optimal_lags)

                        # Test if col1 Granger-causes col2
                        causality_test = fitted_model.test_causality(
                            col2, [col1], kind="f"
                        )

                        granger_results[pair] = {
                            "f_statistic": causality_test.statistic,
                            "p_value": causality_test.pvalue,
                            "critical_value": causality_test.critical_value,
                            "lags_used": optimal_lags,
                        }

                    except Exception as e:
                        logger.warning(f"Granger causality test failed for {pair}: {e}")
                        granger_results[pair] = {
                            "f_statistic": np.nan,
                            "p_value": np.nan,
                            "critical_value": np.nan,
                            "lags_used": 0,
                        }

        return granger_results

    async def _cointegration_tests(
        self, df: pd.DataFrame
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """Test for cointegration between pairs of variables."""
        cointegration_results = {}

        columns = df.columns.tolist()
        for i, col1 in enumerate(columns):
            for j, col2 in enumerate(columns):
                if i < j:  # Avoid duplicate pairs
                    pair = (col1, col2)

                    try:
                        series1 = df[col1].dropna()
                        series2 = df[col2].dropna()

                        # Align series
                        common_index = series1.index.intersection(series2.index)
                        if len(common_index) < 20:
                            continue

                        series1 = series1.loc[common_index]
                        series2 = series2.loc[common_index]

                        # Engle-Granger cointegration test
                        # Step 1: Test for unit roots (simplified)
                        from statsmodels.tsa.stattools import adfuller

                        adf1 = adfuller(series1)
                        adf2 = adfuller(series2)

                        # Step 2: If both series are I(1), test cointegration
                        if adf1[1] > 0.05 and adf2[1] > 0.05:  # Both non-stationary
                            # Run cointegration regression
                            X = sm.add_constant(series1.values)
                            y = series2.values
                            model = sm.OLS(y, X).fit()

                            # Test residuals for stationarity
                            residuals = model.resid
                            adf_residuals = adfuller(residuals)

                            cointegration_results[pair] = {
                                "cointegrated": adf_residuals[1] < 0.05,
                                "adf_statistic": adf_residuals[0],
                                "p_value": adf_residuals[1],
                                "critical_values": adf_residuals[4],
                                "beta_coefficient": model.params[1],
                                "r_squared": model.rsquared,
                            }
                        else:
                            cointegration_results[pair] = {
                                "cointegrated": False,
                                "reason": "One or both series are stationary",
                            }

                    except Exception as e:
                        logger.warning(f"Cointegration test failed for {pair}: {e}")
                        cointegration_results[pair] = {
                            "cointegrated": False,
                            "error": str(e),
                        }

        return cointegration_results


class ScenarioGenerator:
    """Generate economic scenarios for stress testing and forecasting."""

    def __init__(self):
        self.scenario_templates = self._load_scenario_templates()

    def _load_scenario_templates(self) -> dict[str, dict]:
        """Load predefined scenario templates."""
        return {
            "base_case": {
                "name": "Base Case",
                "description": "Most likely economic outcome based on current trends",
                "probability": 0.5,
                "gdp_growth": 0.02,
                "inflation_rate": 0.025,
                "unemployment_rate": 0.05,
                "interest_rate_change": 0.0,
            },
            "recession": {
                "name": "Economic Recession",
                "description": "Significant economic downturn scenario",
                "probability": 0.15,
                "gdp_growth": -0.03,
                "inflation_rate": 0.01,
                "unemployment_rate": 0.08,
                "interest_rate_change": -0.02,
            },
            "inflation_surge": {
                "name": "High Inflation",
                "description": "Persistent high inflation scenario",
                "probability": 0.20,
                "gdp_growth": 0.01,
                "inflation_rate": 0.06,
                "unemployment_rate": 0.06,
                "interest_rate_change": 0.03,
            },
            "strong_growth": {
                "name": "Strong Economic Growth",
                "description": "Above-trend economic expansion",
                "probability": 0.15,
                "gdp_growth": 0.04,
                "inflation_rate": 0.03,
                "unemployment_rate": 0.04,
                "interest_rate_change": 0.01,
            },
        }

    async def generate_scenarios(
        self, base_indicators: list[EconomicIndicator], horizon_months: int = 12
    ) -> list[EconomicScenario]:
        """Generate economic scenarios based on current indicators."""
        scenarios = []

        for scenario_id, template in self.scenario_templates.items():
            scenario = await self._create_scenario_from_template(
                scenario_id, template, base_indicators, horizon_months
            )
            scenarios.append(scenario)

        return scenarios

    async def _create_scenario_from_template(
        self,
        scenario_id: str,
        template: dict,
        base_indicators: list[EconomicIndicator],
        horizon_months: int,
    ) -> EconomicScenario:
        """Create a scenario from a template."""

        # Generate projections for each indicator
        indicator_projections = {}

        for indicator in base_indicators:
            projection = await self._project_indicator(
                indicator, template, horizon_months
            )
            indicator_projections[indicator.indicator_id] = projection

        # Generate risk factors
        risk_factors = self._identify_risk_factors(template)

        # Generate market implications
        market_implications = self._generate_market_implications(template)

        return EconomicScenario(
            scenario_id=scenario_id,
            name=template["name"],
            description=template["description"],
            probability=template["probability"],
            key_assumptions=template,
            indicator_projections=indicator_projections,
            risk_factors=risk_factors,
            market_implications=market_implications,
        )

    async def _project_indicator(
        self, indicator: EconomicIndicator, scenario_template: dict, horizon_months: int
    ) -> pd.Series:
        """Project an indicator under a specific scenario."""

        if indicator.data.empty:
            return pd.Series(dtype=float)

        # Get last value
        last_value = indicator.data.iloc[-1]
        last_date = indicator.data.index[-1]

        # Generate future dates
        future_dates = pd.date_range(
            start=last_date + pd.DateOffset(months=1), periods=horizon_months, freq="M"
        )

        # Apply scenario adjustments based on indicator type
        if indicator.indicator_type == IndicatorType.GROWTH:
            growth_rate = scenario_template.get("gdp_growth", 0.02)
            monthly_growth = (1 + growth_rate) ** (1 / 12) - 1
            projections = [
                last_value * (1 + monthly_growth) ** (i + 1)
                for i in range(horizon_months)
            ]

        elif indicator.indicator_type == IndicatorType.INFLATION:
            inflation_rate = scenario_template.get("inflation_rate", 0.025)
            monthly_inflation = inflation_rate / 12
            projections = [
                last_value + monthly_inflation * (i + 1) for i in range(horizon_months)
            ]

        elif indicator.indicator_type == IndicatorType.EMPLOYMENT:
            target_unemployment = scenario_template.get("unemployment_rate", 0.05) * 100
            adjustment_speed = 0.1  # 10% adjustment per month
            projections = []
            current_value = last_value

            for _i in range(horizon_months):
                adjustment = (target_unemployment - current_value) * adjustment_speed
                current_value += adjustment
                projections.append(current_value)

        elif indicator.indicator_type == IndicatorType.MONETARY:
            rate_change = scenario_template.get("interest_rate_change", 0.0)
            monthly_change = rate_change / horizon_months
            projections = [
                last_value + monthly_change * (i + 1) for i in range(horizon_months)
            ]

        else:
            # Default projection (maintain current trend with scenario adjustment)
            recent_trend = indicator.data.pct_change().tail(6).mean()
            scenario_adjustment = 1 + scenario_template.get("gdp_growth", 0.02) / 12

            projections = []
            current_value = last_value

            for _i in range(horizon_months):
                current_value *= (1 + recent_trend) * scenario_adjustment
                projections.append(current_value)

        return pd.Series(projections, index=future_dates)

    def _identify_risk_factors(self, template: dict) -> list[str]:
        """Identify key risk factors for a scenario."""
        risk_factors = []

        if template.get("gdp_growth", 0) < -0.01:
            risk_factors.extend(
                [
                    "Corporate earnings decline",
                    "Rising credit defaults",
                    "Increased financial market volatility",
                ]
            )

        if template.get("inflation_rate", 0) > 0.04:
            risk_factors.extend(
                [
                    "Central bank aggressive tightening",
                    "Currency devaluation pressure",
                    "Wage-price spiral risk",
                ]
            )

        if template.get("unemployment_rate", 0) > 0.07:
            risk_factors.extend(
                [
                    "Consumer spending reduction",
                    "Social and political instability",
                    "Government fiscal strain",
                ]
            )

        return risk_factors

    def _generate_market_implications(self, template: dict) -> dict[str, str]:
        """Generate market implications for a scenario."""
        implications = {}

        # Equity markets
        if template.get("gdp_growth", 0) > 0.03:
            implications["equities"] = "Positive for growth-oriented stocks"
        elif template.get("gdp_growth", 0) < -0.01:
            implications["equities"] = "Significant downside risk for equities"
        else:
            implications["equities"] = "Mixed performance expected"

        # Bond markets
        if template.get("inflation_rate", 0) > 0.04:
            implications["bonds"] = "Negative for long-term bonds"
        elif template.get("gdp_growth", 0) < -0.01:
            implications["bonds"] = "Flight to quality benefits government bonds"
        else:
            implications["bonds"] = "Stable performance for high-quality bonds"

        # Currency
        if template.get("interest_rate_change", 0) > 0.02:
            implications["currency"] = "Supportive for domestic currency"
        elif template.get("gdp_growth", 0) < -0.02:
            implications["currency"] = "Downward pressure on currency"
        else:
            implications["currency"] = "Neutral currency impact"

        return implications


class MacroAnalysisEngine:
    """Main macroeconomic analysis engine."""

    def __init__(self):
        self.data_provider = EconomicDataProvider()
        self.trend_analyzer = TrendAnalyzer()
        self.correlation_analyzer = CorrelationAnalyzer()
        self.scenario_generator = ScenarioGenerator()
        self.indicators = {}
        self.db_path = "macro_analysis.db"
        self._setup_database()

    def _setup_database(self):
        """Setup macro analysis database."""
        conn = sqlite3.connect(self.db_path)

        # Economic indicators table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS economic_indicators (
                indicator_id TEXT PRIMARY KEY,
                name TEXT,
                indicator_type TEXT,
                frequency TEXT,
                unit TEXT,
                source TEXT,
                description TEXT,
                last_updated TEXT,
                seasonal_adjustment BOOLEAN,
                metadata TEXT
            )
        """
        )

        # Indicator data table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS indicator_data (
                data_id TEXT PRIMARY KEY,
                indicator_id TEXT,
                date TEXT,
                value REAL,
                created_at TEXT
            )
        """
        )

        # Trend analysis table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trend_analysis (
                analysis_id TEXT PRIMARY KEY,
                indicator_id TEXT,
                trend_direction TEXT,
                trend_strength REAL,
                change_rate REAL,
                momentum REAL,
                volatility REAL,
                confidence_level REAL,
                breakpoints TEXT,
                analysis_date TEXT
            )
        """
        )

        # Scenarios table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS economic_scenarios (
                scenario_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                probability REAL,
                key_assumptions TEXT,
                risk_factors TEXT,
                market_implications TEXT,
                created_at TEXT
            )
        """
        )

        # Forecasts table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS macro_forecasts (
                forecast_id TEXT PRIMARY KEY,
                forecast_horizon INTEGER,
                base_scenario_id TEXT,
                key_metrics TEXT,
                confidence_intervals TEXT,
                risk_assessment TEXT,
                policy_implications TEXT,
                generated_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    async def add_indicator(
        self,
        name: str,
        indicator_type: IndicatorType,
        frequency: IndicatorFrequency,
        unit: str,
        source: str,
        description: str,
        data_source_id: str,
    ) -> EconomicIndicator:
        """Add a new economic indicator to the system."""

        indicator_id = str(uuid.uuid4())

        # Fetch data based on source
        end_date = datetime.now()
        start_date = end_date - timedelta(days=2 * 365)  # 2 years of data

        if source.upper() == "FRED":
            data = await self.data_provider.get_fred_data(
                data_source_id, start_date, end_date
            )
        elif source.upper() == "BEA":
            # For BEA, data_source_id should be in format "dataset:table"
            parts = data_source_id.split(":")
            if len(parts) == 2:
                df = await self.data_provider.get_bea_data(
                    parts[0], parts[1], start_date.year, end_date.year
                )
                data = df.iloc[:, 0] if not df.empty else pd.Series(dtype=float)
            else:
                data = pd.Series(dtype=float)
        else:
            # Default to simulated data
            data = await self._generate_sample_data(
                indicator_type, start_date, end_date
            )

        indicator = EconomicIndicator(
            indicator_id=indicator_id,
            name=name,
            indicator_type=indicator_type,
            frequency=frequency,
            unit=unit,
            source=source,
            description=description,
            data=data,
        )

        self.indicators[indicator_id] = indicator

        # Store in database
        await self._store_indicator(indicator)

        return indicator

    async def _generate_sample_data(
        self, indicator_type: IndicatorType, start_date: datetime, end_date: datetime
    ) -> pd.Series:
        """Generate sample data for demonstration."""
        dates = pd.date_range(start=start_date, end=end_date, freq="M")

        if indicator_type == IndicatorType.GROWTH:
            # GDP-like growth data
            base_value = 20000
            trend = np.linspace(0, len(dates) * 0.02, len(dates))
            cycle = 0.01 * np.sin(2 * np.pi * np.arange(len(dates)) / 40)
            noise = np.random.normal(0, 0.005, len(dates))
            values = base_value * (1 + trend + cycle + noise)

        elif indicator_type == IndicatorType.INFLATION:
            # CPI-like inflation data
            base_value = 100
            trend = np.cumsum(np.random.normal(0.002, 0.01, len(dates)))
            values = base_value * np.exp(trend)

        elif indicator_type == IndicatorType.EMPLOYMENT:
            # Unemployment rate data
            base_rate = 5.0
            cycle = 2.0 * np.sin(2 * np.pi * np.arange(len(dates)) / 60)
            noise = np.random.normal(0, 0.3, len(dates))
            values = np.maximum(1.0, base_rate + cycle + noise)

        else:
            # Generic indicator
            values = 100 + np.cumsum(np.random.normal(0.1, 1.0, len(dates)))

        return pd.Series(values, index=dates)

    async def analyze_economic_cycle(self) -> dict[str, Any]:
        """Analyze current economic cycle phase."""

        if not self.indicators:
            return {"phase": "unknown", "confidence": 0.0}

        # Get key indicators for cycle analysis
        growth_indicators = [
            i
            for i in self.indicators.values()
            if i.indicator_type == IndicatorType.GROWTH
        ]
        employment_indicators = [
            i
            for i in self.indicators.values()
            if i.indicator_type == IndicatorType.EMPLOYMENT
        ]

        # Analyze trends
        growth_trends = []
        employment_trends = []

        for indicator in growth_indicators:
            trend = await self.trend_analyzer.analyze_trend(indicator)
            growth_trends.append(trend)

        for indicator in employment_indicators:
            trend = await self.trend_analyzer.analyze_trend(indicator)
            employment_trends.append(trend)

        # Determine cycle phase
        phase = self._determine_cycle_phase(growth_trends, employment_trends)

        # Calculate confidence
        confidence = self._calculate_cycle_confidence(growth_trends, employment_trends)

        return {
            "phase": phase.value,
            "confidence": confidence,
            "growth_trend": self._aggregate_trend_direction(growth_trends),
            "employment_trend": self._aggregate_trend_direction(employment_trends),
            "analysis_date": datetime.now().isoformat(),
        }

    def _determine_cycle_phase(
        self, growth_trends: list[TrendAnalysis], employment_trends: list[TrendAnalysis]
    ) -> EconomicRegime:
        """Determine the current economic cycle phase."""

        # Aggregate trend directions
        growth_score = self._calculate_trend_score(growth_trends)
        employment_score = self._calculate_trend_score(employment_trends)

        # Cycle phase determination logic
        if growth_score > 0.5 and employment_score > 0.5:
            return EconomicRegime.EXPANSION
        elif growth_score > 0.8 and employment_score > 0.8:
            return EconomicRegime.PEAK
        elif growth_score < -0.5 and employment_score < -0.5:
            return EconomicRegime.RECESSION
        elif growth_score < -0.8 and employment_score < -0.8:
            return EconomicRegime.TROUGH
        elif growth_score > 0 and employment_score > 0:
            return EconomicRegime.RECOVERY
        else:
            return EconomicRegime.EXPANSION  # Default

    def _calculate_trend_score(self, trends: list[TrendAnalysis]) -> float:
        """Calculate aggregate trend score."""
        if not trends:
            return 0.0

        scores = []
        for trend in trends:
            if trend.trend_direction == TrendDirection.STRONGLY_RISING:
                scores.append(1.0)
            elif trend.trend_direction == TrendDirection.RISING:
                scores.append(0.5)
            elif trend.trend_direction == TrendDirection.STABLE:
                scores.append(0.0)
            elif trend.trend_direction == TrendDirection.DECLINING:
                scores.append(-0.5)
            elif trend.trend_direction == TrendDirection.STRONGLY_DECLINING:
                scores.append(-1.0)

        return np.mean(scores) if scores else 0.0

    def _aggregate_trend_direction(self, trends: list[TrendAnalysis]) -> str:
        """Aggregate trend direction across multiple indicators."""
        if not trends:
            return "unknown"

        directions = [trend.trend_direction for trend in trends]
        direction_counts = pd.Series(directions).value_counts()
        most_common = (
            direction_counts.index[0]
            if not direction_counts.empty
            else TrendDirection.STABLE
        )

        return most_common.value

    def _calculate_cycle_confidence(
        self, growth_trends: list[TrendAnalysis], employment_trends: list[TrendAnalysis]
    ) -> float:
        """Calculate confidence in cycle phase determination."""

        all_trends = growth_trends + employment_trends
        if not all_trends:
            return 0.0

        # Base confidence on trend strength and consistency
        confidence_scores = [trend.confidence_level for trend in all_trends]
        trend_strengths = [trend.trend_strength for trend in all_trends]

        avg_confidence = np.mean(confidence_scores)
        avg_strength = np.mean(trend_strengths)

        # Adjust for consistency (lower variance = higher confidence)
        direction_scores = [
            self._trend_to_score(trend.trend_direction) for trend in all_trends
        ]
        consistency = 1.0 - np.std(direction_scores) / 2.0  # Normalize std

        overall_confidence = (avg_confidence + avg_strength + consistency) / 3.0
        return min(overall_confidence, 1.0)

    def _trend_to_score(self, direction: TrendDirection) -> float:
        """Convert trend direction to numerical score."""
        mapping = {
            TrendDirection.STRONGLY_DECLINING: -2.0,
            TrendDirection.DECLINING: -1.0,
            TrendDirection.STABLE: 0.0,
            TrendDirection.RISING: 1.0,
            TrendDirection.STRONGLY_RISING: 2.0,
        }
        return mapping.get(direction, 0.0)

    async def generate_macro_forecast(self, horizon_months: int = 12) -> MacroForecast:
        """Generate comprehensive macroeconomic forecast."""

        # Generate scenarios
        scenarios = await self.scenario_generator.generate_scenarios(
            list(self.indicators.values()), horizon_months
        )

        # Select base scenario (highest probability)
        base_scenario = max(scenarios, key=lambda s: s.probability)
        alternative_scenarios = [s for s in scenarios if s != base_scenario]

        # Calculate key metrics
        key_metrics = await self._calculate_forecast_metrics(scenarios)

        # Calculate confidence intervals
        confidence_intervals = await self._calculate_confidence_intervals(scenarios)

        # Assess risks
        risk_assessment = await self._assess_forecast_risks(scenarios)

        # Generate policy implications
        policy_implications = self._generate_policy_implications(scenarios)

        forecast = MacroForecast(
            forecast_id=str(uuid.uuid4()),
            forecast_horizon=horizon_months,
            base_scenario=base_scenario,
            alternative_scenarios=alternative_scenarios,
            key_metrics=key_metrics,
            confidence_intervals=confidence_intervals,
            risk_assessment=risk_assessment,
            policy_implications=policy_implications,
        )

        # Store forecast
        await self._store_forecast(forecast)

        return forecast

    async def _calculate_forecast_metrics(
        self, scenarios: list[EconomicScenario]
    ) -> dict[str, float]:
        """Calculate key forecast metrics across scenarios."""

        metrics = {}

        # Weight scenarios by probability
        total_prob = sum(s.probability for s in scenarios)

        if total_prob > 0:
            # GDP growth expectation
            gdp_growth = (
                sum(
                    s.key_assumptions.get("gdp_growth", 0) * s.probability
                    for s in scenarios
                )
                / total_prob
            )
            metrics["expected_gdp_growth"] = gdp_growth

            # Inflation expectation
            inflation = (
                sum(
                    s.key_assumptions.get("inflation_rate", 0) * s.probability
                    for s in scenarios
                )
                / total_prob
            )
            metrics["expected_inflation"] = inflation

            # Unemployment expectation
            unemployment = (
                sum(
                    s.key_assumptions.get("unemployment_rate", 0) * s.probability
                    for s in scenarios
                )
                / total_prob
            )
            metrics["expected_unemployment"] = unemployment

            # Interest rate change expectation
            rate_change = (
                sum(
                    s.key_assumptions.get("interest_rate_change", 0) * s.probability
                    for s in scenarios
                )
                / total_prob
            )
            metrics["expected_rate_change"] = rate_change

        return metrics

    async def _calculate_confidence_intervals(
        self, scenarios: list[EconomicScenario]
    ) -> dict[str, tuple[float, float]]:
        """Calculate confidence intervals for key metrics."""

        confidence_intervals = {}

        # Extract key metrics from scenarios
        gdp_values = [s.key_assumptions.get("gdp_growth", 0) for s in scenarios]
        inflation_values = [
            s.key_assumptions.get("inflation_rate", 0) for s in scenarios
        ]

        # Calculate 90% confidence intervals (5th and 95th percentiles)
        if gdp_values:
            confidence_intervals["gdp_growth"] = (
                np.percentile(gdp_values, 5),
                np.percentile(gdp_values, 95),
            )

        if inflation_values:
            confidence_intervals["inflation_rate"] = (
                np.percentile(inflation_values, 5),
                np.percentile(inflation_values, 95),
            )

        return confidence_intervals

    async def _assess_forecast_risks(
        self, scenarios: list[EconomicScenario]
    ) -> dict[str, RiskLevel]:
        """Assess risks associated with the forecast."""

        risk_assessment = {}

        # Assess recession risk
        recession_prob = sum(
            s.probability
            for s in scenarios
            if s.key_assumptions.get("gdp_growth", 0) < -0.01
        )

        if recession_prob > 0.3:
            risk_assessment["recession_risk"] = RiskLevel.HIGH
        elif recession_prob > 0.15:
            risk_assessment["recession_risk"] = RiskLevel.MODERATE
        else:
            risk_assessment["recession_risk"] = RiskLevel.LOW

        # Assess inflation risk
        high_inflation_prob = sum(
            s.probability
            for s in scenarios
            if s.key_assumptions.get("inflation_rate", 0) > 0.05
        )

        if high_inflation_prob > 0.3:
            risk_assessment["inflation_risk"] = RiskLevel.HIGH
        elif high_inflation_prob > 0.15:
            risk_assessment["inflation_risk"] = RiskLevel.MODERATE
        else:
            risk_assessment["inflation_risk"] = RiskLevel.LOW

        return risk_assessment

    def _generate_policy_implications(
        self, scenarios: list[EconomicScenario]
    ) -> list[str]:
        """Generate policy implications based on scenarios."""

        implications = []

        # Check for high recession risk
        recession_scenarios = [
            s for s in scenarios if s.key_assumptions.get("gdp_growth", 0) < -0.01
        ]
        if sum(s.probability for s in recession_scenarios) > 0.2:
            implications.append("Consider countercyclical fiscal policy measures")
            implications.append("Monetary policy should remain accommodative")

        # Check for high inflation risk
        inflation_scenarios = [
            s for s in scenarios if s.key_assumptions.get("inflation_rate", 0) > 0.05
        ]
        if sum(s.probability for s in inflation_scenarios) > 0.2:
            implications.append(
                "Central bank should consider tightening monetary policy"
            )
            implications.append("Monitor wage growth and inflation expectations")

        # Check for high unemployment risk
        unemployment_scenarios = [
            s for s in scenarios if s.key_assumptions.get("unemployment_rate", 0) > 0.07
        ]
        if sum(s.probability for s in unemployment_scenarios) > 0.2:
            implications.append("Focus on employment-supporting policies")
            implications.append("Consider targeted job training programs")

        return implications

    async def _store_indicator(self, indicator: EconomicIndicator):
        """Store economic indicator in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Store indicator metadata
            conn.execute(
                """
                INSERT OR REPLACE INTO economic_indicators
                (indicator_id, name, indicator_type, frequency, unit, source,
                 description, last_updated, seasonal_adjustment, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    indicator.indicator_id,
                    indicator.name,
                    indicator.indicator_type.value,
                    indicator.frequency.value,
                    indicator.unit,
                    indicator.source,
                    indicator.description,
                    indicator.last_updated.isoformat(),
                    indicator.seasonal_adjustment,
                    json.dumps(indicator.metadata),
                ),
            )

            # Store indicator data
            for date, value in indicator.data.items():
                data_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT OR REPLACE INTO indicator_data
                    (data_id, indicator_id, date, value, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        data_id,
                        indicator.indicator_id,
                        date.isoformat(),
                        float(value),
                        datetime.now().isoformat(),
                    ),
                )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing indicator: {e}")

    async def _store_forecast(self, forecast: MacroForecast):
        """Store macro forecast in database."""
        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                """
                INSERT INTO macro_forecasts
                (forecast_id, forecast_horizon, base_scenario_id, key_metrics,
                 confidence_intervals, risk_assessment, policy_implications, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    forecast.forecast_id,
                    forecast.forecast_horizon,
                    forecast.base_scenario.scenario_id,
                    json.dumps(forecast.key_metrics),
                    json.dumps(forecast.confidence_intervals),
                    json.dumps(
                        {k: v.value for k, v in forecast.risk_assessment.items()}
                    ),
                    json.dumps(forecast.policy_implications),
                    forecast.generated_at.isoformat(),
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error storing forecast: {e}")


# Example usage and testing
async def main():
    """Example usage of the Macro Analysis Engine."""

    # Initialize engine
    engine = MacroAnalysisEngine()

    print("Initializing Economic Indicators...")

    # Add key economic indicators
    gdp_indicator = await engine.add_indicator(
        name="Real GDP",
        indicator_type=IndicatorType.GROWTH,
        frequency=IndicatorFrequency.QUARTERLY,
        unit="Billions of Chained 2012 Dollars",
        source="BEA",
        description="Real Gross Domestic Product",
        data_source_id="NIPA:GDP",
    )

    unemployment_indicator = await engine.add_indicator(
        name="Unemployment Rate",
        indicator_type=IndicatorType.EMPLOYMENT,
        frequency=IndicatorFrequency.MONTHLY,
        unit="Percent",
        source="FRED",
        description="Civilian Unemployment Rate",
        data_source_id="UNRATE",
    )

    await engine.add_indicator(
        name="Consumer Price Index",
        indicator_type=IndicatorType.INFLATION,
        frequency=IndicatorFrequency.MONTHLY,
        unit="Index 1982-84=100",
        source="FRED",
        description="Consumer Price Index for All Urban Consumers: All Items",
        data_source_id="CPIAUCSL",
    )

    await engine.add_indicator(
        name="Federal Funds Rate",
        indicator_type=IndicatorType.MONETARY,
        frequency=IndicatorFrequency.MONTHLY,
        unit="Percent",
        source="FRED",
        description="Effective Federal Funds Rate",
        data_source_id="FEDFUNDS",
    )

    print(f"Added {len(engine.indicators)} economic indicators")

    # Analyze trends
    print("\nAnalyzing Economic Trends...")

    gdp_trend = await engine.trend_analyzer.analyze_trend(gdp_indicator)
    print(
        f"GDP Trend: {gdp_trend.trend_direction.value} (strength: {gdp_trend.trend_strength:.3f})"
    )

    unemployment_trend = await engine.trend_analyzer.analyze_trend(
        unemployment_indicator
    )
    print(
        f"Unemployment Trend: {unemployment_trend.trend_direction.value} (strength: {unemployment_trend.trend_strength:.3f})"
    )

    # Analyze correlations
    print("\nAnalyzing Correlations...")

    indicators_list = list(engine.indicators.values())
    correlation_analysis = await engine.correlation_analyzer.analyze_correlations(
        indicators_list
    )

    print("Correlation Matrix:")
    print(correlation_analysis.correlation_matrix)

    # Analyze economic cycle
    print("\nAnalyzing Economic Cycle...")

    cycle_analysis = await engine.analyze_economic_cycle()
    print(f"Current Economic Phase: {cycle_analysis['phase']}")
    print(f"Confidence: {cycle_analysis['confidence']:.3f}")
    print(f"Growth Trend: {cycle_analysis['growth_trend']}")
    print(f"Employment Trend: {cycle_analysis['employment_trend']}")

    # Generate macro forecast
    print("\nGenerating Macro Forecast...")

    forecast = await engine.generate_macro_forecast(horizon_months=12)

    print("\nMacro Forecast (12-month horizon):")
    print(f"Base Scenario: {forecast.base_scenario.name}")
    print(f"Probability: {forecast.base_scenario.probability:.1%}")

    print("\nKey Metrics:")
    for metric, value in forecast.key_metrics.items():
        print(f"  {metric}: {value:.3f}")

    print("\nRisk Assessment:")
    for risk, level in forecast.risk_assessment.items():
        print(f"  {risk}: {level.value}")

    print("\nPolicy Implications:")
    for implication in forecast.policy_implications:
        print(f"  • {implication}")

    print("\nAlternative Scenarios:")
    for scenario in forecast.alternative_scenarios:
        print(
            f"  • {scenario.name} ({scenario.probability:.1%}): {scenario.description}"
        )

    # Test scenario generation
    print("\n" + "=" * 60)
    print("ECONOMIC SCENARIO ANALYSIS")
    print("=" * 60)

    scenarios = await engine.scenario_generator.generate_scenarios(
        list(engine.indicators.values()), horizon_months=12
    )

    for scenario in scenarios:
        print(f"\nScenario: {scenario.name}")
        print(f"Probability: {scenario.probability:.1%}")
        print(f"Description: {scenario.description}")

        print("Key Assumptions:")
        for key, value in scenario.key_assumptions.items():
            if isinstance(value, int | float) and key != "probability":
                print(f"  {key}: {value:.3f}")

        print("Risk Factors:")
        for risk in scenario.risk_factors[:3]:  # Show first 3
            print(f"  • {risk}")

        print("Market Implications:")
        for market, implication in scenario.market_implications.items():
            print(f"  {market}: {implication}")


if __name__ == "__main__":
    asyncio.run(main())
