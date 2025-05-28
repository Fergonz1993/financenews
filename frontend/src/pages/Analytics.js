import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  Grid,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import { 
  Chart as ChartJS, 
  CategoryScale, 
  LinearScale, 
  BarElement, 
  Title, 
  Tooltip, 
  Legend,
  ArcElement,
  PointElement,
  LineElement
} from 'chart.js';
import { Bar, Pie, Line } from 'react-chartjs-2';
import { getAnalytics } from '../api/newsApi';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  PointElement,
  LineElement
);

const Analytics = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        const data = await getAnalytics();
        setAnalytics(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching analytics:', err);
        setError('Failed to fetch analytics data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, []);

  // Prepare sentiment chart data
  const getSentimentChartData = () => {
    const { sentiment_distribution } = analytics;
    
    return {
      labels: Object.keys(sentiment_distribution),
      datasets: [
        {
          label: 'Sentiment Distribution',
          data: Object.values(sentiment_distribution),
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
    };
  };

  // Prepare source chart data
  const getSourceChartData = () => {
    const { source_distribution } = analytics;
    
    return {
      labels: Object.keys(source_distribution),
      datasets: [
        {
          label: 'Articles per Source',
          data: Object.values(source_distribution),
          backgroundColor: 'rgba(153, 102, 255, 0.6)',
          borderColor: 'rgb(153, 102, 255)',
          borderWidth: 1,
        },
      ],
    };
  };

  // Prepare entities chart data
  const getEntitiesChartData = () => {
    const { top_entities } = analytics;
    
    return {
      labels: top_entities.map(item => item.name),
      datasets: [
        {
          label: 'Mentions',
          data: top_entities.map(item => item.count),
          backgroundColor: 'rgba(255, 159, 64, 0.6)',
          borderColor: 'rgb(255, 159, 64)',
          borderWidth: 1,
        },
      ],
    };
  };

  // Prepare topics chart data
  const getTopicsChartData = () => {
    const { top_topics } = analytics;
    
    return {
      labels: top_topics.map(item => item.name),
      datasets: [
        {
          label: 'Topic Distribution',
          data: top_topics.map(item => item.count),
          backgroundColor: [
            'rgba(255, 99, 132, 0.6)',
            'rgba(54, 162, 235, 0.6)',
            'rgba(255, 206, 86, 0.6)',
            'rgba(75, 192, 192, 0.6)',
            'rgba(153, 102, 255, 0.6)',
          ],
          borderColor: [
            'rgba(255, 99, 132, 1)',
            'rgba(54, 162, 235, 1)',
            'rgba(255, 206, 86, 1)',
            'rgba(75, 192, 192, 1)',
            'rgba(153, 102, 255, 1)',
          ],
          borderWidth: 1,
        },
      ],
    };
  };

  // Chart options
  const barOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
    },
  };

  const pieOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'right',
      },
    },
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Analytics Dashboard
      </Typography>
      
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : analytics ? (
        <Grid container spacing={3}>
          {/* Processing Stats */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2, display: 'flex', justifyContent: 'space-around' }}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary">
                  Articles Processed
                </Typography>
                <Typography variant="h4">
                  {analytics.processing_stats.articles_processed}
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary">
                  Avg. Processing Time
                </Typography>
                <Typography variant="h4">
                  {analytics.processing_stats.avg_processing_time.toFixed(2)}s
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary">
                  Last Update
                </Typography>
                <Typography variant="h4">
                  {new Date(analytics.processing_stats.last_update * 1000).toLocaleTimeString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
          
          {/* Sentiment Distribution */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Sentiment Distribution
                </Typography>
                <Box sx={{ height: 300 }}>
                  <Pie data={getSentimentChartData()} options={pieOptions} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          {/* Source Distribution */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Articles by Source
                </Typography>
                <Box sx={{ height: 300 }}>
                  <Bar 
                    data={getSourceChartData()} 
                    options={barOptions} 
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          {/* Top Entities */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Top Entities Mentioned
                </Typography>
                <Box sx={{ height: 300 }}>
                  <Bar 
                    data={getEntitiesChartData()} 
                    options={barOptions} 
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          
          {/* Topic Distribution */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Topic Distribution
                </Typography>
                <Box sx={{ height: 300 }}>
                  <Pie data={getTopicsChartData()} options={pieOptions} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      ) : (
        <Alert severity="warning">No analytics data available.</Alert>
      )}
    </Box>
  );
};

export default Analytics;
