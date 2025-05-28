import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  TextField,
  IconButton,
  InputAdornment,
  Paper,
  List,
  ListItem,
  ListItemText,
  Typography,
  Divider,
  CircularProgress,
} from '@mui/material';
import {
  Search as SearchIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { getArticles } from '../api/newsApi';

const SearchBar = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);

  // Handle search input change
  const handleSearchChange = (event) => {
    const value = event.target.value;
    setSearchQuery(value);
    
    if (value.length >= 2) {
      performSearch(value);
    } else {
      setSearchResults([]);
      setShowResults(false);
    }
  };

  // Clear search
  const handleClearSearch = () => {
    setSearchQuery('');
    setSearchResults([]);
    setShowResults(false);
  };

  // Perform search
  const performSearch = async (query) => {
    try {
      setLoading(true);
      
      // Call API with search parameter
      const results = await getArticles({ 
        search: query,
        limit: 5,
        sort_by: 'relevance',
        sort_order: 'desc'
      });
      
      setSearchResults(results);
      setShowResults(true);
    } catch (err) {
      console.error('Error searching articles:', err);
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  };

  // Handle result click
  const handleResultClick = (id) => {
    navigate(`/articles/${id}`);
    handleClearSearch();
  };

  // Handle search submission
  const handleSearchSubmit = (event) => {
    event.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/?search=${encodeURIComponent(searchQuery.trim())}`);
      setShowResults(false);
    }
  };

  return (
    <Box sx={{ position: 'relative', width: '100%', maxWidth: 600, mx: 'auto' }}>
      <Paper 
        component="form" 
        onSubmit={handleSearchSubmit}
        elevation={2}
        sx={{ 
          p: '2px 4px',
          display: 'flex',
          alignItems: 'center',
          borderRadius: 2,
        }}
      >
        <IconButton type="submit" sx={{ p: '10px' }} aria-label="search">
          <SearchIcon />
        </IconButton>
        <TextField
          fullWidth
          placeholder="Search for financial news..."
          value={searchQuery}
          onChange={handleSearchChange}
          variant="standard"
          InputProps={{
            disableUnderline: true,
            endAdornment: searchQuery ? (
              <InputAdornment position="end">
                {loading ? (
                  <CircularProgress size={20} />
                ) : (
                  <IconButton
                    aria-label="clear search"
                    onClick={handleClearSearch}
                    edge="end"
                  >
                    <ClearIcon />
                  </IconButton>
                )}
              </InputAdornment>
            ) : null,
          }}
        />
      </Paper>

      {/* Search Results Dropdown */}
      {showResults && searchResults.length > 0 && (
        <Paper
          sx={{
            position: 'absolute',
            width: '100%',
            mt: 0.5,
            borderRadius: 1,
            zIndex: 1000,
            maxHeight: 400,
            overflow: 'auto',
          }}
          elevation={3}
        >
          <List>
            {searchResults.map((article, index) => (
              <React.Fragment key={article.id}>
                <ListItem 
                  button 
                  onClick={() => handleResultClick(article.id)}
                >
                  <ListItemText
                    primary={article.title}
                    secondary={
                      <Box component="span" sx={{ display: 'flex', flexDirection: 'column', mt: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                          {article.source} • {new Date(article.published_at).toLocaleDateString()}
                        </Typography>
                        {article.key_entities.length > 0 && (
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {article.key_entities.join(', ')}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                </ListItem>
                {index < searchResults.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </Paper>
      )}
    </Box>
  );
};

export default SearchBar;
