import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Grid,
  TextField,
  Typography,
  Paper,
  Alert,
  Chip,
  LinearProgress,
  Divider,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  TrendingFlat,
} from '@mui/icons-material';
import { analyzeSentiment } from '../api/newsApi';

const SentimentAnalyzer = () => {
  const [text, setText] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;

    try {
      setLoading(true);
      setError(null);
      const data = await analyzeSentiment(text);
      setResult(data);
    } catch (err) {
      console.error('Error analyzing sentiment:', err);
      setError('Failed to analyze sentiment. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Render sentiment icon based on sentiment
  const renderSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case 'positive':
        return <TrendingUp sx={{ color: 'success.main' }} />;
      case 'negative':
        return <TrendingDown sx={{ color: 'error.main' }} />;
      default:
        return <TrendingFlat sx={{ color: 'info.main' }} />;
    }
  };

  return (
    <Card elevation={3}>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          Financial Text Sentiment Analyzer
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Enter any financial news text to analyze its sentiment and potential market impact.
        </Typography>

        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
          <TextField
            fullWidth
            label="Enter financial text to analyze"
            multiline
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Example: Tesla announced better-than-expected earnings for Q3, with revenue up 25% year-over-year..."
            variant="outlined"
            sx={{ mb: 2 }}
          />
          <Button
            variant="contained"
            color="primary"
            type="submit"
            disabled={loading || !text.trim()}
          >
            {loading ? 'Analyzing...' : 'Analyze Sentiment'}
          </Button>
        </Box>

        {loading && (
          <Box sx={{ mt: 3 }}>
            <CircularProgress size={24} sx={{ mr: 2 }} />
            <Typography variant="body2" display="inline">
              Analyzing sentiment...
            </Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {error}
          </Alert>
        )}

        {result && !loading && (
          <Box sx={{ mt: 3 }}>
            <Divider sx={{ my: 2 }} />
            
            <Typography variant="h6" gutterBottom>
              Analysis Results
            </Typography>
            
            <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
              <Grid container spacing={2} alignItems="center">
                <Grid item>
                  {renderSentimentIcon(result.sentiment)}
                </Grid>
                <Grid item>
                  <Typography variant="h6" sx={{ textTransform: 'capitalize' }}>
                    {result.sentiment} Sentiment
                  </Typography>
                </Grid>
                <Grid item xs>
                  <Chip 
                    label={`${Math.round(result.sentiment_score * 100)}% Confidence`}
                    color={
                      result.sentiment === 'positive' ? 'success' : 
                      result.sentiment === 'negative' ? 'error' : 'info'
                    }
                    sx={{ ml: 2 }}
                  />
                </Grid>
              </Grid>
            </Paper>
            
            <Typography variant="subtitle1" gutterBottom>
              Sentiment Breakdown
            </Typography>
            
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="body2" color="success.main" gutterBottom>
                    Positive
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={result.positive_score * 100} 
                    color="success"
                    sx={{ height: 10, borderRadius: 5 }}
                  />
                  <Typography variant="body2" align="right" sx={{ mt: 1 }}>
                    {Math.round(result.positive_score * 100)}%
                  </Typography>
                </Paper>
              </Grid>
              
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="body2" color="info.main" gutterBottom>
                    Neutral
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={result.neutral_score * 100} 
                    color="info"
                    sx={{ height: 10, borderRadius: 5 }}
                  />
                  <Typography variant="body2" align="right" sx={{ mt: 1 }}>
                    {Math.round(result.neutral_score * 100)}%
                  </Typography>
                </Paper>
              </Grid>
              
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="body2" color="error.main" gutterBottom>
                    Negative
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={result.negative_score * 100} 
                    color="error"
                    sx={{ height: 10, borderRadius: 5 }}
                  />
                  <Typography variant="body2" align="right" sx={{ mt: 1 }}>
                    {Math.round(result.negative_score * 100)}%
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
            
            {result.sentence_scores && result.sentence_scores.length > 0 && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Sentence-Level Analysis
                </Typography>
                {result.sentence_scores.map((sentence, index) => (
                  <Paper key={index} variant="outlined" sx={{ p: 2, mb: 2 }}>
                    <Typography variant="body2" paragraph>
                      {sentence.text}
                    </Typography>
                    <Grid container spacing={1} alignItems="center">
                      <Grid item>
                        {renderSentimentIcon(
                          sentence.compound > 0.05 ? 'positive' :
                          sentence.compound < -0.05 ? 'negative' : 'neutral'
                        )}
                      </Grid>
                      <Grid item>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {sentence.compound > 0.05 ? 'Positive' :
                           sentence.compound < -0.05 ? 'Negative' : 'Neutral'}
                        </Typography>
                      </Grid>
                      <Grid item xs>
                        <LinearProgress 
                          variant="determinate" 
                          value={((sentence.compound + 1) / 2) * 100} 
                          color={
                            sentence.compound > 0.05 ? 'success' :
                            sentence.compound < -0.05 ? 'error' : 'info'
                          }
                          sx={{ height: 8, borderRadius: 5 }}
                        />
                      </Grid>
                      <Grid item>
                        <Typography variant="body2">
                          {Math.round(((sentence.compound + 1) / 2) * 100)}%
                        </Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                ))}
              </Box>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default SentimentAnalyzer;
