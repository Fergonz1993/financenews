import React from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Divider,
} from '@mui/material';
import SentimentAnalyzer from '../components/SentimentAnalyzer';

const Tools = () => {
  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Financial Analysis Tools
      </Typography>
      
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="body1">
          Use these tools to analyze financial data and news. Currently available tools include 
          sentiment analysis for financial text, with more tools coming soon.
        </Typography>
      </Paper>
      
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <SentimentAnalyzer />
        </Grid>
      </Grid>
    </Box>
  );
};

export default Tools;
