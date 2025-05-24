#!/usr/bin/env python3
"""
Enhanced Graph Neural Network Analyzer for Financial Sentiment
Implements cutting-edge GNN techniques for relationship analysis and sentiment propagation.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, SAGEConv, global_mean_pool
from torch_geometric.data import Data, DataLoader
import networkx as nx
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set
import logging
from dataclasses import dataclass
import json
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import asyncio
import aiohttp
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class FinancialEntity:
    """Represents a financial entity in the knowledge graph."""
    id: str
    name: str
    entity_type: str  # 'company', 'person', 'sector', 'event', 'location'
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    country: Optional[str] = None
    sentiment_score: float = 0.0
    confidence: float = 0.0
    last_updated: Optional[datetime] = None
    
    def __hash__(self):
        return hash(self.id)

class FinancialGraphBuilder:
    """Builds knowledge graphs from financial news and market data."""
    
    def __init__(self):
        self.entities: Dict[str, FinancialEntity] = {}
        self.relationships: List[Tuple[str, str, str, float]] = []  # (source, target, rel_type, weight)
        self.graph = nx.DiGraph()
        
    async def extract_entities_from_articles(self, articles: List) -> List[FinancialEntity]:
        """Extract and classify financial entities from news articles."""
        entities = []
        
        # Known financial entities and their types
        company_patterns = [
            r'\b([A-Z]{1,5})\b',  # Stock tickers
            r'\b([A-Z][a-z]+ (?:Corp|Inc|Ltd|LLC|Company|Technologies|Systems|Group))\b'
        ]
        
        person_patterns = [
            r'\bCEO\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b',
            r'\bChief Executive\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
        ]
        
        for article in articles:
            content = f"{article.title} {article.content}"
            
            # Extract company entities
            import re
            for pattern in company_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    entity_id = f"company_{match.replace(' ', '_').upper()}"
                    if entity_id not in self.entities:
                        self.entities[entity_id] = FinancialEntity(
                            id=entity_id,
                            name=match,
                            entity_type='company',
                            sentiment_score=article.sentiment_score or 0.0,
                            last_updated=datetime.now()
                        )
                        entities.append(self.entities[entity_id])
                    else:
                        # Update sentiment with moving average
                        existing = self.entities[entity_id]
                        existing.sentiment_score = (existing.sentiment_score + 
                                                  (article.sentiment_score or 0.0)) / 2
        
        return entities
    
    def build_relationship_graph(self, articles: List) -> nx.DiGraph:
        """Build a directed graph of entity relationships."""
        
        # Add entities as nodes
        for entity in self.entities.values():
            self.graph.add_node(
                entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                sentiment=entity.sentiment_score,
                market_cap=entity.market_cap or 0
            )
        
        # Add relationships based on co-occurrence and known business relationships
        self._add_cooccurrence_edges(articles)
        self._add_sector_relationships()
        self._add_supply_chain_relationships()
        
        return self.graph
    
    def _add_cooccurrence_edges(self, articles: List):
        """Add edges based on entity co-occurrence in articles."""
        for article in articles:
            # Find entities mentioned in this article
            mentioned_entities = []
            content = f"{article.title} {article.content}".lower()
            
            for entity in self.entities.values():
                if entity.name.lower() in content:
                    mentioned_entities.append(entity)
            
            # Create edges between co-occurring entities
            for i, entity1 in enumerate(mentioned_entities):
                for entity2 in mentioned_entities[i+1:]:
                    weight = self._calculate_relationship_strength(entity1, entity2, article)
                    self.graph.add_edge(
                        entity1.id, 
                        entity2.id, 
                        weight=weight,
                        relationship_type='cooccurrence',
                        sentiment_impact=article.sentiment_score or 0.0
                    )
    
    def _calculate_relationship_strength(self, entity1: FinancialEntity, 
                                       entity2: FinancialEntity, article) -> float:
        """Calculate the strength of relationship between two entities."""
        base_weight = 1.0
        
        # Boost weight if entities are in same sentence
        content = article.content.lower()
        sentences = content.split('.')
        
        for sentence in sentences:
            if (entity1.name.lower() in sentence and 
                entity2.name.lower() in sentence):
                base_weight *= 1.5
                break
        
        # Boost for high-impact articles
        if hasattr(article, 'market_impact_score') and article.market_impact_score:
            base_weight *= (1 + article.market_impact_score)
        
        return min(base_weight, 5.0)  # Cap at 5.0
    
    def _add_sector_relationships(self):
        """Add relationships between entities in the same sector."""
        sectors = {}
        for entity in self.entities.values():
            if entity.sector:
                if entity.sector not in sectors:
                    sectors[entity.sector] = []
                sectors[entity.sector].append(entity)
        
        # Connect entities within the same sector
        for sector, entities in sectors.items():
            for i, entity1 in enumerate(entities):
                for entity2 in entities[i+1:]:
                    if not self.graph.has_edge(entity1.id, entity2.id):
                        self.graph.add_edge(
                            entity1.id, 
                            entity2.id,
                            weight=0.3,
                            relationship_type='sector_peer'
                        )

class AdvancedGNNModel(nn.Module):
    """Advanced Graph Neural Network for financial sentiment propagation."""
    
    def __init__(self, input_dim: int, hidden_dim: int = 128, output_dim: int = 1, 
                 num_layers: int = 3, dropout: float = 0.1):
        super().__init__()
        
        self.num_layers = num_layers
        self.dropout = dropout
        
        # Multi-layer GNN with attention
        self.convs = nn.ModuleList([
            GATConv(input_dim if i == 0 else hidden_dim, 
                   hidden_dim, heads=4, dropout=dropout)
            for i in range(num_layers)
        ])
        
        # Output layers
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 4, hidden_dim),  # 4 heads
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim)
        )
        
        # Sentiment propagation layer
        self.sentiment_propagator = nn.LSTM(hidden_dim * 4, hidden_dim, batch_first=True)
        
    def forward(self, x, edge_index, batch=None):
        """Forward pass through the GNN."""
        
        # Apply GNN layers with residual connections
        h = x
        for i, conv in enumerate(self.convs):
            h_new = F.relu(conv(h, edge_index))
            h_new = F.dropout(h_new, p=self.dropout, training=self.training)
            
            # Residual connection (if dimensions match)
            if h.size(-1) == h_new.size(-1):
                h = h + h_new
            else:
                h = h_new
        
        # Global pooling for graph-level prediction
        if batch is not None:
            h = global_mean_pool(h, batch)
        else:
            h = h.mean(dim=0, keepdim=True)
        
        # Final prediction
        output = self.classifier(h)
        return output, h

class SentimentPropagationEngine:
    """Engine for predicting sentiment propagation through financial networks."""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.scaler = StandardScaler()
        self.entity_encoder = {}
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        if model_path:
            self.load_model(model_path)
    
    def prepare_graph_data(self, graph: nx.DiGraph) -> Data:
        """Convert NetworkX graph to PyTorch Geometric data format."""
        
        # Create node feature matrix
        nodes = list(graph.nodes())
        node_features = []
        
        for node in nodes:
            attrs = graph.nodes[node]
            features = [
                attrs.get('sentiment', 0.0),
                attrs.get('market_cap', 0.0) / 1e9,  # Normalize to billions
                1.0 if attrs.get('entity_type') == 'company' else 0.0,
                1.0 if attrs.get('entity_type') == 'person' else 0.0,
                graph.degree(node) / len(nodes),  # Centrality measure
            ]
            node_features.append(features)
        
        x = torch.tensor(node_features, dtype=torch.float)
        
        # Create edge index
        edge_list = []
        edge_weights = []
        
        for source, target, attrs in graph.edges(data=True):
            source_idx = nodes.index(source)
            target_idx = nodes.index(target)
            edge_list.extend([[source_idx, target_idx], [target_idx, source_idx]])  # Bidirectional
            weight = attrs.get('weight', 1.0)
            edge_weights.extend([weight, weight])
        
        edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
        edge_weights = torch.tensor(edge_weights, dtype=torch.float)
        
        return Data(x=x, edge_index=edge_index, edge_attr=edge_weights)
    
    def train_model(self, graphs: List[nx.DiGraph], sentiment_targets: List[float]):
        """Train the GNN model on historical data."""
        
        # Prepare training data
        data_list = []
        for graph, target in zip(graphs, sentiment_targets):
            data = self.prepare_graph_data(graph)
            data.y = torch.tensor([target], dtype=torch.float)
            data_list.append(data)
        
        # Initialize model
        input_dim = data_list[0].x.size(1)
        self.model = AdvancedGNNModel(input_dim).to(self.device)
        
        # Training setup
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001, weight_decay=1e-4)
        criterion = nn.MSELoss()
        
        # Training loop
        self.model.train()
        for epoch in range(100):
            total_loss = 0
            for data in data_list:
                data = data.to(self.device)
                optimizer.zero_grad()
                
                output, _ = self.model(data.x, data.edge_index)
                loss = criterion(output.squeeze(), data.y)
                
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
            if epoch % 20 == 0:
                logger.info(f"Epoch {epoch}, Loss: {total_loss/len(data_list):.4f}")
    
    def predict_sentiment_propagation(self, graph: nx.DiGraph, 
                                    initial_shocks: Dict[str, float]) -> Dict[str, float]:
        """Predict how sentiment will propagate through the network."""
        
        if self.model is None:
            logger.warning("Model not trained. Using simple propagation.")
            return self._simple_propagation(graph, initial_shocks)
        
        # Apply initial sentiment shocks
        for node_id, sentiment in initial_shocks.items():
            if node_id in graph.nodes:
                graph.nodes[node_id]['sentiment'] = sentiment
        
        # Prepare data and predict
        data = self.prepare_graph_data(graph).to(self.device)
        
        self.model.eval()
        with torch.no_grad():
            _, embeddings = self.model(data.x, data.edge_index)
            
            # Convert embeddings back to sentiment scores
            sentiment_predictions = {}
            for i, node in enumerate(graph.nodes()):
                # Use embedding magnitude as sentiment strength
                sentiment_score = torch.norm(embeddings[i]).item()
                sentiment_predictions[node] = sentiment_score
        
        return sentiment_predictions
    
    def _simple_propagation(self, graph: nx.DiGraph, 
                          initial_shocks: Dict[str, float]) -> Dict[str, float]:
        """Simple PageRank-style sentiment propagation as fallback."""
        
        # Initialize sentiment values
        sentiment_values = {node: 0.0 for node in graph.nodes()}
        sentiment_values.update(initial_shocks)
        
        # Iterative propagation
        for iteration in range(10):
            new_values = sentiment_values.copy()
            
            for node in graph.nodes():
                if node not in initial_shocks:  # Don't update shock sources
                    incoming_sentiment = 0.0
                    total_weight = 0.0
                    
                    for predecessor in graph.predecessors(node):
                        edge_data = graph.edges[predecessor, node]
                        weight = edge_data.get('weight', 1.0)
                        incoming_sentiment += sentiment_values[predecessor] * weight
                        total_weight += weight
                    
                    if total_weight > 0:
                        # Damping factor to prevent infinite amplification
                        damping = 0.85
                        new_values[node] = (damping * incoming_sentiment / total_weight + 
                                          (1 - damping) * sentiment_values[node])
            
            sentiment_values = new_values
        
        return sentiment_values

class FinancialGraphAnalyzer:
    """Main class for comprehensive financial graph analysis."""
    
    def __init__(self, enable_gpu: bool = True):
        self.graph_builder = FinancialGraphBuilder()
        self.sentiment_engine = SentimentPropagationEngine()
        self.enable_gpu = enable_gpu and torch.cuda.is_available()
        
        if self.enable_gpu:
            logger.info("🚀 GPU acceleration enabled for GNN processing")
        else:
            logger.info("💻 Using CPU for GNN processing")
    
    async def analyze_articles(self, articles: List) -> Dict:
        """Complete analysis pipeline for financial articles."""
        
        logger.info("🔍 Extracting financial entities...")
        entities = await self.graph_builder.extract_entities_from_articles(articles)
        
        logger.info("🕸️ Building relationship graph...")
        graph = self.graph_builder.build_relationship_graph(articles)
        
        logger.info("📊 Analyzing network structure...")
        network_metrics = self._analyze_network_structure(graph)
        
        logger.info("🌊 Predicting sentiment propagation...")
        # Simulate sentiment shocks from high-impact articles
        sentiment_shocks = {}
        for article in articles:
            if hasattr(article, 'market_impact_score') and article.market_impact_score > 0.7:
                # Find entities mentioned in high-impact articles
                for entity in entities:
                    if entity.name.lower() in article.content.lower():
                        sentiment_shocks[entity.id] = article.sentiment_score or 0.0
        
        propagated_sentiment = self.sentiment_engine.predict_sentiment_propagation(
            graph, sentiment_shocks)
        
        return {
            'entities': [entity.__dict__ for entity in entities],
            'graph_metrics': network_metrics,
            'sentiment_propagation': propagated_sentiment,
            'risk_clusters': self._identify_risk_clusters(graph, propagated_sentiment),
            'market_influence_ranking': self._rank_market_influence(graph, entities)
        }
    
    def _analyze_network_structure(self, graph: nx.DiGraph) -> Dict:
        """Analyze the structure of the financial network."""
        
        metrics = {}
        
        if len(graph.nodes()) > 0:
            # Centrality measures
            betweenness = nx.betweenness_centrality(graph)
            closeness = nx.closeness_centrality(graph)
            pagerank = nx.pagerank(graph)
            
            # Network statistics
            metrics = {
                'num_entities': len(graph.nodes()),
                'num_relationships': len(graph.edges()),
                'network_density': nx.density(graph),
                'avg_clustering': nx.average_clustering(graph.to_undirected()),
                'most_central_entities': sorted(betweenness.items(), 
                                              key=lambda x: x[1], reverse=True)[:5],
                'most_influential_entities': sorted(pagerank.items(), 
                                                  key=lambda x: x[1], reverse=True)[:5]
            }
        
        return metrics
    
    def _identify_risk_clusters(self, graph: nx.DiGraph, 
                              sentiment_scores: Dict[str, float]) -> List[Dict]:
        """Identify clusters of entities with high risk correlation."""
        
        # Find negative sentiment clusters
        negative_entities = {k: v for k, v in sentiment_scores.items() if v < -0.3}
        
        if not negative_entities:
            return []
        
        # Use community detection to find risk clusters
        undirected_graph = graph.to_undirected()
        try:
            communities = nx.community.greedy_modularity_communities(undirected_graph)
            
            risk_clusters = []
            for i, community in enumerate(communities):
                cluster_entities = list(community)
                cluster_sentiment = np.mean([sentiment_scores.get(e, 0) for e in cluster_entities])
                
                if cluster_sentiment < -0.2:  # Negative sentiment cluster
                    risk_clusters.append({
                        'cluster_id': i,
                        'entities': cluster_entities,
                        'avg_sentiment': cluster_sentiment,
                        'size': len(cluster_entities),
                        'risk_level': 'HIGH' if cluster_sentiment < -0.5 else 'MEDIUM'
                    })
            
            return sorted(risk_clusters, key=lambda x: x['avg_sentiment'])
        
        except Exception as e:
            logger.warning(f"Community detection failed: {e}")
            return []
    
    def _rank_market_influence(self, graph: nx.DiGraph, 
                             entities: List[FinancialEntity]) -> List[Dict]:
        """Rank entities by their potential market influence."""
        
        influence_scores = []
        
        for entity in entities:
            if entity.id in graph.nodes():
                # Combine multiple influence factors
                centrality = nx.betweenness_centrality(graph).get(entity.id, 0)
                degree = graph.degree(entity.id)
                market_cap_factor = np.log(entity.market_cap + 1) if entity.market_cap else 0
                
                influence_score = (centrality * 0.4 + 
                                 (degree / len(graph.nodes())) * 0.3 + 
                                 market_cap_factor * 0.3)
                
                influence_scores.append({
                    'entity_id': entity.id,
                    'entity_name': entity.name,
                    'influence_score': influence_score,
                    'centrality': centrality,
                    'connections': degree,
                    'market_cap': entity.market_cap
                })
        
        return sorted(influence_scores, key=lambda x: x['influence_score'], reverse=True)

# Usage example integration
async def integrate_with_news_summarizer(articles: List) -> Dict:
    """Integration function for the existing news summarizer."""
    
    analyzer = FinancialGraphAnalyzer()
    
    try:
        analysis_results = await analyzer.analyze_articles(articles)
        
        logger.info("✅ Graph analysis completed successfully")
        return analysis_results
        
    except Exception as e:
        logger.error(f"❌ Graph analysis failed: {e}")
        return {
            'error': str(e),
            'entities': [],
            'graph_metrics': {},
            'sentiment_propagation': {},
            'risk_clusters': [],
            'market_influence_ranking': []
        }

if __name__ == "__main__":
    # Test the graph analyzer
    import asyncio
    
    # Mock article data for testing
    class MockArticle:
        def __init__(self, title, content, sentiment_score=0.0, market_impact_score=0.5):
            self.title = title
            self.content = content
            self.sentiment_score = sentiment_score
            self.market_impact_score = market_impact_score
    
    test_articles = [
        MockArticle(
            "Apple Reports Strong Q4 Earnings", 
            "Apple Inc reported strong quarterly earnings with iPhone sales exceeding expectations.",
            sentiment_score=0.8, market_impact_score=0.9
        ),
        MockArticle(
            "Microsoft Azure Revenue Growth", 
            "Microsoft Corporation showed robust cloud revenue growth in Azure services.",
            sentiment_score=0.6, market_impact_score=0.7
        )
    ]
    
    async def test_analysis():
        results = await integrate_with_news_summarizer(test_articles)
        print(json.dumps(results, indent=2, default=str))
    
    asyncio.run(test_analysis()) 