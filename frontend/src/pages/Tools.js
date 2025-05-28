import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Divider,
  Card,
  CardContent,
  CardActionArea,
  Button,
} from '@mui/material';
import { TrendingUp, Analytics, BarChart } from '@mui/icons-material';
import SentimentAnalyzer from '../components/SentimentAnalyzer';

const Tools = () => {
  const navigate = useNavigate();
  
  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Financial Analysis Tools
      </Typography>
      
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="body1">
          Use these tools to analyze financial data and news. Explore sentiment analysis, market insights, and more.
        </Typography>
      </Paper>
      
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Tool Cards */}
        <Grid item xs={12} md={6} lg={4}>
          <Card elevation={3}>
            <CardActionArea onClick={() => navigate('/sentiment')}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <TrendingUp fontSize="large" color="primary" sx={{ mr: 1 }} />
                  <Typography variant="h6">Sentiment Dashboard</Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Advanced sentiment analysis dashboard with historical trends, entity analysis, and market impact visualization.
                </Typography>
                <Button variant="outlined" size="small">
                  Open Dashboard
                </Button>
              </CardContent>
            </CardActionArea>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={6} lg={4}>
          <Card elevation={3}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Analytics fontSize="large" color="secondary" sx={{ mr: 1 }} />
                <Typography variant="h6">Text Sentiment Analyzer</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" paragraph>
                Analyze the sentiment of any financial text to understand its potential market impact.
              </Typography>
              <Button variant="outlined" size="small" onClick={() => document.getElementById('sentimentAnalyzer').scrollIntoView({ behavior: 'smooth' })}>
                Use Tool
              </Button>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={6} lg={4}>
          <Card elevation={3}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <BarChart fontSize="large" color="info" sx={{ mr: 1 }} />
                <Typography variant="h6">Market Analytics</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" paragraph>
                Coming soon: Advanced market analytics, correlation tools, and predictive models.
              </Typography>
              <Button variant="outlined" size="small" disabled>
                Coming Soon
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
      
      <Divider sx={{ my: 4 }} />
      
      <Box id="sentimentAnalyzer">
        <Typography variant="h5" gutterBottom>
          Text Sentiment Analyzer
        </Typography>
        <SentimentAnalyzer />
      </Box>
    </Box>
  );
};

export default Tools;
