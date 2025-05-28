import React, { useState, useEffect } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  CardActionArea,
  Chip,
  CircularProgress,
  Grid,
  Typography,
  Paper,
  TextField,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Alert,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  TrendingFlat,
} from '@mui/icons-material';
import { getArticles, getSources, getTopics } from '../api/newsApi';

const Home = () => {
  // State for articles and loading
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // State for filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSource, setSelectedSource] = useState('');
  const [selectedSentiment, setSelectedSentiment] = useState('');
  const [selectedTopic, setSelectedTopic] = useState('');
  
  // State for filter options
  const [sources, setSources] = useState([]);
  const [topics, setTopics] = useState([]);

  // Load articles on component mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Create filter params
        const params = {};
        if (selectedSource) params.source = selectedSource;
        if (selectedSentiment) params.sentiment = selectedSentiment;
        if (selectedTopic) params.topic = selectedTopic;
        
        const articlesData = await getArticles(params);
        setArticles(articlesData);
        setError(null);
      } catch (err) {
        console.error('Error fetching articles:', err);
        setError('Failed to fetch articles. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedSource, selectedSentiment, selectedTopic]);

  // Load filter options on component mount
  useEffect(() => {
    const fetchFilterOptions = async () => {
      try {
        const [sourcesData, topicsData] = await Promise.all([
          getSources(),
          getTopics(),
        ]);
        setSources(sourcesData);
        setTopics(topicsData);
      } catch (err) {
        console.error('Error fetching filter options:', err);
      }
    };

    fetchFilterOptions();
  }, []);

  // Filter articles by search query
  const filteredArticles = articles.filter((article) => {
    if (!searchQuery) return true;
    
    const query = searchQuery.toLowerCase();
    return (
      article.title.toLowerCase().includes(query) ||
      article.summarized_headline?.toLowerCase().includes(query) ||
      article.key_entities.some(entity => entity.toLowerCase().includes(query))
    );
  });

  // Render sentiment icon based on sentiment
  const renderSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case 'positive':
        return <TrendingUp className="sentiment-positive" />;
      case 'negative':
        return <TrendingDown className="sentiment-negative" />;
      default:
        return <TrendingFlat className="sentiment-neutral" />;
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Financial News
      </Typography>
      
      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Search articles"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              variant="outlined"
              placeholder="Search by title, summary, or entity"
            />
          </Grid>
          <Grid item xs={12} sm={4} md={2}>
            <FormControl fullWidth>
              <InputLabel>Source</InputLabel>
              <Select
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
                label="Source"
              >
                <MenuItem value="">
                  <em>All Sources</em>
                </MenuItem>
                {sources.map((source) => (
                  <MenuItem key={source.id} value={source.id}>
                    {source.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={4} md={2}>
            <FormControl fullWidth>
              <InputLabel>Sentiment</InputLabel>
              <Select
                value={selectedSentiment}
                onChange={(e) => setSelectedSentiment(e.target.value)}
                label="Sentiment"
              >
                <MenuItem value="">
                  <em>All Sentiments</em>
                </MenuItem>
                <MenuItem value="positive">Positive</MenuItem>
                <MenuItem value="neutral">Neutral</MenuItem>
                <MenuItem value="negative">Negative</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={4} md={2}>
            <FormControl fullWidth>
              <InputLabel>Topic</InputLabel>
              <Select
                value={selectedTopic}
                onChange={(e) => setSelectedTopic(e.target.value)}
                label="Topic"
              >
                <MenuItem value="">
                  <em>All Topics</em>
                </MenuItem>
                {topics.map((topic) => (
                  <MenuItem key={topic.id} value={topic.id}>
                    {topic.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>
      
      {/* Error message */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      
      {/* Loading indicator */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* Articles list */}
          {filteredArticles.length === 0 ? (
            <Alert severity="info" sx={{ mt: 2 }}>
              No articles found matching your criteria.
            </Alert>
          ) : (
            <Grid container spacing={3}>
              {filteredArticles.map((article) => (
                <Grid item xs={12} sm={6} md={4} key={article.id}>
                  <Card className="article-card" elevation={2}>
                    <CardActionArea component={RouterLink} to={`/articles/${article.id}`}>
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Chip
                            label={article.source}
                            size="small"
                            color="primary"
                            variant="outlined"
                          />
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            {renderSentimentIcon(article.sentiment)}
                            <Typography variant="caption" sx={{ ml: 0.5 }}>
                              {article.sentiment_score
                                ? Math.round(article.sentiment_score * 100) + '%'
                                : ''}
                            </Typography>
                          </Box>
                        </Box>
                        <Typography variant="h6" component="h2" gutterBottom>
                          {article.summarized_headline || article.title}
                        </Typography>
                        {article.summary_bullets && article.summary_bullets.length > 0 && (
                          <Typography variant="body2" color="text.secondary" component="p">
                            {article.summary_bullets[0]}
                          </Typography>
                        )}
                        <Box sx={{ mt: 2 }}>
                          {article.key_entities &&
                            article.key_entities.slice(0, 3).map((entity, index) => (
                              <Chip
                                key={index}
                                label={entity}
                                size="small"
                                sx={{ mr: 0.5, mb: 0.5 }}
                              />
                            ))}
                        </Box>
                      </CardContent>
                    </CardActionArea>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </>
      )}
    </Box>
  );
};

export default Home;
