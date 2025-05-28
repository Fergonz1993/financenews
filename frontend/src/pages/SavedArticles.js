import React, { useState, useEffect } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  IconButton,
  Paper,
  Typography,
  Alert,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  Delete as DeleteIcon,
  MoreVert as MoreVertIcon,
  TrendingUp,
  TrendingDown,
  TrendingFlat,
  Sort as SortIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { getSavedArticles, unsaveArticle } from '../api/newsApi';
import { useNotification } from '../context/NotificationContext';

// Mock user ID (in a real app, this would come from authentication)
const MOCK_USER_ID = 'user123';

const SavedArticles = () => {
  const navigate = useNavigate();
  const { notifySuccess, notifyError } = useNotification();
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [menuAnchorEl, setMenuAnchorEl] = useState(null);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [sortMenuAnchorEl, setSortMenuAnchorEl] = useState(null);
  const [sortOption, setSortOption] = useState('date');

  // Load saved articles on component mount
  useEffect(() => {
    const fetchSavedArticles = async () => {
      try {
        setLoading(true);
        const data = await getSavedArticles(MOCK_USER_ID);
        setArticles(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching saved articles:', err);
        setError('Failed to load saved articles. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchSavedArticles();
  }, []);

  // Handle article menu open
  const handleMenuOpen = (event, article) => {
    event.stopPropagation();
    setMenuAnchorEl(event.currentTarget);
    setSelectedArticle(article);
  };

  // Handle article menu close
  const handleMenuClose = () => {
    setMenuAnchorEl(null);
  };

  // Handle sort menu open
  const handleSortMenuOpen = (event) => {
    setSortMenuAnchorEl(event.currentTarget);
  };

  // Handle sort menu close
  const handleSortMenuClose = () => {
    setSortMenuAnchorEl(null);
  };

  // Handle sort option selection
  const handleSortChange = (option) => {
    setSortOption(option);
    setSortMenuAnchorEl(null);
    
    // Sort the articles based on the selected option
    const sortedArticles = [...articles];
    switch (option) {
      case 'date':
        sortedArticles.sort((a, b) => new Date(b.saved_at) - new Date(a.saved_at));
        break;
      case 'title':
        sortedArticles.sort((a, b) => a.title.localeCompare(b.title));
        break;
      case 'source':
        sortedArticles.sort((a, b) => a.source.localeCompare(b.source));
        break;
      case 'sentiment':
        // Sort by sentiment score (high to low)
        sortedArticles.sort((a, b) => (b.sentiment_score || 0) - (a.sentiment_score || 0));
        break;
      default:
        // Default to date
        sortedArticles.sort((a, b) => new Date(b.saved_at) - new Date(a.saved_at));
    }
    
    setArticles(sortedArticles);
  };

  // Unsave an article
  const handleUnsaveArticle = async () => {
    if (!selectedArticle) return;
    
    try {
      await unsaveArticle(MOCK_USER_ID, selectedArticle.id);
      
      // Remove the article from the list
      setArticles(articles.filter(article => article.id !== selectedArticle.id));
      
      // Close the menu
      handleMenuClose();
      
      // Show success notification
      notifySuccess('Article removed from saved articles');
    } catch (err) {
      console.error('Error unsaving article:', err);
      notifyError('Failed to remove article. Please try again.');
    }
  };

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

  // Format date
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Saved Articles
      </Typography>
      
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body1">
            Your bookmarked financial news articles for later reference.
          </Typography>
          
          <Box>
            <Button
              startIcon={<SortIcon />}
              onClick={handleSortMenuOpen}
              size="small"
              sx={{ mr: 1 }}
            >
              Sort
            </Button>
            
            <Menu
              anchorEl={sortMenuAnchorEl}
              open={Boolean(sortMenuAnchorEl)}
              onClose={handleSortMenuClose}
            >
              <MenuItem 
                selected={sortOption === 'date'} 
                onClick={() => handleSortChange('date')}
              >
                <ListItemText>Date Saved</ListItemText>
              </MenuItem>
              <MenuItem 
                selected={sortOption === 'title'} 
                onClick={() => handleSortChange('title')}
              >
                <ListItemText>Title</ListItemText>
              </MenuItem>
              <MenuItem 
                selected={sortOption === 'source'} 
                onClick={() => handleSortChange('source')}
              >
                <ListItemText>Source</ListItemText>
              </MenuItem>
              <MenuItem 
                selected={sortOption === 'sentiment'} 
                onClick={() => handleSortChange('sentiment')}
              >
                <ListItemText>Sentiment</ListItemText>
              </MenuItem>
            </Menu>
          </Box>
        </Box>
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
          {articles.length === 0 ? (
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <BookmarkBorderIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                No Saved Articles
              </Typography>
              <Typography variant="body1" color="text.secondary" paragraph>
                You haven't saved any articles yet. Browse financial news and click the bookmark icon to save articles for later.
              </Typography>
              <Button 
                variant="contained" 
                color="primary"
                onClick={() => navigate('/')}
              >
                Browse Articles
              </Button>
            </Paper>
          ) : (
            <Grid container spacing={3}>
              {articles.map((article) => (
                <Grid item xs={12} sm={6} md={4} key={article.id}>
                  <Card className="article-card" elevation={2}>
                    <CardActionArea 
                      component={RouterLink} 
                      to={`/articles/${article.id}`}
                      sx={{ height: '100%' }}
                    >
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Chip
                            label={article.source}
                            size="small"
                            variant="outlined"
                          />
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            {renderSentimentIcon(article.sentiment)}
                            <Typography variant="caption" sx={{ ml: 0.5 }}>
                              {article.sentiment}
                            </Typography>
                            
                            <IconButton
                              size="small"
                              onClick={(e) => handleMenuOpen(e, article)}
                              sx={{ ml: 1 }}
                            >
                              <MoreVertIcon fontSize="small" />
                            </IconButton>
                          </Box>
                        </Box>
                        
                        <Typography variant="h6" component="h2" gutterBottom>
                          {article.title}
                        </Typography>
                        
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                          {article.summarized_headline || article.title}
                        </Typography>
                        
                        <Divider sx={{ mb: 1 }} />
                        
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="caption" color="text.secondary">
                            {formatDate(article.published_at)}
                          </Typography>
                          
                          <Typography variant="caption" color="text.secondary">
                            Saved: {formatDate(article.saved_at)}
                          </Typography>
                        </Box>
                        
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', mt: 1 }}>
                          {article.key_entities &&
                            article.key_entities
                              .slice(0, 3)
                              .map((entity, index) => (
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
      
      {/* Article actions menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleUnsaveArticle}>
          <ListItemIcon>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Remove from saved</ListItemText>
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default SavedArticles;
