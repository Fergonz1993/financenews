import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import {
  ArrowBack,
  TrendingUp,
  TrendingDown,
  TrendingFlat,
  Link as LinkIcon,
} from '@mui/icons-material';
import { getArticleById } from '../api/newsApi';

const ArticleDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchArticle = async () => {
      try {
        setLoading(true);
        const data = await getArticleById(id);
        setArticle(data);
        setError(null);
      } catch (err) {
        console.error(`Error fetching article ${id}:`, err);
        setError('Failed to fetch article details. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchArticle();
  }, [id]);

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
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate(-1)}
        sx={{ mb: 3 }}
      >
        Back to Articles
      </Button>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : article ? (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card elevation={3}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                  <Chip
                    label={article.source}
                    color="primary"
                    variant="outlined"
                    sx={{ mr: 1 }}
                  />
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {renderSentimentIcon(article.sentiment)}
                    <Typography variant="body2" sx={{ ml: 0.5 }}>
                      {article.sentiment} ({article.sentiment_score
                        ? Math.round(article.sentiment_score * 100) + '%'
                        : ''}
                      )
                    </Typography>
                  </Box>
                </Box>

                <Typography variant="h4" component="h1" gutterBottom>
                  {article.summarized_headline || article.title}
                </Typography>

                <Box sx={{ my: 2 }}>
                  <Button
                    startIcon={<LinkIcon />}
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="outlined"
                    size="small"
                  >
                    Original Article
                  </Button>
                </Box>

                <Divider sx={{ my: 3 }} />

                <Typography variant="h6" gutterBottom>
                  Key Takeaways
                </Typography>
                {article.summary_bullets && article.summary_bullets.length > 0 ? (
                  <Box component="ul" sx={{ pl: 2 }}>
                    {article.summary_bullets.map((bullet, index) => (
                      <Typography key={index} component="li" paragraph>
                        {bullet}
                      </Typography>
                    ))}
                  </Box>
                ) : (
                  <Typography variant="body1" paragraph>
                    No summary available.
                  </Typography>
                )}

                {article.why_it_matters && (
                  <>
                    <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
                      Why It Matters
                    </Typography>
                    <Typography variant="body1" paragraph>
                      {article.why_it_matters}
                    </Typography>
                  </>
                )}

                <Divider sx={{ my: 3 }} />

                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="h6" gutterBottom>
                        Key Entities
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {article.key_entities && article.key_entities.length > 0 ? (
                          article.key_entities.map((entity, index) => (
                            <Chip key={index} label={entity} />
                          ))
                        ) : (
                          <Typography variant="body2">No entities identified.</Typography>
                        )}
                      </Box>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="h6" gutterBottom>
                        Topics
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {article.topics && article.topics.length > 0 ? (
                          article.topics.map((topic, index) => (
                            <Chip
                              key={index}
                              label={topic}
                              color="secondary"
                              variant="outlined"
                            />
                          ))
                        ) : (
                          <Typography variant="body2">No topics identified.</Typography>
                        )}
                      </Box>
                    </Paper>
                  </Grid>
                </Grid>

                {article.market_impact_score !== null && (
                  <Paper variant="outlined" sx={{ p: 2, mt: 3 }}>
                    <Typography variant="h6" gutterBottom>
                      Market Impact
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Box
                        sx={{
                          width: '100%',
                          height: 10,
                          bgcolor: '#e0e0e0',
                          borderRadius: 5,
                          mr: 2,
                        }}
                      >
                        <Box
                          sx={{
                            width: `${article.market_impact_score * 100}%`,
                            height: '100%',
                            bgcolor: 
                              article.market_impact_score > 0.7 
                                ? 'error.main' 
                                : article.market_impact_score > 0.4 
                                ? 'warning.main' 
                                : 'success.main',
                            borderRadius: 5,
                          }}
                        />
                      </Box>
                      <Typography>
                        {Math.round(article.market_impact_score * 100)}%
                      </Typography>
                    </Box>
                  </Paper>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      ) : (
        <Alert severity="warning">Article not found.</Alert>
      )}
    </Box>
  );
};

export default ArticleDetail;
