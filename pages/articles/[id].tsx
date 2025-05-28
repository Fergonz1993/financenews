import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { 
  Box, 
  Typography, 
  Paper, 
  Chip, 
  Grid, 
  Divider, 
  Button,
  CircularProgress,
  Link as MuiLink
} from '@mui/material';
import {
  BookmarkBorder as BookmarkIcon,
  Bookmark as BookmarkFilledIcon,
  ArrowBack as ArrowBackIcon,
  Share as ShareIcon
} from '@mui/icons-material';
import Layout from '../../components/Layout';

// Article type definition
type Article = {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  content: string;
  summarized_headline?: string;
  summary_bullets?: string[];
  sentiment?: string;
  sentiment_score?: number;
  market_impact_score?: number;
  key_entities?: string[];
  topics?: string[];
  is_saved?: boolean;
};

export default function ArticlePage() {
  const router = useRouter();
  const { id } = router.query;
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!id) return;

    const fetchArticle = async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/articles/${id}?user_id=user1`);
        if (!response.ok) throw new Error('Failed to fetch article');
        const data = await response.json();
        setArticle(data);
        setSaved(data.is_saved || false);
      } catch (error) {
        console.error('Error fetching article:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchArticle();
  }, [id]);

  const toggleSaved = async () => {
    if (!article) return;
    
    try {
      const endpoint = `/api/users/user1/saved-articles/${article.id}`;
      const method = saved ? 'DELETE' : 'POST';
      
      const response = await fetch(endpoint, { method });
      if (!response.ok) throw new Error('Failed to update saved status');
      
      setSaved(!saved);
    } catch (error) {
      console.error('Error updating saved status:', error);
    }
  };

  const getSentimentColor = (sentiment?: string) => {
    switch (sentiment) {
      case 'positive': return 'success';
      case 'negative': return 'error';
      case 'neutral': return 'warning';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <Layout title="Loading Article" description="Loading article...">
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <CircularProgress />
        </Box>
      </Layout>
    );
  }

  if (!article) {
    return (
      <Layout title="Article Not Found" description="The requested article could not be found">
        <Box sx={{ textAlign: 'center', py: 5 }}>
          <Typography variant="h5" gutterBottom>Article Not Found</Typography>
          <Button 
            startIcon={<ArrowBackIcon />}
            variant="contained" 
            onClick={() => router.push('/articles')}
            sx={{ mt: 2 }}
          >
            Back to Articles
          </Button>
        </Box>
      </Layout>
    );
  }

  return (
    <Layout title={article.title} description={article.summarized_headline || article.title}>
      <Button 
        startIcon={<ArrowBackIcon />}
        variant="outlined" 
        onClick={() => router.push('/articles')}
        sx={{ mb: 3 }}
      >
        Back to Articles
      </Button>
      
      <Paper sx={{ p: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="caption" color="text.secondary">
            {article.source} • {new Date(article.published_at).toLocaleString()}
          </Typography>
          <Box>
            <Button 
              startIcon={saved ? <BookmarkFilledIcon /> : <BookmarkIcon />}
              onClick={toggleSaved}
              color={saved ? 'primary' : 'inherit'}
              size="small"
            >
              {saved ? 'Saved' : 'Save'}
            </Button>
            <Button 
              startIcon={<ShareIcon />}
              size="small"
              onClick={() => {
                navigator.clipboard.writeText(window.location.href);
                alert('Link copied to clipboard!');
              }}
            >
              Share
            </Button>
          </Box>
        </Box>

        <Typography variant="h4" component="h1" gutterBottom>
          {article.title}
        </Typography>
        
        {/* Sentiment Indicator */}
        {article.sentiment && (
          <Chip 
            label={`${article.sentiment} sentiment (${(article.sentiment_score || 0).toFixed(2)})`} 
            color={getSentimentColor(article.sentiment) as any}
            sx={{ mb: 3 }}
          />
        )}
        
        {/* AI Summary */}
        <Paper variant="outlined" sx={{ p: 3, mb: 4, bgcolor: 'background.paper' }}>
          <Typography variant="h6" gutterBottom>
            AI Summary
          </Typography>
          <Typography variant="body1" paragraph>
            {article.summarized_headline}
          </Typography>
          <Typography variant="subtitle2" gutterBottom>
            Key Points:
          </Typography>
          <Box component="ul" sx={{ pl: 2 }}>
            {article.summary_bullets?.map((bullet, index) => (
              <Typography component="li" key={index} paragraph>
                {bullet}
              </Typography>
            ))}
          </Box>
        </Paper>
        
        {/* Full Article Content */}
        <Typography variant="h6" gutterBottom>
          Full Article
        </Typography>
        <Typography variant="body1" paragraph>
          {article.content}
        </Typography>
        
        <Box sx={{ mt: 4 }}>
          <MuiLink href={article.url} target="_blank" rel="noopener noreferrer">
            Read original article at {article.source}
          </MuiLink>
        </Box>
        
        <Divider sx={{ my: 4 }} />
        
        {/* Related Information */}
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle1" gutterBottom>
              Key Entities
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {article.key_entities?.map(entity => (
                <Chip 
                  key={entity} 
                  label={entity} 
                  variant="outlined" 
                  size="small"
                />
              ))}
            </Box>
          </Grid>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle1" gutterBottom>
              Topics
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {article.topics?.map(topic => (
                <Chip 
                  key={topic} 
                  label={topic} 
                  color="primary" 
                  variant="outlined"
                  size="small"
                />
              ))}
            </Box>
          </Grid>
        </Grid>
        
        {article.market_impact_score !== undefined && (
          <Box sx={{ mt: 4 }}>
            <Typography variant="subtitle1" gutterBottom>
              Market Impact Score
            </Typography>
            <Box 
              sx={{ 
                height: 10, 
                width: '100%', 
                bgcolor: 'grey.200',
                borderRadius: 5,
                overflow: 'hidden'
              }}
            >
              <Box 
                sx={{ 
                  height: '100%', 
                  width: `${article.market_impact_score * 100}%`,
                  bgcolor: article.market_impact_score > 0.7 ? 'error.main' : 
                           article.market_impact_score > 0.4 ? 'warning.main' : 
                           'success.main',
                }}
              />
            </Box>
            <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
              {article.market_impact_score < 0.3 ? 'Low impact' : 
               article.market_impact_score < 0.7 ? 'Moderate impact' : 
               'High impact'} - {(article.market_impact_score * 100).toFixed(0)}%
            </Typography>
          </Box>
        )}
      </Paper>
    </Layout>
  );
}
