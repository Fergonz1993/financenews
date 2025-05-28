import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Divider,
  Chip,
  CircularProgress,
  Tooltip,
  IconButton,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Refresh as RefreshIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

// Mock market data for demonstration
const getMockMarketData = () => {
  // In a real app, this would come from an API
  return {
    indices: [
      {
        name: 'S&P 500',
        value: 5247.12,
        change: 32.45,
        changePercent: 0.62,
      },
      {
        name: 'NASDAQ',
        value: 16389.27,
        change: -52.31,
        changePercent: -0.32,
      },
      {
        name: 'Dow Jones',
        value: 37985.42,
        change: 120.93,
        changePercent: 0.32,
      },
    ],
    stocks: [
      {
        symbol: 'AAPL',
        name: 'Apple Inc.',
        price: 198.45,
        change: 2.34,
        changePercent: 1.19,
      },
      {
        symbol: 'MSFT',
        name: 'Microsoft Corp.',
        price: 415.67,
        change: -3.21,
        changePercent: -0.77,
      },
      {
        symbol: 'AMZN',
        name: 'Amazon.com Inc.',
        price: 189.32,
        change: 1.87,
        changePercent: 1.0,
      },
      {
        symbol: 'TSLA',
        name: 'Tesla Inc.',
        price: 243.78,
        change: -5.19,
        changePercent: -2.09,
      },
    ],
    forex: [
      {
        pair: 'EUR/USD',
        rate: 1.0842,
        change: 0.0023,
        changePercent: 0.21,
      },
      {
        pair: 'USD/JPY',
        rate: 152.34,
        change: -0.78,
        changePercent: -0.51,
      },
    ],
    crypto: [
      {
        symbol: 'BTC',
        name: 'Bitcoin',
        price: 63457.12,
        change: 1243.56,
        changePercent: 2.0,
      },
      {
        symbol: 'ETH',
        name: 'Ethereum',
        price: 3421.89,
        change: -87.65,
        changePercent: -2.5,
      },
    ],
    lastUpdated: new Date().toISOString(),
  };
};

const MarketDataWidget = () => {
  const [marketData, setMarketData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedTab, setSelectedTab] = useState('indices');

  // Fetch market data on component mount and when refresh is clicked
  const fetchMarketData = async () => {
    try {
      setLoading(true);
      // In a real app, this would be an API call
      // For now, we'll use our mock data with a small delay to simulate a network request
      setTimeout(() => {
        const data = getMockMarketData();
        setMarketData(data);
        setLoading(false);
      }, 800);
    } catch (err) {
      console.error('Error fetching market data:', err);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketData();
    
    // Set up auto-refresh every 60 seconds
    const intervalId = setInterval(fetchMarketData, 60000);
    
    return () => clearInterval(intervalId);
  }, []);

  // Handle tab change
  const handleTabChange = (tab) => {
    setSelectedTab(tab);
  };

  // Format a number with thousands separators
  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  };

  // Format a price based on type
  const formatPrice = (price, type) => {
    if (type === 'crypto' && price > 1000) {
      return formatNumber(price);
    } else if (type === 'forex') {
      return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 4,
        maximumFractionDigits: 4,
      }).format(price);
    }
    return formatNumber(price);
  };

  // Render change with color and icon
  const renderChange = (change, changePercent) => {
    const isPositive = change >= 0;
    
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
        {isPositive ? (
          <TrendingUp sx={{ color: 'success.main', fontSize: 16, mr: 0.5 }} />
        ) : (
          <TrendingDown sx={{ color: 'error.main', fontSize: 16, mr: 0.5 }} />
        )}
        <Typography
          variant="body2"
          sx={{
            color: isPositive ? 'success.main' : 'error.main',
            fontWeight: 'medium',
          }}
        >
          {isPositive ? '+' : ''}{formatNumber(change)} ({isPositive ? '+' : ''}{changePercent.toFixed(2)}%)
        </Typography>
      </Box>
    );
  };

  if (loading && !marketData) {
    return (
      <Card elevation={2}>
        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
            <CircularProgress size={30} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card elevation={2}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="h6" component="h2">
            Market Data
          </Typography>
          
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
              {marketData && new Date(marketData.lastUpdated).toLocaleTimeString()}
            </Typography>
            
            <Tooltip title="Refresh data">
              <IconButton 
                size="small" 
                onClick={fetchMarketData}
                disabled={loading}
              >
                {loading ? <CircularProgress size={20} /> : <RefreshIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
        
        <Divider sx={{ mb: 1.5 }} />
        
        <Box sx={{ display: 'flex', mb: 2, pb: 0.5, overflowX: 'auto' }}>
          {['indices', 'stocks', 'forex', 'crypto'].map((tab) => (
            <Chip
              key={tab}
              label={tab.charAt(0).toUpperCase() + tab.slice(1)}
              onClick={() => handleTabChange(tab)}
              color={selectedTab === tab ? 'primary' : 'default'}
              variant={selectedTab === tab ? 'filled' : 'outlined'}
              size="small"
              sx={{ mr: 1, textTransform: 'capitalize' }}
            />
          ))}
        </Box>
        
        {marketData && (
          <Box>
            <Grid container spacing={1}>
              {marketData[selectedTab].map((item, index) => (
                <Grid item xs={12} key={index}>
                  <Box 
                    sx={{ 
                      display: 'flex', 
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      py: 0.75,
                      borderBottom: index < marketData[selectedTab].length - 1 ? '1px solid' : 'none',
                      borderBottomColor: 'divider',
                    }}
                  >
                    <Box>
                      <Typography variant="body2" fontWeight="medium">
                        {item.symbol || item.name || item.pair}
                      </Typography>
                      {item.symbol && item.name && (
                        <Typography variant="caption" color="text.secondary">
                          {item.name}
                        </Typography>
                      )}
                    </Box>
                    
                    <Box sx={{ textAlign: 'right' }}>
                      <Typography variant="body2">
                        {formatPrice(item.price || item.value || item.rate, selectedTab)}
                      </Typography>
                      {renderChange(item.change, item.changePercent)}
                    </Box>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default MarketDataWidget;
