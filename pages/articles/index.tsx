import React, { useState, useEffect } from 'react';
import { 
  Grid, 
  Typography, 
  Paper, 
  Box, 
  TextField, 
  MenuItem, 
  Select, 
  FormControl, 
  InputLabel,
  CircularProgress,
  Card,
  CardContent,
  CardActionArea,
  Chip
} from '@mui/material';
import Layout from '../../components/Layout';
import { useRouter } from 'next/router';

// Article type definition
type Article = {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  summarized_headline?: string;
  summary_bullets?: string[];
  sentiment?: string;
  sentiment_score?: number;
  market_impact_score?: number;
  key_entities?: string[];
  topics?: string[];
};

export default function ArticlesPage() {
  const router = useRouter();
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [sources, setSources] = useState<{id: string, name: string}[]>([]);
  const [topics, setTopics] = useState<{id: string, name: string}[]>([]);
  
  // Filter states
  const [source, setSource] = useState('');
  const [topic, setTopic] = useState('');
  const [sentiment, setSentiment] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [sortOrder, setSortOrder] = useState('desc');

  useEffect(() => {
    // Fetch filter options
    const fetchOptions = async () => {
      try {
        const [sourcesRes, topicsRes] = await Promise.all([
          fetch('/api/sources'),
          fetch('/api/topics')
        ]);
        
        if (sourcesRes.ok && topicsRes.ok) {
          const sourcesData = await sourcesRes.json();
          const topicsData = await topicsRes.json();
          
          setSources(sourcesData);
          setTopics(topicsData);
        }
      } catch (error) {
        console.error('Error fetching filter options:', error);
      }
    };
    
    fetchOptions();
  }, []);

  // Effect to fetch articles with filters
  useEffect(() => {
    const fetchArticles = async () => {
      setLoading(true);
      
      // Build query string
      const params = new URLSearchParams();
      if (source) params.append('source', source);
      if (topic) params.append('topic', topic);
      if (sentiment) params.append('sentiment', sentiment);
      if (search) params.append('search', search);
      params.append('sort_by', sortBy);
      params.append('sort_order', sortOrder);
      params.append('limit', '20');
      
      try {
        const response = await fetch(`/api/articles?${params.toString()}`);
        if (!response.ok) throw new Error('Failed to fetch articles');
        const data = await response.json();
        setArticles(data);
      } catch (error) {
        console.error('Error fetching articles:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchArticles();
  }, [source, topic, sentiment, search, sortBy, sortOrder]);

  // Handle article click
  const handleArticleClick = (id: string) => {
    router.push(`/articles/${id}`);
  };

  // Get sentiment color
  const getSentimentColor = (sentiment?: string) => {
    switch (sentiment) {
      case 'positive': return 'success';
      case 'negative': return 'error';
      case 'neutral': return 'warning';
      default: return 'default';
    }
  };

  return (
    <Layout title="Financial News Articles" description="Browse and search financial news articles">
      <Typography variant="h4" component="h1" gutterBottom>
        Financial News Articles
      </Typography>
      
      {/* Filters */}
      <Paper sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={3}>
            <TextField
              label="Search"
              fullWidth
              variant="outlined"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Grid>
          
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={source}
                label="Source"
                onChange={(e) => setSource(e.target.value as string)}
              >
                <MenuItem value="">All Sources</MenuItem>
                {sources.map(s => (
                  <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Topic</InputLabel>
              <Select
                value={topic}
                label="Topic"
                onChange={(e) => setTopic(e.target.value as string)}
              >
                <MenuItem value="">All Topics</MenuItem>
                {topics.map(t => (
                  <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sentiment</InputLabel>
              <Select
                value={sentiment}
                label="Sentiment"
                onChange={(e) => setSentiment(e.target.value as string)}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="positive">Positive</MenuItem>
                <MenuItem value="neutral">Neutral</MenuItem>
                <MenuItem value="negative">Negative</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={sortBy}
                label="Sort By"
                onChange={(e) => setSortBy(e.target.value as string)}
              >
                <MenuItem value="date">Date</MenuItem>
                <MenuItem value="relevance">Relevance</MenuItem>
                <MenuItem value="sentiment">Sentiment</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>
      
      {/* Articles */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 5 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Grid container spacing={3}>
          {articles.length > 0 ? (
            articles.map((article) => (
              <Grid item xs={12} sm={6} md={4} key={article.id}>
                <Card 
                  sx={{ 
                    height: '100%', 
                    display: 'flex', 
                    flexDirection: 'column',
                    borderLeft: 4,
                    borderColor: getSentimentColor(article.sentiment)
                  }}
                >
                  <CardActionArea 
                    onClick={() => handleArticleClick(article.id)}
                    sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}
                  >
                    <CardContent sx={{ flexGrow: 1, width: '100%' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="caption" color="text.secondary">
                          {article.source}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(article.published_at).toLocaleDateString()}
                        </Typography>
                      </Box>
                      
                      <Typography variant="h6" component="h2" gutterBottom>
                        {article.title}
                      </Typography>
                      
                      <Typography variant="body2" color="text.secondary" paragraph>
                        {article.summarized_headline}
                      </Typography>
                      
                      <Box sx={{ mt: 'auto', pt: 2 }}>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          {article.topics?.slice(0, 3).map(topic => (
                            <Chip 
                              key={topic} 
                              label={topic} 
                              size="small" 
                              variant="outlined" 
                              color="primary"
                            />
                          ))}
                          
                          {article.sentiment && (
                            <Chip
                              label={article.sentiment}
                              size="small"
                              color={getSentimentColor(article.sentiment) as any}
                            />
                          )}
                        </Box>
                      </Box>
                    </CardContent>
                  </CardActionArea>
                </Card>
              </Grid>
            ))
          ) : (
            <Grid item xs={12}>
              <Typography align="center" color="text.secondary">
                No articles found matching your criteria.
              </Typography>
            </Grid>
          )}
        </Grid>
      )}
    </Layout>
  );
}
