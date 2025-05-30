import { useState, useEffect } from 'react';
import { 
  Container, Typography, Box, Button, Paper, TableContainer, 
  Table, TableHead, TableRow, TableCell, TableBody, Chip,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, FormControl, InputLabel, Select, MenuItem,
  FormControlLabel, Switch, CircularProgress, Grid
} from '@mui/material';
import { format, formatDistanceToNow } from 'date-fns';
import axios from 'axios';
import { NewsSource, SourceType, SourceCategory } from '../../lib/models/NewsSource';

// Admin page for managing crawlers and news sources
export default function CrawlerAdmin() {
  const [loading, setLoading] = useState(true);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [currentSource, setCurrentSource] = useState<NewsSource | null>(null);
  const [isRunningCrawl, setIsRunningCrawl] = useState(false);
  const [crawlResult, setCrawlResult] = useState<string | null>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<'running' | 'stopped'>('stopped');
  
  // Load sources and stats on initial load
  useEffect(() => {
    fetchSources();
    fetchStats();
  }, []);
  
  const fetchSources = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/crawler/sources');
      setSources(response.data);
    } catch (error) {
      console.error('Error fetching sources:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/crawler');
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching crawler stats:', error);
    }
  };
  
  const handleOpenDialog = (source: NewsSource | null = null) => {
    if (source) {
      setCurrentSource(source);
    } else {
      setCurrentSource({
        id: '',
        name: '',
        url: '',
        type: 'rss',
        category: 'finance',
        crawlFrequency: 30,
        isActive: true,
        useProxy: false,
        respectRobotsTxt: true
      });
    }
    setOpenDialog(true);
  };
  
  const handleCloseDialog = () => {
    setOpenDialog(false);
    setCurrentSource(null);
  };
  
  const handleSourceChange = (field: keyof NewsSource, value: any) => {
    if (!currentSource) return;
    
    if (field === 'selector') {
      setCurrentSource({
        ...currentSource,
        selector: {
          ...currentSource.selector,
          ...value
        }
      });
    } else {
      setCurrentSource({
        ...currentSource,
        [field]: value
      });
    }
  };
  
  const handleSaveSource = async () => {
    if (!currentSource) return;
    
    try {
      await axios.post('/api/crawler/sources', currentSource);
      handleCloseDialog();
      fetchSources();
      fetchStats();
    } catch (error) {
      console.error('Error saving source:', error);
    }
  };
  
  const handleDeleteSource = async (id: string) => {
    if (!confirm('Are you sure you want to delete this source?')) return;
    
    try {
      await axios.delete(`/api/crawler/sources?id=${id}`);
      fetchSources();
      fetchStats();
    } catch (error) {
      console.error('Error deleting source:', error);
    }
  };
  
  const handleToggleSourceStatus = async (source: NewsSource) => {
    try {
      await axios.post('/api/crawler/sources', {
        ...source,
        isActive: !source.isActive
      });
      fetchSources();
      fetchStats();
    } catch (error) {
      console.error('Error updating source status:', error);
    }
  };
  
  const handleRunCrawlers = async () => {
    try {
      setIsRunningCrawl(true);
      setCrawlResult(null);
      
      const response = await axios.post('/api/crawler', { action: 'run_now' });
      setCrawlResult(`Crawl completed. Found ${response.data.newArticles} new articles.`);
      
      // Refresh sources and stats
      fetchSources();
      fetchStats();
    } catch (error) {
      console.error('Error running crawlers:', error);
      setCrawlResult('Error running crawlers. Check console for details.');
    } finally {
      setIsRunningCrawl(false);
    }
  };
  
  const handleToggleScheduler = async () => {
    try {
      const action = schedulerStatus === 'running' ? 'stop_scheduler' : 'start_scheduler';
      await axios.post('/api/crawler', { action });
      setSchedulerStatus(schedulerStatus === 'running' ? 'stopped' : 'running');
    } catch (error) {
      console.error('Error toggling scheduler:', error);
    }
  };
  
  return (
    <Container maxWidth="lg">
      <Box my={4}>
        <Typography variant="h4" component="h1" gutterBottom>
          News Crawler Admin
        </Typography>
        
        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} md={8}>
            <Paper elevation={2} sx={{ p: 2, mb: 3 }}>
              <Typography variant="h6" gutterBottom>Crawler System Status</Typography>
              {stats ? (
                <Box>
                  <Typography>Total Sources: {stats.totalSources}</Typography>
                  <Typography>Active Sources: {stats.activeSources}</Typography>
                  <Typography>Sources Due for Crawling: {stats.sourcesDueCrawling}</Typography>
                  <Box mt={2} display="flex" gap={2}>
                    <Button 
                      variant="contained" 
                      color="primary" 
                      onClick={handleRunCrawlers}
                      disabled={isRunningCrawl}
                    >
                      {isRunningCrawl ? <CircularProgress size={24} /> : 'Run Crawlers Now'}
                    </Button>
                    <Button 
                      variant="outlined" 
                      color={schedulerStatus === 'running' ? 'error' : 'success'}
                      onClick={handleToggleScheduler}
                    >
                      {schedulerStatus === 'running' ? 'Stop Scheduler' : 'Start Scheduler'}
                    </Button>
                  </Box>
                  {crawlResult && (
                    <Typography color="text.secondary" mt={2}>
                      {crawlResult}
                    </Typography>
                  )}
                </Box>
              ) : (
                <CircularProgress />
              )}
            </Paper>
          </Grid>
          <Grid item xs={12} md={4}>
            <Paper elevation={2} sx={{ p: 2, mb: 3, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <Typography variant="h6" gutterBottom>Add a News Source</Typography>
              <Button
                variant="contained"
                color="secondary"
                onClick={() => handleOpenDialog()}
                fullWidth
              >
                Add New Source
              </Button>
            </Paper>
          </Grid>
        </Grid>
        
        <Typography variant="h5" gutterBottom mt={4}>News Sources</Typography>
        
        {loading ? (
          <CircularProgress />
        ) : (
          <TableContainer component={Paper}>
            <Table sx={{ minWidth: 650 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>URL</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell>Frequency</TableCell>
                  <TableCell>Last Crawled</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sources.map((source) => (
                  <TableRow key={source.id} hover>
                    <TableCell>{source.name}</TableCell>
                    <TableCell>
                      <a href={source.url} target="_blank" rel="noopener noreferrer">
                        {source.url.substring(0, 30)}...
                      </a>
                    </TableCell>
                    <TableCell>{source.type}</TableCell>
                    <TableCell>{source.category}</TableCell>
                    <TableCell>{source.crawlFrequency} minutes</TableCell>
                    <TableCell>
                      {source.lastCrawled ? 
                        formatDistanceToNow(new Date(source.lastCrawled), { addSuffix: true }) : 
                        'Never'
                      }
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={source.isActive ? 'Active' : 'Inactive'} 
                        color={source.isActive ? 'success' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Box display="flex" gap={1}>
                        <Button 
                          size="small" 
                          variant="outlined" 
                          onClick={() => handleOpenDialog(source)}
                        >
                          Edit
                        </Button>
                        <Button 
                          size="small" 
                          variant="outlined" 
                          color={source.isActive ? 'error' : 'success'}
                          onClick={() => handleToggleSourceStatus(source)}
                        >
                          {source.isActive ? 'Disable' : 'Enable'}
                        </Button>
                        <Button 
                          size="small" 
                          variant="outlined" 
                          color="error"
                          onClick={() => handleDeleteSource(source.id)}
                        >
                          Delete
                        </Button>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
                
                {sources.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} align="center">No sources found</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
      
      {/* Add/Edit Source Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} fullWidth maxWidth="md">
        <DialogTitle>
          {currentSource?.id ? `Edit Source: ${currentSource.name}` : 'Add New Source'}
        </DialogTitle>
        <DialogContent>
          <Box component="form" noValidate autoComplete="off" mt={2} display="flex" flexDirection="column" gap={2}>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <TextField
                  label="Name"
                  fullWidth
                  value={currentSource?.name || ''}
                  onChange={(e) => handleSourceChange('name', e.target.value)}
                />
              </Grid>
              
              <Grid item xs={12} md={6}>
                <TextField
                  label="URL"
                  fullWidth
                  value={currentSource?.url || ''}
                  onChange={(e) => handleSourceChange('url', e.target.value)}
                />
              </Grid>
              
              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Type</InputLabel>
                  <Select
                    value={currentSource?.type || 'rss'}
                    label="Type"
                    onChange={(e) => handleSourceChange('type', e.target.value)}
                  >
                    <MenuItem value="rss">RSS Feed</MenuItem>
                    <MenuItem value="scrape">Web Scraping</MenuItem>
                    <MenuItem value="api">API</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Category</InputLabel>
                  <Select
                    value={currentSource?.category || 'finance'}
                    label="Category"
                    onChange={(e) => handleSourceChange('category', e.target.value)}
                  >
                    <MenuItem value="finance">Finance</MenuItem>
                    <MenuItem value="economics">Economics</MenuItem>
                    <MenuItem value="markets">Markets</MenuItem>
                    <MenuItem value="technology">Technology</MenuItem>
                    <MenuItem value="general">General</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <TextField
                  label="Crawl Frequency (minutes)"
                  fullWidth
                  type="number"
                  InputProps={{ inputProps: { min: 5 } }}
                  value={currentSource?.crawlFrequency || 30}
                  onChange={(e) => handleSourceChange('crawlFrequency', parseInt(e.target.value))}
                />
              </Grid>
              
              <Grid item xs={12} md={6}>
                <TextField
                  label="User Agent"
                  fullWidth
                  value={currentSource?.userAgent || 'FinanceNewsBot/1.0'}
                  onChange={(e) => handleSourceChange('userAgent', e.target.value)}
                />
              </Grid>
              
              {currentSource?.type === 'rss' && (
                <Grid item xs={12}>
                  <TextField
                    label="RSS URL"
                    fullWidth
                    value={currentSource?.rssUrl || ''}
                    onChange={(e) => handleSourceChange('rssUrl', e.target.value)}
                  />
                </Grid>
              )}
              
              {currentSource?.type === 'api' && (
                <>
                  <Grid item xs={12} md={8}>
                    <TextField
                      label="API Endpoint"
                      fullWidth
                      value={currentSource?.apiEndpoint || ''}
                      onChange={(e) => handleSourceChange('apiEndpoint', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <TextField
                      label="API Key"
                      fullWidth
                      value={currentSource?.apiKey || ''}
                      onChange={(e) => handleSourceChange('apiKey', e.target.value)}
                    />
                  </Grid>
                </>
              )}
              
              {currentSource?.type === 'scrape' && (
                <>
                  <Grid item xs={12}>
                    <Typography variant="subtitle1">Selectors for HTML parsing</Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Title Selector"
                      fullWidth
                      value={currentSource?.selector?.title || 'h1'}
                      onChange={(e) => handleSourceChange('selector', { title: e.target.value })}
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Content Selector"
                      fullWidth
                      value={currentSource?.selector?.content || 'article, .article-body'}
                      onChange={(e) => handleSourceChange('selector', { content: e.target.value })}
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Date Selector"
                      fullWidth
                      value={currentSource?.selector?.date || 'time, .date'}
                      onChange={(e) => handleSourceChange('selector', { date: e.target.value })}
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      label="Author Selector"
                      fullWidth
                      value={currentSource?.selector?.author || '.author, .byline'}
                      onChange={(e) => handleSourceChange('selector', { author: e.target.value })}
                    />
                  </Grid>
                </>
              )}
              
              <Grid item xs={12} md={4}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={currentSource?.isActive || false}
                      onChange={(e) => handleSourceChange('isActive', e.target.checked)}
                    />
                  }
                  label="Active"
                />
              </Grid>
              
              <Grid item xs={12} md={4}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={currentSource?.useProxy || false}
                      onChange={(e) => handleSourceChange('useProxy', e.target.checked)}
                    />
                  }
                  label="Use Proxy"
                />
              </Grid>
              
              <Grid item xs={12} md={4}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={currentSource?.respectRobotsTxt || true}
                      onChange={(e) => handleSourceChange('respectRobotsTxt', e.target.checked)}
                    />
                  }
                  label="Respect robots.txt"
                />
              </Grid>
              
              {currentSource?.type === 'scrape' && (
                <Grid item xs={12} md={6}>
                  <TextField
                    label="Wait Time (ms)"
                    fullWidth
                    type="number"
                    InputProps={{ inputProps: { min: 0, max: 10000 } }}
                    value={currentSource?.waitTime || 2000}
                    onChange={(e) => handleSourceChange('waitTime', parseInt(e.target.value))}
                  />
                </Grid>
              )}
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSaveSource} variant="contained" color="primary">
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
