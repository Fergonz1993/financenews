#!/usr/bin/env python3
"""
Financial News Summarizer Web Dashboard
A user-friendly Streamlit interface for the enhanced news summarizer.
"""

import streamlit as st
import asyncio
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Add the current directory to the path to import our modules
sys.path.append(os.path.dirname(__file__))

# Import our enhanced summarizer components
try:
    from enhanced_news_summarizer import (
        Config, CacheManager, EnhancedNewsFetcher, 
        EnhancedNewsSummarizer, NewsAnalytics, 
        EnhancedOutputManager, run_enhanced_summarizer
    )
except ImportError:
    st.error("Enhanced news summarizer module not found. Please ensure enhanced_news_summarizer.py is in the same directory.")
    st.stop()

# Configure Streamlit page
st.set_page_config(
    page_title="📈 Financial News Summarizer",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .sentiment-positive {
        color: #28a745;
        font-weight: bold;
    }
    .sentiment-negative {
        color: #dc3545;
        font-weight: bold;
    }
    .sentiment-neutral {
        color: #6c757d;
        font-weight: bold;
    }
    .article-card {
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
        background-color: white;
    }
    .high-impact {
        border-left: 5px solid #ff6b6b;
    }
    .medium-impact {
        border-left: 5px solid #feca57;
    }
    .low-impact {
        border-left: 5px solid #48dbfb;
    }
</style>
""", unsafe_allow_html=True)

def load_recent_results():
    """Load recent analysis results from briefings directory."""
    briefings_dir = Path("./briefings")
    
    if not briefings_dir.exists():
        return None, None, None
    
    # Look for recent JSON files
    json_files = list(briefings_dir.glob("*_data.json"))
    if not json_files:
        return None, None, None
    
    # Get the most recent file
    latest_file = max(json_files, key=lambda x: x.stat().st_mtime)
    
    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        articles = data.get('articles', [])
        analytics = data.get('analytics', {})
        metadata = data.get('metadata', {})
        
        return articles, analytics, metadata
    except Exception as e:
        st.error(f"Error loading recent results: {e}")
        return None, None, None

def display_analytics_dashboard(analytics):
    """Display analytics dashboard."""
    if not analytics:
        st.warning("No analytics data available.")
        return
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📰 Total Articles",
            value=analytics.get('total_articles', 0)
        )
    
    with col2:
        sentiment_dist = analytics.get('sentiment_distribution', {})
        avg_sentiment = sentiment_dist.get('average_score', 0)
        st.metric(
            label="😊 Avg Sentiment",
            value=f"{avg_sentiment:.2f}",
            delta=f"{avg_sentiment:+.2f}"
        )
    
    with col3:
        market_impact = analytics.get('market_impact_summary', {})
        avg_impact = market_impact.get('average_impact', 0)
        st.metric(
            label="🔥 Avg Market Impact",
            value=f"{avg_impact:.2f}",
            delta=f"{avg_impact:.2f}"
        )
    
    with col4:
        processing_stats = analytics.get('processing_stats', {})
        avg_time = processing_stats.get('average_processing_time', 0)
        st.metric(
            label="⚡ Avg Processing Time",
            value=f"{avg_time:.1f}s"
        )
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        # Sentiment distribution pie chart
        sentiment_dist = analytics.get('sentiment_distribution', {}).get('distribution', {})
        if sentiment_dist:
            fig_sentiment = px.pie(
                values=list(sentiment_dist.values()),
                names=list(sentiment_dist.keys()),
                title="📊 Sentiment Distribution",
                color_discrete_map={
                    'positive': '#28a745',
                    'negative': '#dc3545',
                    'neutral': '#6c757d'
                }
            )
            st.plotly_chart(fig_sentiment, use_container_width=True)
    
    with col2:
        # Source distribution bar chart
        source_dist = analytics.get('source_distribution', {}).get('distribution', {})
        if source_dist:
            fig_sources = px.bar(
                x=list(source_dist.keys()),
                y=list(source_dist.values()),
                title="📺 Source Distribution",
                labels={'x': 'Source', 'y': 'Article Count'}
            )
            st.plotly_chart(fig_sources, use_container_width=True)
    
    # Top entities and topics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏢 Top Entities")
        top_entities = analytics.get('top_entities', [])[:10]
        if top_entities:
            entities_df = pd.DataFrame(top_entities)
            fig_entities = px.bar(
                entities_df,
                x='count',
                y='entity',
                orientation='h',
                title="Most Mentioned Entities"
            )
            fig_entities.update_layout(height=400)
            st.plotly_chart(fig_entities, use_container_width=True)
        else:
            st.info("No entity data available.")
    
    with col2:
        st.subheader("🏷️ Trending Topics")
        trending_topics = analytics.get('trending_topics', [])[:10]
        if trending_topics:
            topics_df = pd.DataFrame(trending_topics)
            fig_topics = px.bar(
                topics_df,
                x='count',
                y='topic',
                orientation='h',
                title="Trending Topics"
            )
            fig_topics.update_layout(height=400)
            st.plotly_chart(fig_topics, use_container_width=True)
        else:
            st.info("No topic data available.")

def display_articles(articles):
    """Display articles in a user-friendly format."""
    if not articles:
        st.warning("No articles available.")
        return
    
    # Sort articles by market impact score
    sorted_articles = sorted(
        articles, 
        key=lambda x: x.get('market_impact_score', 0), 
        reverse=True
    )
    
    for i, article in enumerate(sorted_articles):
        # Determine impact level for styling
        impact_score = article.get('market_impact_score', 0)
        if impact_score > 0.7:
            impact_class = "high-impact"
            impact_badge = "🔥 High Impact"
        elif impact_score > 0.4:
            impact_class = "medium-impact"
            impact_badge = "⚠️ Medium Impact"
        else:
            impact_class = "low-impact"
            impact_badge = "ℹ️ Low Impact"
        
        # Sentiment styling
        sentiment = article.get('sentiment', 'neutral')
        sentiment_score = article.get('sentiment_score', 0)
        
        if sentiment == 'positive':
            sentiment_class = "sentiment-positive"
            sentiment_emoji = "😊"
        elif sentiment == 'negative':
            sentiment_class = "sentiment-negative"
            sentiment_emoji = "😟"
        else:
            sentiment_class = "sentiment-neutral"
            sentiment_emoji = "😐"
        
        # Create article card
        with st.container():
            st.markdown(f'<div class="article-card {impact_class}">', unsafe_allow_html=True)
            
            # Header with title and badges
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                title = article.get('summarized_headline') or article.get('title', 'Untitled')
                url = article.get('url', '#')
                st.markdown(f"### [{title}]({url})")
            
            with col2:
                st.markdown(f"**{impact_badge}**")
            
            with col3:
                st.markdown(f'<span class="{sentiment_class}">{sentiment_emoji} {sentiment.title()}</span>', 
                           unsafe_allow_html=True)
            
            # Article metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                st.text(f"📺 Source: {article.get('source', 'Unknown')}")
            with col2:
                pub_date = article.get('published_at', '')
                if pub_date:
                    try:
                        # Try to parse and format the date
                        parsed_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M')
                        st.text(f"📅 Published: {formatted_date}")
                    except:
                        st.text(f"📅 Published: {pub_date}")
            with col3:
                word_count = article.get('word_count', 0)
                st.text(f"📝 Words: {word_count}")
            
            # Summary bullets
            st.markdown("**Key Points:**")
            summary_bullets = article.get('summary_bullets', [])
            for bullet in summary_bullets:
                st.markdown(f"• {bullet}")
            
            # Why it matters
            why_matters = article.get('why_it_matters', '')
            if why_matters:
                st.markdown(f"**💡 Why it matters:** {why_matters}")
            
            # Expandable sections for additional details
            with st.expander("📊 Detailed Metrics & Entities"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Scores:**")
                    st.text(f"Sentiment Score: {sentiment_score:+.2f}")
                    st.text(f"Market Impact: {impact_score:.2f}")
                    
                    # Key entities
                    entities = article.get('key_entities', [])
                    if entities:
                        st.markdown("**Key Entities:**")
                        st.text(", ".join(entities[:5]))
                
                with col2:
                    # Topics
                    topics = article.get('topics', [])
                    if topics:
                        st.markdown("**Topics:**")
                        st.text(", ".join(topics[:5]))
                    
                    # Processing info
                    processed_at = article.get('processed_at')
                    if processed_at:
                        st.markdown("**Processing Info:**")
                        st.text(f"Processed: {processed_at}")
            
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")

async def run_analysis(queries, max_articles):
    """Run the enhanced news summarizer analysis."""
    with st.spinner("🔍 Fetching and analyzing news articles..."):
        try:
            await run_enhanced_summarizer(queries, max_articles=max_articles)
            return True
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            return False

def main():
    """Main dashboard application."""
    
    # Header
    st.markdown('<h1 class="main-header">📈 Financial News Summarizer Dashboard</h1>', 
                unsafe_allow_html=True)
    
    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration")
    
    # Query input
    st.sidebar.subheader("📝 Search Queries")
    
    # Predefined popular queries
    popular_queries = [
        "AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "AMZN",
        "artificial intelligence", "federal reserve", "interest rates",
        "cryptocurrency", "bitcoin", "inflation", "earnings"
    ]
    
    selected_popular = st.sidebar.multiselect(
        "Select from popular queries:",
        popular_queries,
        default=["AAPL", "MSFT", "artificial intelligence"]
    )
    
    # Custom query input
    custom_queries = st.sidebar.text_area(
        "Add custom queries (one per line):",
        placeholder="Enter stock symbols, keywords, or topics..."
    )
    
    # Parse custom queries
    custom_query_list = []
    if custom_queries:
        custom_query_list = [q.strip() for q in custom_queries.split('\n') if q.strip()]
    
    # Combine all queries
    all_queries = list(set(selected_popular + custom_query_list))
    
    # Analysis settings
    st.sidebar.subheader("🔧 Analysis Settings")
    max_articles = st.sidebar.slider("Max articles to analyze:", 5, 100, 25)
    
    # API Key status
    st.sidebar.subheader("🔑 API Status")
    openai_key = os.getenv('OPENAI_API_KEY')
    news_key = os.getenv('NEWS_API_KEY')
    
    if openai_key and openai_key != 'your_openai_api_key_here':
        st.sidebar.success("✅ OpenAI API configured")
    else:
        st.sidebar.error("❌ OpenAI API key missing")
    
    if news_key and news_key != 'your_newsapi_key_here':
        st.sidebar.success("✅ News API configured")
    else:
        st.sidebar.error("❌ News API key missing")
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["🚀 Run Analysis", "📊 Analytics Dashboard", "📰 Articles"])
    
    with tab1:
        st.header("🚀 Run New Analysis")
        
        if all_queries:
            st.write("**Selected queries:**")
            for query in all_queries:
                st.write(f"• {query}")
            
            col1, col2 = st.columns([1, 3])
            
            with col1:
                if st.button("🔍 Start Analysis", type="primary", use_container_width=True):
                    # Check API keys
                    if not openai_key or openai_key == 'your_openai_api_key_here':
                        st.error("❌ OpenAI API key is required. Please configure it in your .env file.")
                    else:
                        # Run analysis
                        success = asyncio.run(run_analysis(all_queries, max_articles))
                        if success:
                            st.success("✅ Analysis completed! Check the other tabs for results.")
                            st.experimental_rerun()
            
            with col2:
                st.info("💡 Analysis will fetch news articles, analyze them with AI, and generate comprehensive reports.")
        
        else:
            st.warning("⚠️ Please select or enter some queries to analyze.")
        
        # Setup section
        st.header("⚙️ Setup")
        st.markdown("""
        **First time setup:**
        1. Copy `env_template` to `.env`
        2. Add your API keys to `.env`
        3. Run the analysis
        
        **Required API keys:**
        - OpenAI API key (for AI analysis)
        - News API key (for news data)
        
        **Optional API keys:**
        - Finnhub API key (for additional financial data)
        - Email configuration (for automated reports)
        """)
        
        if st.button("🛠️ Run Setup Wizard"):
            try:
                import subprocess
                subprocess.run([sys.executable, "setup.py"])
                st.success("Setup wizard completed!")
            except Exception as e:
                st.error(f"Setup failed: {e}")
    
    with tab2:
        st.header("📊 Analytics Dashboard")
        
        # Load recent results
        articles, analytics, metadata = load_recent_results()
        
        if analytics:
            # Show metadata
            if metadata:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📅 Generated", metadata.get('generated_at', 'Unknown')[:10])
                with col2:
                    st.metric("📊 Version", metadata.get('version', 'Unknown'))
                with col3:
                    st.metric("📰 Articles", metadata.get('total_articles', 0))
            
            # Display analytics
            display_analytics_dashboard(analytics)
        else:
            st.info("📊 No analytics data available. Run an analysis first!")
    
    with tab3:
        st.header("📰 Latest Articles")
        
        # Load recent results
        articles, analytics, metadata = load_recent_results()
        
        if articles:
            # Filter and sort options
            col1, col2, col3 = st.columns(3)
            
            with col1:
                sentiment_filter = st.selectbox(
                    "Filter by sentiment:",
                    ["All", "Positive", "Negative", "Neutral"]
                )
            
            with col2:
                impact_filter = st.selectbox(
                    "Filter by market impact:",
                    ["All", "High (>0.7)", "Medium (0.4-0.7)", "Low (<0.4)"]
                )
            
            with col3:
                sort_by = st.selectbox(
                    "Sort by:",
                    ["Market Impact", "Sentiment Score", "Published Date"]
                )
            
            # Apply filters
            filtered_articles = articles.copy()
            
            if sentiment_filter != "All":
                filtered_articles = [
                    a for a in filtered_articles 
                    if a.get('sentiment', '').lower() == sentiment_filter.lower()
                ]
            
            if impact_filter != "All":
                if impact_filter.startswith("High"):
                    filtered_articles = [a for a in filtered_articles if a.get('market_impact_score', 0) > 0.7]
                elif impact_filter.startswith("Medium"):
                    filtered_articles = [a for a in filtered_articles if 0.4 <= a.get('market_impact_score', 0) <= 0.7]
                elif impact_filter.startswith("Low"):
                    filtered_articles = [a for a in filtered_articles if a.get('market_impact_score', 0) < 0.4]
            
            st.write(f"**Showing {len(filtered_articles)} of {len(articles)} articles**")
            
            # Display filtered articles
            display_articles(filtered_articles)
        else:
            st.info("📰 No articles available. Run an analysis first!")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "🤖 **Enhanced Financial News Summarizer** • "
        "Powered by AI • "
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

if __name__ == "__main__":
    main() 