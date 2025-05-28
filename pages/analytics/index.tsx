import React, { useState, useEffect } from 'react';
import { 
  Typography, 
  Grid, 
  Paper, 
  Box, 
  CircularProgress,
  Card,
  CardContent,
  CardHeader
} from '@mui/material';
import Layout from '../../components/Layout';

type AnalyticsData = {
  sentiment_distribution: { [key: string]: number };
  source_distribution: { [key: string]: number };
  top_entities: { name: string; count: number }[];
  top_topics: { name: string; count: number }[];
  processing_stats: {
    avg_processing_time: number;
    articles_processed: number;
    last_update: number;
  };
};

export default function AnalyticsPage() {
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const response = await fetch('/api/analytics');
        if (!response.ok) throw new Error('Failed to fetch analytics data');
        const data = await response.json();
        setAnalyticsData(data);
      } catch (error) {
        console.error('Error fetching analytics data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, []);

  if (loading) {
    return (
      <Layout title="Analytics Dashboard" description="Financial news analytics and insights">
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <CircularProgress />
        </Box>
      </Layout>
    );
  }

  if (!analyticsData) {
    return (
      <Layout title="Analytics Dashboard" description="Financial news analytics and insights">
        <Typography variant="h5" color="error" align="center">
          Failed to load analytics data. Please try again later.
        </Typography>
      </Layout>
    );
  }

  // Helper function to create simple bar charts
  const renderBarChart = (data: { [key: string]: number } | { name: string; count: number }[], maxBars = 5) => {
    let chartData: { label: string; value: number }[] = [];

    if (Array.isArray(data)) {
      chartData = data.slice(0, maxBars).map(item => ({
        label: item.name,
        value: item.count
      }));
    } else {
      chartData = Object.entries(data)
        .map(([label, value]) => ({ label, value }))
        .sort((a, b) => b.value - a.value)
        .slice(0, maxBars);
    }

    const maxValue = Math.max(...chartData.map(item => item.value));

    return (
      <Box sx={{ mt: 2 }}>
        {chartData.map((item, index) => (
          <Box key={index} sx={{ mb: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2">{item.label}</Typography>
              <Typography variant="body2" fontWeight="bold">{item.value}</Typography>
            </Box>
            <Box sx={{ width: '100%', bgcolor: 'grey.100', borderRadius: 1, height: 10 }}>
              <Box
                sx={{
                  width: `${(item.value / maxValue) * 100}%`,
                  bgcolor: 'primary.main',
                  height: '100%',
                  borderRadius: 1,
                }}
              />
            </Box>
          </Box>
        ))}
      </Box>
    );
  };

  // Prepare sentiment colors
  const sentimentColors = {
    positive: '#4caf50',
    neutral: '#ff9800',
    negative: '#f44336'
  };

  // Create sentiment chart data
  const sentimentData = Object.entries(analyticsData.sentiment_distribution).map(([key, value]) => ({
    label: key,
    value,
    color: sentimentColors[key as keyof typeof sentimentColors] || '#2196f3'
  }));

  // Calculate sentiment totals for percentage
  const totalSentiment = sentimentData.reduce((sum, item) => sum + item.value, 0);

  return (
    <Layout title="Analytics Dashboard" description="Financial news analytics and insights">
      <Typography variant="h4" component="h1" gutterBottom>
        Analytics Dashboard
      </Typography>

      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Last updated: {new Date(analyticsData.processing_stats.last_update).toLocaleString()}
      </Typography>

      <Grid container spacing={3} sx={{ mt: 1 }}>
        {/* Summary Cards */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Articles Processed</Typography>
              <Typography variant="h3">{analyticsData.processing_stats.articles_processed}</Typography>
              <Typography variant="body2" color="text.secondary">
                Avg. processing time: {analyticsData.processing_stats.avg_processing_time.toFixed(2)}s
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Sentiment Distribution */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Sentiment Distribution</Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
              {sentimentData.map((item, index) => (
                <Box key={index} sx={{ textAlign: 'center', width: '33%' }}>
                  <Box
                    sx={{
                      width: 80,
                      height: 80,
                      borderRadius: '50%',
                      bgcolor: item.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      mx: 'auto',
                      color: 'white',
                      mb: 1
                    }}
                  >
                    <Typography variant="h5">{item.value}</Typography>
                  </Box>
                  <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
                    {item.label}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {((item.value / totalSentiment) * 100).toFixed(1)}%
                  </Typography>
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>

        {/* Source Distribution */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Top News Sources</Typography>
            {renderBarChart(analyticsData.source_distribution)}
          </Paper>
        </Grid>

        {/* Top Entities */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Top Entities Mentioned</Typography>
            {renderBarChart(analyticsData.top_entities)}
          </Paper>
        </Grid>

        {/* Top Topics */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>Top Topics</Typography>
            <Grid container spacing={2}>
              {analyticsData.top_topics.map((topic, index) => (
                <Grid item xs={6} sm={4} md={2.4} key={index}>
                  <Box
                    sx={{
                      bgcolor: 'primary.light',
                      color: 'white',
                      p: 2,
                      borderRadius: 2,
                      textAlign: 'center',
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center'
                    }}
                  >
                    <Typography variant="h6">{topic.count}</Typography>
                    <Typography variant="body2">{topic.name}</Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Layout>
  );
}
