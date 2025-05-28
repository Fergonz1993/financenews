import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Box,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Menu,
  Paper,
  Popover,
  Tooltip,
  Typography,
  Chip,
} from '@mui/material';
import {
  Notifications as NotificationIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { useNotification } from '../context/NotificationContext';

const NotificationCenter = () => {
  const navigate = useNavigate();
  const { notifyInfo, notifyError, notifySuccess, notifyWarning } = useNotification();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [anchorEl, setAnchorEl] = useState(null);
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  // Initialize WebSocket connection
  useEffect(() => {
    // Create WebSocket connection
    const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws/notifications';
    const ws = new WebSocket(wsUrl);

    // Connection opened
    ws.addEventListener('open', (event) => {
      setIsConnected(true);
      notifySuccess('Connected to notification service');
    });

    // Listen for messages
    ws.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        handleNewNotification(data);
      } catch (error) {
        console.error('Error parsing notification message:', error);
      }
    });

    // Handle errors
    ws.addEventListener('error', (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
      notifyError('Connection to notification service failed');
    });

    // Handle disconnection
    ws.addEventListener('close', (event) => {
      setIsConnected(false);
      notifyInfo('Disconnected from notification service');
    });

    // Set the socket in state
    setSocket(ws);

    // Clean up the WebSocket connection when the component unmounts
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [notifySuccess, notifyError, notifyInfo]);

  // Handle a new notification
  const handleNewNotification = useCallback((data) => {
    const now = new Date();
    let newNotification = {
      id: `notification-${Date.now()}`,
      timestamp: now,
      read: false,
    };

    if (data.type === 'connection_established') {
      // Connection confirmation, don't add to notifications list
      return;
    } else if (data.type === 'market_alert') {
      const { alert } = data;
      newNotification = {
        ...newNotification,
        type: 'market_alert',
        title: alert.title,
        message: alert.details,
        source: alert.source,
        severity: alert.severity,
      };

      // Show in-app notification
      switch (alert.severity) {
        case 'success':
          notifySuccess(alert.title);
          break;
        case 'error':
          notifyError(alert.title);
          break;
        case 'warning':
          notifyWarning(alert.title);
          break;
        default:
          notifyInfo(alert.title);
      }
    } else if (data.type === 'news_update') {
      const { news } = data;
      newNotification = {
        ...newNotification,
        type: 'news_update',
        title: news.title,
        message: news.summary,
        source: news.source,
        url: news.url,
        severity: 'info',
      };

      // Show in-app notification for news updates
      notifyInfo(`New: ${news.title}`);
    }

    // Add to notifications list
    setNotifications(prev => [newNotification, ...prev].slice(0, 50)); // Keep only the 50 most recent
    setUnreadCount(prev => prev + 1);
  }, [notifySuccess, notifyError, notifyWarning, notifyInfo]);

  // Handle notification click
  const handleNotificationClick = (notification) => {
    // Mark as read
    setNotifications(prev =>
      prev.map(n => (n.id === notification.id ? { ...n, read: true } : n))
    );
    setUnreadCount(prev => Math.max(0, prev - 1));

    // Navigate if URL is provided
    if (notification.url) {
      navigate(notification.url);
    }

    // Close menu
    handleClose();
  };

  // Clear all notifications
  const handleClearAll = () => {
    setNotifications([]);
    setUnreadCount(0);
    handleClose();
  };

  // Mark all as read
  const handleMarkAllRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    setUnreadCount(0);
  };

  // Menu handlers
  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  // Render icon based on severity
  const renderSeverityIcon = (severity) => {
    switch (severity) {
      case 'success':
        return <SuccessIcon fontSize="small" color="success" />;
      case 'error':
        return <ErrorIcon fontSize="small" color="error" />;
      case 'warning':
        return <WarningIcon fontSize="small" color="warning" />;
      default:
        return <InfoIcon fontSize="small" color="info" />;
    }
  };

  // Format relative time (e.g., "2 minutes ago")
  const formatRelativeTime = (timestamp) => {
    const now = new Date();
    const diff = Math.floor((now - new Date(timestamp)) / 1000); // diff in seconds

    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hrs ago`;
    return `${Math.floor(diff / 86400)} days ago`;
  };

  return (
    <>
      <Tooltip title="Notifications">
        <IconButton color="inherit" onClick={handleClick}>
          <Badge badgeContent={unreadCount} color="error">
            <NotificationIcon />
          </Badge>
        </IconButton>
      </Tooltip>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
        PaperProps={{
          sx: {
            width: 360,
            maxHeight: 500,
            overflow: 'auto',
          },
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Notifications</Typography>
          <Box>
            {notifications.length > 0 && (
              <>
                <Tooltip title="Mark all as read">
                  <IconButton size="small" onClick={handleMarkAllRead}>
                    <CheckCircle fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Clear all">
                  <IconButton size="small" onClick={handleClearAll}>
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </>
            )}
          </Box>
        </Box>

        <Divider />

        {notifications.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              No notifications
            </Typography>
          </Box>
        ) : (
          <List>
            {notifications.map((notification) => (
              <React.Fragment key={notification.id}>
                <ListItem
                  button
                  onClick={() => handleNotificationClick(notification)}
                  sx={{
                    bgcolor: notification.read ? 'transparent' : 'action.hover',
                    '&:hover': {
                      bgcolor: 'action.selected',
                    },
                  }}
                >
                  <Box sx={{ mr: 1 }}>
                    {renderSeverityIcon(notification.severity)}
                  </Box>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" fontWeight={notification.read ? 'normal' : 'bold'}>
                          {notification.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {formatRelativeTime(notification.timestamp)}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <>
                        <Typography variant="body2" color="text.secondary" noWrap>
                          {notification.message}
                        </Typography>
                        <Chip
                          label={notification.source}
                          size="small"
                          sx={{ mt: 0.5, height: 20 }}
                        />
                      </>
                    }
                  />
                </ListItem>
                <Divider />
              </React.Fragment>
            ))}
          </List>
        )}
      </Menu>
    </>
  );
};

export default NotificationCenter;
