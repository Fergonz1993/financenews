import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  FormControl,
  FormControlLabel,
  FormGroup,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Switch,
  TextField,
  Typography,
  Chip,
  IconButton,
  Snackbar,
  Alert,
} from '@mui/material';
import { Add as AddIcon, Close as CloseIcon } from '@mui/icons-material';
import { getUserSettings, updateUserSettings } from '../api/newsApi';

const Settings = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [notification, setNotification] = useState({
    open: false,
    message: '',
    severity: 'success',
  });

  // Load settings on component mount
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        setLoading(true);
        const data = await getUserSettings();
        setSettings(data);
      } catch (err) {
        console.error('Error loading settings:', err);
        setNotification({
          open: true,
          message: 'Failed to load settings',
          severity: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, []);

  // Handle toggle changes
  const handleToggle = (field) => (event) => {
    setSettings({
      ...settings,
      [field]: event.target.checked,
    });
  };

  // Handle select changes
  const handleSelectChange = (field) => (event) => {
    setSettings({
      ...settings,
      [field]: event.target.value,
    });
  };

  // Handle nested select changes
  const handleNestedSelectChange = (parent, field) => (event) => {
    setSettings({
      ...settings,
      [parent]: {
        ...settings[parent],
        [field]: event.target.value,
      },
    });
  };

  // Handle nested toggle changes
  const handleNestedToggle = (parent, field) => (event) => {
    setSettings({
      ...settings,
      [parent]: {
        ...settings[parent],
        [field]: event.target.checked,
      },
    });
  };

  // Handle keyword addition
  const handleAddKeyword = () => {
    if (keyword.trim() === '') return;
    
    const updatedSettings = {
      ...settings,
      emailAlerts: {
        ...settings.emailAlerts,
        keywords: [...settings.emailAlerts.keywords, keyword.trim()],
      },
    };
    
    setSettings(updatedSettings);
    setKeyword('');
  };

  // Handle keyword removal
  const handleRemoveKeyword = (index) => {
    const updatedKeywords = [...settings.emailAlerts.keywords];
    updatedKeywords.splice(index, 1);
    
    setSettings({
      ...settings,
      emailAlerts: {
        ...settings.emailAlerts,
        keywords: updatedKeywords,
      },
    });
  };

  // Handle form submission
  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      await updateUserSettings(settings);
      setNotification({
        open: true,
        message: 'Settings updated successfully',
        severity: 'success',
      });
    } catch (err) {
      console.error('Error updating settings:', err);
      setNotification({
        open: true,
        message: 'Failed to update settings',
        severity: 'error',
      });
    }
  };

  // Handle notification close
  const handleCloseNotification = () => {
    setNotification({
      ...notification,
      open: false,
    });
  };

  // If settings are still loading, show loading state
  if (loading || !settings) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          Settings
        </Typography>
        <Typography>Loading settings...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>

      <Paper component="form" onSubmit={handleSubmit} sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={3}>
          {/* Display Preferences */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Display Preferences
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <FormGroup>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.darkMode}
                    onChange={handleToggle('darkMode')}
                  />
                }
                label="Dark Mode"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.autoRefresh}
                    onChange={handleToggle('autoRefresh')}
                  />
                }
                label="Auto-refresh Content"
              />
            </FormGroup>
            
            <Box sx={{ mt: 2, width: 200 }}>
              <FormControl fullWidth disabled={!settings.autoRefresh}>
                <InputLabel>Refresh Interval</InputLabel>
                <Select
                  value={settings.refreshInterval}
                  onChange={handleSelectChange('refreshInterval')}
                  label="Refresh Interval"
                >
                  <MenuItem value={1}>1 minute</MenuItem>
                  <MenuItem value={5}>5 minutes</MenuItem>
                  <MenuItem value={15}>15 minutes</MenuItem>
                  <MenuItem value={30}>30 minutes</MenuItem>
                  <MenuItem value={60}>1 hour</MenuItem>
                </Select>
              </FormControl>
            </Box>
          </Grid>

          {/* Visualization Settings */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
              Visualization Settings
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={4}>
                <FormControl fullWidth>
                  <InputLabel>Default Chart Type</InputLabel>
                  <Select
                    value={settings.visualization.chartType}
                    onChange={handleNestedSelectChange('visualization', 'chartType')}
                    label="Default Chart Type"
                  >
                    <MenuItem value="bar">Bar Chart</MenuItem>
                    <MenuItem value="line">Line Chart</MenuItem>
                    <MenuItem value="pie">Pie Chart</MenuItem>
                    <MenuItem value="radar">Radar Chart</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6} md={4}>
                <FormControl fullWidth>
                  <InputLabel>Color Scheme</InputLabel>
                  <Select
                    value={settings.visualization.colorScheme}
                    onChange={handleNestedSelectChange('visualization', 'colorScheme')}
                    label="Color Scheme"
                  >
                    <MenuItem value="default">Default</MenuItem>
                    <MenuItem value="pastel">Pastel</MenuItem>
                    <MenuItem value="monochrome">Monochrome</MenuItem>
                    <MenuItem value="vibrant">Vibrant</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Grid>

          {/* Email Alerts */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
              Email Alerts
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <FormGroup>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.emailAlerts.enabled}
                    onChange={handleNestedToggle('emailAlerts', 'enabled')}
                  />
                }
                label="Enable Email Alerts"
              />
            </FormGroup>
            
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12} sm={6} md={4}>
                <FormControl fullWidth disabled={!settings.emailAlerts.enabled}>
                  <InputLabel>Alert Frequency</InputLabel>
                  <Select
                    value={settings.emailAlerts.frequency}
                    onChange={handleNestedSelectChange('emailAlerts', 'frequency')}
                    label="Alert Frequency"
                  >
                    <MenuItem value="instant">Instant</MenuItem>
                    <MenuItem value="hourly">Hourly</MenuItem>
                    <MenuItem value="daily">Daily</MenuItem>
                    <MenuItem value="weekly">Weekly</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Alert Keywords
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TextField
                  label="Add keyword"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  disabled={!settings.emailAlerts.enabled}
                  size="small"
                  sx={{ mr: 1 }}
                />
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={handleAddKeyword}
                  disabled={!settings.emailAlerts.enabled || !keyword.trim()}
                >
                  Add
                </Button>
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {settings.emailAlerts.keywords.map((kw, index) => (
                  <Chip
                    key={index}
                    label={kw}
                    onDelete={() => handleRemoveKeyword(index)}
                    disabled={!settings.emailAlerts.enabled}
                  />
                ))}
                {settings.emailAlerts.keywords.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    No keywords added
                  </Typography>
                )}
              </Box>
            </Box>
          </Grid>

          {/* Save Button */}
          <Grid item xs={12} sx={{ mt: 2 }}>
            <Button variant="contained" color="primary" type="submit">
              Save Settings
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Notification */}
      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={handleCloseNotification}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleCloseNotification}
          severity={notification.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {notification.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Settings;
