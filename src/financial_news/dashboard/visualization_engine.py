"""
Interactive Visualization Dashboard Engine

This module provides comprehensive dashboard capabilities including advanced charting,
real-time data visualization, customizable layouts, and interactive analytics.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import redis
import yfinance as yf
from dash import Input, Output, callback_context, dcc, html
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


class ChartType(Enum):
    """Types of charts available."""

    LINE = "line"
    CANDLESTICK = "candlestick"
    BAR = "bar"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    SUNBURST = "sunburst"
    WATERFALL = "waterfall"
    FUNNEL = "funnel"
    GAUGE = "gauge"
    INDICATOR = "indicator"
    TABLE = "table"
    HISTOGRAM = "histogram"
    BOX = "box"
    VIOLIN = "violin"
    SURFACE = "surface"
    CONTOUR = "contour"


class LayoutType(Enum):
    """Dashboard layout types."""

    GRID = "grid"
    MASONRY = "masonry"
    SIDEBAR = "sidebar"
    TABS = "tabs"
    ACCORDION = "accordion"
    CAROUSEL = "carousel"


class UpdateFrequency(Enum):
    """Data update frequencies."""

    REAL_TIME = "real_time"
    EVERY_SECOND = "1s"
    EVERY_MINUTE = "1m"
    EVERY_FIVE_MINUTES = "5m"
    EVERY_HOUR = "1h"
    DAILY = "1d"
    MANUAL = "manual"


@dataclass
class ChartConfig:
    """Chart configuration."""

    chart_id: str
    chart_type: ChartType
    title: str
    data_source: str
    parameters: dict[str, Any]
    layout: dict[str, Any] = field(default_factory=dict)
    style: dict[str, Any] = field(default_factory=dict)
    update_frequency: UpdateFrequency = UpdateFrequency.MANUAL
    is_interactive: bool = True
    export_enabled: bool = True


@dataclass
class DashboardLayout:
    """Dashboard layout configuration."""

    layout_id: str
    name: str
    layout_type: LayoutType
    grid_config: dict[str, Any] = field(default_factory=dict)
    responsive: bool = True
    theme: str = "light"
    custom_css: str = ""


@dataclass
class Widget:
    """Dashboard widget."""

    widget_id: str
    widget_type: str
    title: str
    content: dict[str, Any]
    position: dict[str, int]  # x, y, width, height
    config: dict[str, Any] = field(default_factory=dict)
    data_source: str | None = None
    update_frequency: UpdateFrequency = UpdateFrequency.MANUAL
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Dashboard:
    """Complete dashboard definition."""

    dashboard_id: str
    name: str
    description: str
    layout: DashboardLayout
    widgets: list[Widget]
    created_by: str
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    tags: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)


class DataSourceManager:
    """Manage various data sources for visualizations."""

    def __init__(self):
        self.redis_client = None
        self.data_cache = {}
        self.streaming_connections = {}

        try:
            self.redis_client = redis.Redis(host="localhost", port=6379, db=0)
        except Exception as e:
            logger.warning(f"Redis not available: {e}")

    async def get_stock_data(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """Get stock price data."""
        try:
            cache_key = f"stock_{symbol}_{period}_{interval}"

            # Check cache first
            if cache_key in self.data_cache:
                cached_time, data = self.data_cache[cache_key]
                if datetime.now() - cached_time < timedelta(minutes=5):
                    return data

            # Fetch fresh data
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)

            # Cache the data
            self.data_cache[cache_key] = (datetime.now(), data)

            return data

        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {e}")
            return pd.DataFrame()

    async def get_market_indices(self) -> dict[str, pd.DataFrame]:
        """Get major market indices data."""
        indices = {
            "S&P 500": "^GSPC",
            "Dow Jones": "^DJI",
            "NASDAQ": "^IXIC",
            "Russell 2000": "^RUT",
            "VIX": "^VIX",
        }

        results = {}
        for name, symbol in indices.items():
            try:
                data = await self.get_stock_data(symbol, period="1mo", interval="1d")
                results[name] = data
            except Exception as e:
                logger.error(f"Error fetching {name} data: {e}")
                results[name] = pd.DataFrame()

        return results

    async def get_sector_performance(self) -> dict[str, float]:
        """Get sector performance data."""
        sector_etfs = {
            "Technology": "XLK",
            "Healthcare": "XLV",
            "Financial": "XLF",
            "Energy": "XLE",
            "Consumer Discretionary": "XLY",
            "Industrial": "XLI",
            "Consumer Staples": "XLP",
            "Materials": "XLB",
            "Real Estate": "XLRE",
            "Utilities": "XLU",
            "Communication": "XLC",
        }

        performance = {}
        for sector, symbol in sector_etfs.items():
            try:
                data = await self.get_stock_data(symbol, period="1mo", interval="1d")
                if not data.empty:
                    current_price = data["Close"][-1]
                    month_ago_price = data["Close"][0]
                    change_pct = (
                        (current_price - month_ago_price) / month_ago_price * 100
                    )
                    performance[sector] = round(change_pct, 2)
            except Exception as e:
                logger.error(f"Error calculating {sector} performance: {e}")
                performance[sector] = 0.0

        return performance

    async def get_economic_indicators(self) -> dict[str, Any]:
        """Get economic indicators (simulated for demo)."""
        return {
            "GDP Growth": {"value": 2.1, "change": 0.1, "unit": "%"},
            "Unemployment Rate": {"value": 3.7, "change": -0.1, "unit": "%"},
            "Inflation Rate": {"value": 3.2, "change": 0.2, "unit": "%"},
            "Interest Rate": {"value": 5.25, "change": 0.0, "unit": "%"},
            "Consumer Confidence": {"value": 102.3, "change": 1.5, "unit": "index"},
        }

    async def get_real_time_data(self, symbols: list[str]) -> dict[str, dict]:
        """Get real-time data for symbols."""
        real_time_data = {}

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period="2d", interval="1m")

                if not hist.empty:
                    current_price = hist["Close"][-1]
                    prev_close = info.get("previousClose", current_price)
                    change = current_price - prev_close
                    change_pct = (change / prev_close) * 100

                    real_time_data[symbol] = {
                        "price": round(current_price, 2),
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2),
                        "volume": hist["Volume"][-1] if "Volume" in hist.columns else 0,
                        "timestamp": datetime.now().isoformat(),
                    }
            except Exception as e:
                logger.error(f"Error fetching real-time data for {symbol}: {e}")
                real_time_data[symbol] = {
                    "price": 0,
                    "change": 0,
                    "change_pct": 0,
                    "volume": 0,
                    "timestamp": datetime.now().isoformat(),
                }

        return real_time_data


class ChartGenerator:
    """Generate various types of charts using Plotly."""

    def __init__(self):
        self.default_colors = px.colors.qualitative.Set1
        self.themes = {
            "light": {"background": "white", "text": "black", "grid": "lightgray"},
            "dark": {"background": "#1e1e1e", "text": "white", "grid": "#444444"},
        }

    def create_candlestick_chart(
        self, data: pd.DataFrame, title: str = "Stock Price", theme: str = "light"
    ) -> go.Figure:
        """Create a candlestick chart."""
        fig = go.Figure(
            data=go.Candlestick(
                x=data.index,
                open=data["Open"],
                high=data["High"],
                low=data["Low"],
                close=data["Close"],
                name="Price",
            )
        )

        # Add volume subplot
        fig.add_trace(
            go.Bar(
                x=data.index, y=data["Volume"], name="Volume", yaxis="y2", opacity=0.3
            )
        )

        # Update layout
        fig.update_layout(
            title=title,
            yaxis_title="Price",
            yaxis2={"title": "Volume", "overlaying": "y", "side": "right"},
            xaxis_rangeslider_visible=False,
            template=self._get_plotly_theme(theme),
            height=500,
        )

        return fig

    def create_line_chart(
        self,
        data: pd.DataFrame,
        x_col: str,
        y_cols: list[str],
        title: str = "Line Chart",
        theme: str = "light",
    ) -> go.Figure:
        """Create a line chart."""
        fig = go.Figure()

        for i, col in enumerate(y_cols):
            fig.add_trace(
                go.Scatter(
                    x=data[x_col] if x_col in data.columns else data.index,
                    y=data[col],
                    mode="lines",
                    name=col,
                    line={"color": self.default_colors[i % len(self.default_colors)]},
                )
            )

        fig.update_layout(
            title=title, template=self._get_plotly_theme(theme), height=400
        )

        return fig

    def create_heatmap(
        self, data: dict[str, float], title: str = "Heatmap", theme: str = "light"
    ) -> go.Figure:
        """Create a heatmap chart."""
        # Convert data to matrix format
        labels = list(data.keys())
        list(data.values())

        # Create a grid for the heatmap
        grid_size = int(np.ceil(np.sqrt(len(labels))))
        matrix = np.zeros((grid_size, grid_size))
        text_matrix = np.empty((grid_size, grid_size), dtype=object)

        for i, (label, value) in enumerate(data.items()):
            row = i // grid_size
            col = i % grid_size
            matrix[row, col] = value
            text_matrix[row, col] = f"{label}<br>{value:.1f}%"

        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                text=text_matrix,
                texttemplate="%{text}",
                textfont={"size": 10},
                colorscale="RdYlGn",
                zmid=0,
                showscale=True,
            )
        )

        fig.update_layout(
            title=title,
            template=self._get_plotly_theme(theme),
            height=400,
            xaxis={"showticklabels": False},
            yaxis={"showticklabels": False},
        )

        return fig

    def create_gauge_chart(
        self,
        value: float,
        title: str = "Gauge",
        min_val: float = 0,
        max_val: float = 100,
        theme: str = "light",
    ) -> go.Figure:
        """Create a gauge chart."""
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number+delta",
                value=value,
                domain={"x": [0, 1], "y": [0, 1]},
                title={"text": title},
                delta={"reference": (max_val + min_val) / 2},
                gauge={
                    "axis": {"range": [None, max_val]},
                    "bar": {"color": "darkblue"},
                    "steps": [
                        {"range": [min_val, max_val * 0.25], "color": "lightgray"},
                        {"range": [max_val * 0.25, max_val * 0.5], "color": "gray"},
                        {
                            "range": [max_val * 0.5, max_val * 0.75],
                            "color": "lightgreen",
                        },
                        {"range": [max_val * 0.75, max_val], "color": "green"},
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.75,
                        "value": max_val * 0.9,
                    },
                },
            )
        )

        fig.update_layout(template=self._get_plotly_theme(theme), height=300)

        return fig

    def create_treemap(
        self, data: dict[str, float], title: str = "Treemap", theme: str = "light"
    ) -> go.Figure:
        """Create a treemap chart."""
        labels = list(data.keys())
        values = [abs(v) for v in data.values()]  # Use absolute values for size
        list(data.values())  # Use original values for color

        fig = go.Figure(
            go.Treemap(
                labels=labels,
                values=values,
                parents=[""] * len(labels),
                textinfo="label+value",
                texttemplate="<b>%{label}</b><br>%{color:.1f}%",
                colorscale="RdYlGn",
                colorbar={"title": "Performance %"},
                marker_colorbar_title_text="Performance %",
            )
        )

        fig.update_layout(
            title=title, template=self._get_plotly_theme(theme), height=400
        )

        return fig

    def create_waterfall_chart(
        self,
        categories: list[str],
        values: list[float],
        title: str = "Waterfall Chart",
        theme: str = "light",
    ) -> go.Figure:
        """Create a waterfall chart."""
        fig = go.Figure(
            go.Waterfall(
                name="",
                orientation="v",
                measure=["relative"] * (len(categories) - 1) + ["total"],
                x=categories,
                textposition="outside",
                text=[f"{v:+.1f}" for v in values],
                y=values,
                connector={"line": {"color": "rgb(63, 63, 63)"}},
            )
        )

        fig.update_layout(
            title=title, template=self._get_plotly_theme(theme), height=400
        )

        return fig

    def create_indicator_grid(
        self,
        indicators: dict[str, dict[str, Any]],
        title: str = "Key Indicators",
        theme: str = "light",
    ) -> go.Figure:
        """Create a grid of indicator charts."""
        n_indicators = len(indicators)
        cols = min(3, n_indicators)
        rows = int(np.ceil(n_indicators / cols))

        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=list(indicators.keys()),
            specs=[[{"type": "indicator"}] * cols for _ in range(rows)],
        )

        for i, (name, data) in enumerate(indicators.items()):
            row = i // cols + 1
            col = i % cols + 1

            value = data.get("value", 0)
            change = data.get("change", 0)
            unit = data.get("unit", "")

            fig.add_trace(
                go.Indicator(
                    mode="number+delta",
                    value=value,
                    delta={"reference": value - change, "relative": False},
                    title={
                        "text": f"{name}<br><span style='font-size:0.8em'>{unit}</span>"
                    },
                    number={"suffix": f" {unit}"},
                ),
                row=row,
                col=col,
            )

        fig.update_layout(
            title=title, template=self._get_plotly_theme(theme), height=200 * rows
        )

        return fig

    def _get_plotly_theme(self, theme: str) -> str:
        """Get Plotly theme name."""
        theme_map = {"light": "plotly_white", "dark": "plotly_dark"}
        return theme_map.get(theme, "plotly_white")


class DashboardEngine:
    """Main dashboard engine managing layouts, widgets, and real-time updates."""

    def __init__(self):
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.data_source = DataSourceManager()
        self.chart_generator = ChartGenerator()
        self.dashboards = {}
        self.widgets = {}
        self.db_path = "dashboards.db"
        self._setup_database()
        self._setup_dash_app()

    def _setup_database(self):
        """Setup database for dashboard storage."""
        conn = sqlite3.connect(self.db_path)

        # Dashboards table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dashboards (
                dashboard_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                layout_config TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                is_public BOOLEAN,
                tags TEXT,
                settings TEXT
            )
        """
        )

        # Widgets table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS widgets (
                widget_id TEXT PRIMARY KEY,
                dashboard_id TEXT,
                widget_type TEXT,
                title TEXT,
                content TEXT,
                position TEXT,
                config TEXT,
                data_source TEXT,
                update_frequency TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def _setup_dash_app(self):
        """Setup Dash application with layouts and callbacks."""
        # Define the main layout
        self.app.layout = dbc.Container(
            [
                dcc.Store(id="dashboard-store"),
                dcc.Store(id="real-time-store"),
                dcc.Interval(
                    id="interval-component",
                    interval=5 * 1000,  # Update every 5 seconds
                    n_intervals=0,
                ),
                # Header
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H1(
                                    "Financial Analysis Dashboard",
                                    className="text-primary",
                                ),
                                html.Hr(),
                            ]
                        )
                    ]
                ),
                # Controls
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.ButtonGroup(
                                    [
                                        dbc.Button(
                                            "Market Overview",
                                            id="btn-market",
                                            color="primary",
                                            outline=True,
                                        ),
                                        dbc.Button(
                                            "Stock Analysis",
                                            id="btn-stock",
                                            color="primary",
                                            outline=True,
                                        ),
                                        dbc.Button(
                                            "Sectors",
                                            id="btn-sectors",
                                            color="primary",
                                            outline=True,
                                        ),
                                        dbc.Button(
                                            "Economics",
                                            id="btn-economics",
                                            color="primary",
                                            outline=True,
                                        ),
                                    ]
                                )
                            ],
                            width=8,
                        ),
                        dbc.Col(
                            [
                                dbc.Input(
                                    id="symbol-input",
                                    placeholder="Enter symbol (e.g., AAPL)",
                                    value="AAPL",
                                    type="text",
                                )
                            ],
                            width=4,
                        ),
                    ],
                    className="mb-4",
                ),
                # Main dashboard content
                html.Div(id="dashboard-content"),
                # Footer
                html.Hr(),
                html.P(
                    "Advanced Financial Analysis Platform",
                    className="text-muted text-center",
                ),
            ],
            fluid=True,
        )

        # Setup callbacks
        self._setup_callbacks()

    def _setup_callbacks(self):
        """Setup Dash callbacks for interactivity."""

        @self.app.callback(
            Output("dashboard-content", "children"),
            [
                Input("btn-market", "n_clicks"),
                Input("btn-stock", "n_clicks"),
                Input("btn-sectors", "n_clicks"),
                Input("btn-economics", "n_clicks"),
                Input("symbol-input", "value"),
            ],
        )
        def update_dashboard_content(
            market_clicks, stock_clicks, sectors_clicks, economics_clicks, symbol
        ):
            ctx = callback_context

            if not ctx.triggered:
                # Default to market overview
                return self._create_market_overview_layout()

            button_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if button_id == "btn-market":
                return self._create_market_overview_layout()
            elif button_id == "btn-stock":
                return self._create_stock_analysis_layout(symbol or "AAPL")
            elif button_id == "btn-sectors":
                return self._create_sectors_layout()
            elif button_id == "btn-economics":
                return self._create_economics_layout()
            else:
                return self._create_market_overview_layout()

        @self.app.callback(
            Output("real-time-store", "data"),
            [Input("interval-component", "n_intervals")],
        )
        def update_real_time_data(n):
            # Update real-time data for key symbols
            symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
            return asyncio.run(self.data_source.get_real_time_data(symbols))

    def _create_market_overview_layout(self):
        """Create market overview dashboard layout."""
        # This would be called asynchronously in a real implementation
        # For demo purposes, we'll use simulated data

        return dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="market-indices-chart",
                                    figure=self._create_sample_market_chart(),
                                )
                            ],
                            width=8,
                        ),
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="market-indicators",
                                    figure=self._create_sample_indicators(),
                                )
                            ],
                            width=4,
                        ),
                    ]
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="sector-heatmap",
                                    figure=self._create_sample_sector_heatmap(),
                                )
                            ],
                            width=6,
                        ),
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="top-movers",
                                    figure=self._create_sample_top_movers(),
                                )
                            ],
                            width=6,
                        ),
                    ]
                ),
            ]
        )

    def _create_stock_analysis_layout(self, symbol: str):
        """Create stock analysis dashboard layout."""
        return dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H3(f"{symbol} Analysis"),
                                dcc.Graph(
                                    id="stock-candlestick",
                                    figure=self._create_sample_candlestick(symbol),
                                ),
                            ],
                            width=8,
                        ),
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="stock-metrics",
                                    figure=self._create_sample_stock_metrics(symbol),
                                )
                            ],
                            width=4,
                        ),
                    ]
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="technical-indicators",
                                    figure=self._create_sample_technical_indicators(
                                        symbol
                                    ),
                                )
                            ],
                            width=12,
                        )
                    ]
                ),
            ]
        )

    def _create_sectors_layout(self):
        """Create sectors analysis layout."""
        return dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="sector-performance",
                                    figure=self._create_sample_sector_performance(),
                                )
                            ],
                            width=12,
                        )
                    ]
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="sector-treemap",
                                    figure=self._create_sample_sector_treemap(),
                                )
                            ],
                            width=12,
                        )
                    ]
                ),
            ]
        )

    def _create_economics_layout(self):
        """Create economics dashboard layout."""
        return dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="economic-indicators",
                                    figure=self._create_sample_economic_indicators(),
                                )
                            ],
                            width=12,
                        )
                    ]
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="yield-curve",
                                    figure=self._create_sample_yield_curve(),
                                )
                            ],
                            width=6,
                        ),
                        dbc.Col(
                            [
                                dcc.Graph(
                                    id="inflation-chart",
                                    figure=self._create_sample_inflation_chart(),
                                )
                            ],
                            width=6,
                        ),
                    ]
                ),
            ]
        )

    # Sample chart creation methods (using simulated data for demo)
    def _create_sample_market_chart(self):
        """Create sample market indices chart."""
        dates = pd.date_range(start="2024-01-01", end="2024-12-01", freq="D")

        # Simulate market data
        np.random.seed(42)
        sp500 = 4500 + np.cumsum(np.random.randn(len(dates)) * 20)
        nasdaq = 15000 + np.cumsum(np.random.randn(len(dates)) * 100)
        dow = 35000 + np.cumsum(np.random.randn(len(dates)) * 150)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(x=dates, y=sp500, name="S&P 500", line={"color": "blue"})
        )
        fig.add_trace(
            go.Scatter(x=dates, y=nasdaq, name="NASDAQ", line={"color": "red"})
        )
        fig.add_trace(
            go.Scatter(x=dates, y=dow, name="Dow Jones", line={"color": "green"})
        )

        fig.update_layout(
            title="Major Market Indices",
            xaxis_title="Date",
            yaxis_title="Index Value",
            template="plotly_white",
            height=400,
        )

        return fig

    def _create_sample_indicators(self):
        """Create sample market indicators."""
        indicators = {
            "VIX": {"value": 18.5, "change": -2.1, "unit": ""},
            "Put/Call Ratio": {"value": 0.85, "change": 0.05, "unit": ""},
            "Advance/Decline": {"value": 1.2, "change": 0.1, "unit": ""},
        }

        return self.chart_generator.create_indicator_grid(
            indicators, "Market Sentiment Indicators"
        )

    def _create_sample_sector_heatmap(self):
        """Create sample sector performance heatmap."""
        sector_data = {
            "Technology": 2.1,
            "Healthcare": 1.5,
            "Financial": -0.8,
            "Energy": 3.2,
            "Consumer Disc.": 0.9,
            "Industrial": 1.2,
            "Consumer Staples": -0.3,
            "Materials": 2.8,
            "Real Estate": -1.1,
            "Utilities": 0.5,
            "Communication": 1.8,
        }

        return self.chart_generator.create_heatmap(
            sector_data, "Sector Performance (1M %)"
        )

    def _create_sample_top_movers(self):
        """Create sample top movers chart."""
        symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX"]
        changes = [2.1, 1.8, -1.2, 3.5, -2.8, 4.2, 1.1, -0.9]

        colors = ["green" if x > 0 else "red" for x in changes]

        fig = go.Figure(
            data=go.Bar(
                x=symbols,
                y=changes,
                marker_color=colors,
                text=[f"{x:+.1f}%" for x in changes],
                textposition="auto",
            )
        )

        fig.update_layout(
            title="Top Movers Today",
            xaxis_title="Symbol",
            yaxis_title="Change %",
            template="plotly_white",
            height=400,
        )

        return fig

    def _create_sample_candlestick(self, symbol: str):
        """Create sample candlestick chart."""
        dates = pd.date_range(start="2024-10-01", end="2024-12-01", freq="D")

        # Simulate OHLCV data
        np.random.seed(42)
        base_price = 150
        prices = base_price + np.cumsum(np.random.randn(len(dates)) * 2)

        data = pd.DataFrame(
            {
                "Open": prices + np.random.randn(len(dates)) * 0.5,
                "High": prices + np.abs(np.random.randn(len(dates)) * 1.5),
                "Low": prices - np.abs(np.random.randn(len(dates)) * 1.5),
                "Close": prices,
                "Volume": np.random.randint(1000000, 10000000, len(dates)),
            },
            index=dates,
        )

        return self.chart_generator.create_candlestick_chart(
            data, f"{symbol} Stock Price"
        )

    def _create_sample_stock_metrics(self, symbol: str):
        """Create sample stock metrics."""
        metrics = {
            "P/E Ratio": {"value": 28.5, "change": 0.5, "unit": ""},
            "Market Cap": {"value": 2.8, "change": 0.1, "unit": "T"},
            "Dividend Yield": {"value": 0.5, "change": 0.0, "unit": "%"},
        }

        return self.chart_generator.create_indicator_grid(
            metrics, f"{symbol} Key Metrics"
        )

    def _create_sample_technical_indicators(self, symbol: str):
        """Create sample technical indicators chart."""
        dates = pd.date_range(start="2024-10-01", end="2024-12-01", freq="D")

        # Simulate technical indicators
        np.random.seed(42)
        rsi = 50 + np.cumsum(np.random.randn(len(dates)) * 2)
        rsi = np.clip(rsi, 0, 100)

        macd = np.cumsum(np.random.randn(len(dates)) * 0.5)
        macd_signal = macd + np.random.randn(len(dates)) * 0.2

        fig = make_subplots(
            rows=2, cols=1, subplot_titles=["RSI", "MACD"], vertical_spacing=0.1
        )

        # RSI
        fig.add_trace(
            go.Scatter(x=dates, y=rsi, name="RSI", line={"color": "purple"}),
            row=1,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=1, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=1, col=1)

        # MACD
        fig.add_trace(
            go.Scatter(x=dates, y=macd, name="MACD", line={"color": "blue"}),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=dates, y=macd_signal, name="Signal", line={"color": "red"}),
            row=2,
            col=1,
        )

        fig.update_layout(
            title=f"{symbol} Technical Indicators", template="plotly_white", height=500
        )

        return fig

    def _create_sample_sector_performance(self):
        """Create sample sector performance chart."""
        sectors = [
            "Technology",
            "Healthcare",
            "Financial",
            "Energy",
            "Consumer Disc.",
            "Industrial",
            "Consumer Staples",
            "Materials",
            "Real Estate",
            "Utilities",
        ]
        performance = [12.5, 8.3, -2.1, 15.7, 6.9, 9.2, 3.1, 11.8, -1.5, 4.6]

        colors = ["green" if x > 0 else "red" for x in performance]

        fig = go.Figure(
            data=go.Bar(
                x=sectors,
                y=performance,
                marker_color=colors,
                text=[f"{x:+.1f}%" for x in performance],
                textposition="auto",
            )
        )

        fig.update_layout(
            title="Sector Performance (YTD %)",
            xaxis_title="Sector",
            yaxis_title="Performance %",
            template="plotly_white",
            height=400,
            xaxis={"tickangle": 45},
        )

        return fig

    def _create_sample_sector_treemap(self):
        """Create sample sector treemap."""
        sector_data = {
            "Technology": 15.2,
            "Healthcare": 8.9,
            "Financial": -1.8,
            "Energy": 12.5,
            "Consumer Disc.": 6.3,
            "Industrial": 7.8,
            "Consumer Staples": 2.1,
            "Materials": 9.7,
            "Real Estate": -0.9,
            "Utilities": 3.4,
            "Communication": 11.2,
        }

        return self.chart_generator.create_treemap(
            sector_data, "Sector Performance Treemap (YTD %)"
        )

    def _create_sample_economic_indicators(self):
        """Create sample economic indicators."""
        indicators = {
            "GDP Growth": {"value": 2.1, "change": 0.1, "unit": "%"},
            "Unemployment": {"value": 3.7, "change": -0.1, "unit": "%"},
            "Inflation": {"value": 3.2, "change": 0.2, "unit": "%"},
            "Interest Rate": {"value": 5.25, "change": 0.0, "unit": "%"},
            "Consumer Confidence": {"value": 102.3, "change": 1.5, "unit": ""},
            "Manufacturing PMI": {"value": 48.7, "change": -0.8, "unit": ""},
        }

        return self.chart_generator.create_indicator_grid(
            indicators, "Key Economic Indicators"
        )

    def _create_sample_yield_curve(self):
        """Create sample yield curve chart."""
        maturities = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "20Y", "30Y"]
        yields = [5.2, 5.1, 4.9, 4.8, 4.6, 4.4, 4.3, 4.5, 4.6]

        fig = go.Figure(
            data=go.Scatter(
                x=maturities,
                y=yields,
                mode="lines+markers",
                line={"color": "blue", "width": 3},
                marker={"size": 8},
            )
        )

        fig.update_layout(
            title="US Treasury Yield Curve",
            xaxis_title="Maturity",
            yaxis_title="Yield %",
            template="plotly_white",
            height=400,
        )

        return fig

    def _create_sample_inflation_chart(self):
        """Create sample inflation chart."""
        dates = pd.date_range(start="2023-01-01", end="2024-12-01", freq="M")

        # Simulate inflation data
        inflation_rates = [
            6.5,
            6.4,
            6.0,
            5.0,
            4.9,
            4.0,
            3.2,
            3.7,
            3.2,
            2.6,
            2.4,
            2.9,
            3.2,
            3.1,
            3.5,
            3.4,
            3.2,
            3.0,
            2.4,
            2.6,
            2.9,
            3.2,
            3.1,
            3.2,
        ]

        fig = go.Figure(
            data=go.Scatter(
                x=dates,
                y=inflation_rates[: len(dates)],
                mode="lines+markers",
                line={"color": "red", "width": 2},
                fill="tonexty",
            )
        )

        fig.add_hline(
            y=2.0,
            line_dash="dash",
            line_color="green",
            annotation_text="Fed Target (2%)",
        )

        fig.update_layout(
            title="US Inflation Rate (CPI)",
            xaxis_title="Date",
            yaxis_title="Inflation Rate %",
            template="plotly_white",
            height=400,
        )

        return fig

    async def create_dashboard(
        self, name: str, description: str, layout_type: LayoutType, created_by: str
    ) -> Dashboard:
        """Create a new dashboard."""
        dashboard_id = str(uuid.uuid4())
        current_time = datetime.now()

        layout = DashboardLayout(
            layout_id=f"layout_{dashboard_id}",
            name=f"{name}_layout",
            layout_type=layout_type,
        )

        dashboard = Dashboard(
            dashboard_id=dashboard_id,
            name=name,
            description=description,
            layout=layout,
            widgets=[],
            created_by=created_by,
            created_at=current_time,
            updated_at=current_time,
        )

        # Store in database
        await self._store_dashboard(dashboard)

        self.dashboards[dashboard_id] = dashboard
        return dashboard

    async def add_widget(
        self,
        dashboard_id: str,
        widget_type: str,
        title: str,
        content: dict[str, Any],
        position: dict[str, int],
        data_source: str | None = None,
    ) -> Widget:
        """Add a widget to a dashboard."""
        widget_id = str(uuid.uuid4())

        widget = Widget(
            widget_id=widget_id,
            widget_type=widget_type,
            title=title,
            content=content,
            position=position,
            data_source=data_source,
        )

        # Store in database
        await self._store_widget(dashboard_id, widget)

        if dashboard_id in self.dashboards:
            self.dashboards[dashboard_id].widgets.append(widget)

        self.widgets[widget_id] = widget
        return widget

    async def _store_dashboard(self, dashboard: Dashboard):
        """Store dashboard in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO dashboards
                (dashboard_id, name, description, layout_config, created_by,
                 created_at, updated_at, is_public, tags, settings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    dashboard.dashboard_id,
                    dashboard.name,
                    dashboard.description,
                    json.dumps(
                        {
                            "layout_id": dashboard.layout.layout_id,
                            "layout_type": dashboard.layout.layout_type.value,
                            "grid_config": dashboard.layout.grid_config,
                            "responsive": dashboard.layout.responsive,
                            "theme": dashboard.layout.theme,
                        }
                    ),
                    dashboard.created_by,
                    dashboard.created_at.isoformat(),
                    dashboard.updated_at.isoformat(),
                    dashboard.is_public,
                    json.dumps(dashboard.tags),
                    json.dumps(dashboard.settings),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing dashboard: {e}")

    async def _store_widget(self, dashboard_id: str, widget: Widget):
        """Store widget in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO widgets
                (widget_id, dashboard_id, widget_type, title, content,
                 position, config, data_source, update_frequency, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    widget.widget_id,
                    dashboard_id,
                    widget.widget_type,
                    widget.title,
                    json.dumps(widget.content),
                    json.dumps(widget.position),
                    json.dumps(widget.config),
                    widget.data_source,
                    widget.update_frequency.value,
                    widget.created_at.isoformat(),
                    widget.updated_at.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing widget: {e}")

    def run_server(self, debug: bool = True, port: int = 8050):
        """Run the dashboard server."""
        logger.info(f"Starting dashboard server on port {port}")
        self.app.run_server(debug=debug, port=port, host="0.0.0.0")


# Example usage and testing
async def main():
    """Example usage of the visualization dashboard engine."""

    # Create dashboard engine
    engine = DashboardEngine()

    # Create a sample dashboard
    dashboard = await engine.create_dashboard(
        name="Financial Market Dashboard",
        description="Comprehensive financial market analysis",
        layout_type=LayoutType.GRID,
        created_by="admin",
    )

    print(f"Created dashboard: {dashboard.name}")

    # Add sample widgets
    await engine.add_widget(
        dashboard.dashboard_id,
        widget_type="chart",
        title="Market Overview",
        content={"chart_type": "line", "data_source": "market_indices"},
        position={"x": 0, "y": 0, "width": 8, "height": 4},
        data_source="market_data",
    )

    await engine.add_widget(
        dashboard.dashboard_id,
        widget_type="indicator",
        title="Key Metrics",
        content={"indicators": ["VIX", "Put/Call", "Advance/Decline"]},
        position={"x": 8, "y": 0, "width": 4, "height": 4},
        data_source="market_indicators",
    )

    print(f"Added {len(dashboard.widgets)} widgets to dashboard")

    # Start the dashboard server
    print("Starting dashboard server...")
    print("Access the dashboard at: http://localhost:8050")

    # Note: In production, you would call engine.run_server()
    # For this demo, we'll just show that it's set up

    return engine


if __name__ == "__main__":
    # Run the dashboard
    engine = asyncio.run(main())
    # Uncomment the following line to actually start the server
    # engine.run_server(debug=True, port=8050)
