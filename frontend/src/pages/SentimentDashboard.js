import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Paper,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
  Button,
} from '@mui/material';
import { Bar, Pie, Line } from 'react-chartjs-2';
import { getAnalytics } from '../api/newsApi';
import SentimentAnalyzer from '../components/SentimentAnalyzer';

const SentimentDashboard = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeframe, setTimeframe] = useState('week');
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        const data = await getAnalytics();
        setAnalytics(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching analytics:', err);
        setError('Failed to load sentiment data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [timeframe]);

  const handleTimeframeChange = (event) => {
    setTimeframe(event.target.value);
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
  };

  // Mock sentiment trend data for the chart
  const getSentimentTrendData = () => {
    const labels = {
      day: ['9AM', '10AM', '11AM', '12PM', '1PM', '2PM', '3PM', '4PM', '5PM'],
      week: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      month: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
      quarter: ['Jan', 'Feb', 'Mar'],
      year: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    };

    // Generate random data for demonstration
    const generateData = (base, variance) => {
      return labels[timeframe].map(() => base + (Math.random() * variance * 2) - variance);
    };

    return {
      labels: labels[timeframe],
      datasets: [
        {
          label: 'Positive Sentiment',
          data: generateData(0.6, 0.15),
          borderColor: 'rgba(75, 192, 192, 1)',
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
          tension: 0.4,
          fill: true,
        },
        {
          label: 'Negative Sentiment',
          data: generateData(0.3, 0.12),
          borderColor: 'rgba(255, 99, 132, 1)',
          backgroundColor: 'rgba(255, 99, 132, 0.2)',
          tension: 0.4,
          fill: true,
        },
        {
          label: 'Neutral Sentiment',
          data: generateData(0.1, 0.05),
          borderColor: 'rgba(54, 162, 235, 1)',
          backgroundColor: 'rgba(54, 162, 235, 0.2)',
          tension: 0.4,
          fill: true,
        },
      ],
    };
  };

  // Mock entity sentiment data
  const getEntitySentimentData = () => {
    const entities = ['Apple', 'Tesla', 'Federal Reserve', 'Microsoft', 'Amazon', 'Bitcoin', 'S&P 500', 'Oil'];
    
    return {
      labels: entities,
      datasets: [
        {
          label: 'Positive Mentions',
          data: entities.map(() => Math.floor(Math.random() * 30) + 5),
          backgroundColor: 'rgba(75, 192, 192, 0.6)',
          borderColor: 'rgba(75, 192, 192, 1)',
          borderWidth: 1,
        },
        {
          label: 'Negative Mentions',
          data: entities.map(() => Math.floor(Math.random() * 20) + 2),
          backgroundColor: 'rgba(255, 99, 132, 0.6)',
          borderColor: 'rgba(255, 99, 132, 1)',
          borderWidth: 1,
        },
        {
          label: 'Neutral Mentions',
          data: entities.map(() => Math.floor(Math.random() * 10) + 1),
          backgroundColor: 'rgba(54, 162, 235, 0.6)',
          borderColor: 'rgba(54, 162, 235, 1)',
          borderWidth: 1,
        },
      ],
    };
  };

  // Chart options
  const lineOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: `Sentiment Trends (${timeframe})`,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 1,
        title: {
          display: true,
          text: 'Sentiment Score',
        },
      },
    },
    interaction: {
      mode: 'index',
      intersect: false,
    },
  };

  const barOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'Entity Sentiment Analysis',
      },
    },
    scales: {
      x: {
        stacked: false,
      },
      y: {
        stacked: false,
        beginAtZero: true,
        title: {
          display: true,
          text: 'Number of Mentions',
        },
      },
    },
  };

  if (loading && !analytics) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Sentiment Analysis Dashboard
      </Typography>
      
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="body1">
          Track the sentiment of financial news over time, analyze market trends, and gain insights into how sentiment affects various market sectors and entities.
        </Typography>
      </Paper>
      
      {/* Timeframe Selector */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button 
            variant={activeTab === 'overview' ? 'contained' : 'outlined'} 
            onClick={() => handleTabChange('overview')}
          >
            Overview
          </Button>
          <Button 
            variant={activeTab === 'entities' ? 'contained' : 'outlined'} 
            onClick={() => handleTabChange('entities')}
          >
            Entities
          </Button>
          <Button 
            variant={activeTab === 'analyzer' ? 'contained' : 'outlined'} 
            onClick={() => handleTabChange('analyzer')}
          >
            Sentiment Analyzer
          </Button>
        </Box>
        
        <FormControl sx={{ minWidth: 150 }}>
          <InputLabel>Timeframe</InputLabel>
          <Select
            value={timeframe}
            onChange={handleTimeframeChange}
            label="Timeframe"
            size="small"
          >
            <MenuItem value="day">Today</MenuItem>
            <MenuItem value="week">This Week</MenuItem>
            <MenuItem value="month">This Month</MenuItem>
            <MenuItem value="quarter">This Quarter</MenuItem>
            <MenuItem value="year">This Year</MenuItem>
          </Select>
        </FormControl>
      </Box>
      
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      
      {activeTab === 'overview' && (
        <Grid container spacing={3}>
          {/* Sentiment Distribution Card */}
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Current Sentiment Distribution
                </Typography>
                <Divider sx={{ mb: 2 }} />
                {analytics && (
                  <Box sx={{ height: 250 }}>
                    <Pie 
                      data={{
                        labels: Object.keys(analytics.sentiment_distribution),
                        datasets: [
                          {
                            data: Object.values(analytics.sentiment_distribution),
                            backgroundColor: [
                              'rgba(75, 192, 192, 0.6)', // positive
                              'rgba(54, 162, 235, 0.6)', // neutral
                              'rgba(255, 99, 132, 0.6)', // negative
                            ],
                            borderColor: [
                              'rgb(75, 192, 192)',
                              'rgb(54, 162, 235)',
                              'rgb(255, 99, 132)',
                            ],
                            borderWidth: 1,
                          },
                        ],
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: {
                            position: 'bottom',
                          },
                        },
                      }}
                    />
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
          
          {/* Sentiment Stats Cards */}
          <Grid item xs={12} md={8}>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <Paper sx={{ p: 2, height: '100%', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <Typography variant="h6" color="success.main" gutterBottom>
                    Positive
                  </Typography>
                  <Typography variant="h3" color="success.main">
                    {analytics ? `${Math.round(analytics.sentiment_distribution.positive / Object.values(analytics.sentiment_distribution).reduce((a, b) => a + b) * 100)}%` : '0%'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    of all articles
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={4}>
                <Paper sx={{ p: 2, height: '100%', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <Typography variant="h6" color="info.main" gutterBottom>
                    Neutral
                  </Typography>
                  <Typography variant="h3" color="info.main">
                    {analytics ? `${Math.round(analytics.sentiment_distribution.neutral / Object.values(analytics.sentiment_distribution).reduce((a, b) => a + b) * 100)}%` : '0%'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    of all articles
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={4}>
                <Paper sx={{ p: 2, height: '100%', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <Typography variant="h6" color="error.main" gutterBottom>
                    Negative
                  </Typography>
                  <Typography variant="h3" color="error.main">
                    {analytics ? `${Math.round(analytics.sentiment_distribution.negative / Object.values(analytics.sentiment_distribution).reduce((a, b) => a + b) * 100)}%` : '0%'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    of all articles
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
            
            <Paper sx={{ p: 2, mt: 2 }}>
              <Typography variant="h6" gutterBottom>
                Top Sentiment-Impacting Topics
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Grid container spacing={2}>
                {analytics && analytics.top_topics.slice(0, 5).map((topic, index) => (
                  <Grid item xs={12} sm={6} md={4} key={index}>
                    <Paper variant="outlined" sx={{ p: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="body2">{topic.name}</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>{topic.count}</Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          </Grid>
          
          {/* Sentiment Trend Chart */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Sentiment Trends
                </Typography>
                <Divider sx={{ mb: 2 }} />
                <Box sx={{ height: 400 }}>
                  <Line 
                    data={getSentimentTrendData()} 
                    options={lineOptions}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
      
      {activeTab === 'entities' && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Entity Sentiment Analysis
                </Typography>
                <Divider sx={{ mb: 2 }} />
                <Box sx={{ height: 500 }}>
                  <Bar 
                    data={getEntitySentimentData()} 
                    options={barOptions} 
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Top Entities by Sentiment Impact
                </Typography>
                <Divider sx={{ mb: 2 }} />
                <Grid container spacing={2}>
                  {analytics && analytics.top_entities.map((entity, index) => (
                    <Grid item xs={12} sm={6} md={4} lg={3} key={index}>
                      <Paper 
                        variant="outlined" 
                        sx={{ 
                          p: 2, 
                          display: 'flex', 
                          flexDirection: 'column',
                          height: '100%',
                        }}
                      >
                        <Typography variant="h6" gutterBottom>
                          {entity.name}
                        </Typography>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            Mentions:
                          </Typography>
                          <Typography variant="body2" fontWeight="bold">
                            {entity.count}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            Positive:
                          </Typography>
                          <Typography variant="body2" color="success.main" fontWeight="bold">
                            {Math.round(Math.random() * 100)}%
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Typography variant="body2" color="text.secondary">
                            Negative:
                          </Typography>
                          <Typography variant="body2" color="error.main" fontWeight="bold">
                            {Math.round(Math.random() * 100)}%
                          </Typography>
                        </Box>
                      </Paper>
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
      
      {activeTab === 'analyzer' && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <SentimentAnalyzer />
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default SentimentDashboard;
