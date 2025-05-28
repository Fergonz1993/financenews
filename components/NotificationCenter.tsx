import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
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
import { useNotification } from '../pages/_app';

type Notification = {
  id: string;
  timestamp: Date;
  read: boolean;
  type: string;
  title: string;
  message: string;
  source?: string;
  severity: 'success' | 'error' | 'warning' | 'info';
  url?: string;
};

const NotificationCenter = () => {
  const router = useRouter();
  const { notifyInfo, notifyError, notifySuccess, notifyWarning } = useNotification();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Initialize WebSocket connection
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Create WebSocket connection
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:3000/api/ws';
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
    }
  }, [notifySuccess, notifyError, notifyInfo]);

  // Handle a new notification
  const handleNewNotification = useCallback((data: any) => {
    const now = new Date();
    let newNotification: Notification = {
      id: `notification-${Date.now()}`,
      timestamp: now,
      read: false,
      type: '',
      title: '',
      message: '',
      severity: 'info',
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
        severity: alert.severity as 'success' | 'error' | 'warning' | 'info',
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
  const handleNotificationClick = (notification: Notification) => {
    // Mark as read
    setNotifications(prev =>
      prev.map(n => (n.id === notification.id ? { ...n, read: true } : n))
    );
    setUnreadCount(prev => Math.max(0, prev - 1));

    // Navigate if URL is provided
    if (notification.url) {
      router.push(notification.url);
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
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  // Render icon based on severity
  const renderSeverityIcon = (severity: string) => {
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
  const formatRelativeTime = (timestamp: Date) => {
    const now = new Date();
    const diff = Math.floor((now.getTime() - new Date(timestamp).getTime()) / 1000); // diff in seconds

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
          style: {
            maxHeight: 'calc(100% - 100px)',
            width: '350px',
            maxWidth: '100%',
          },
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Notifications</Typography>
          <Box>
            {unreadCount > 0 && (
              <Tooltip title="Mark all as read">
                <IconButton size="small" onClick={handleMarkAllRead}>
                  <CheckCircle fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            {notifications.length > 0 && (
              <Tooltip title="Clear all">
                <IconButton size="small" onClick={handleClearAll}>
                  <CloseIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>

        <Divider />

        {isConnected && (
          <Box sx={{ px: 2, py: 1 }}>
            <Chip
              label="Connected"
              size="small"
              color="success"
              variant="outlined"
            />
          </Box>
        )}

        {notifications.length > 0 ? (
          <List sx={{ py: 0 }}>
            {notifications.map((notification) => (
              <React.Fragment key={notification.id}>
                <ListItem
                  alignItems="flex-start"
                  button
                  onClick={() => handleNotificationClick(notification)}
                  sx={{
                    opacity: notification.read ? 0.7 : 1,
                    bgcolor: notification.read ? 'transparent' : 'action.hover',
                  }}
                >
                  <Box sx={{ mr: 2, mt: 0.5 }}>
                    {renderSeverityIcon(notification.severity)}
                  </Box>
                  <ListItemText
                    primary={
                      <Typography variant="subtitle2" component="span">
                        {notification.title}
                      </Typography>
                    }
                    secondary={
                      <>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          component="span"
                          sx={{ display: 'block' }}
                        >
                          {notification.message}
                        </Typography>
                        <Box
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            mt: 1,
                            fontSize: '0.75rem',
                            color: 'text.secondary',
                          }}
                        >
                          {notification.source && (
                            <Typography variant="caption">
                              {notification.source}
                            </Typography>
                          )}
                          <Typography variant="caption">
                            {formatRelativeTime(notification.timestamp)}
                          </Typography>
                        </Box>
                      </>
                    }
                  />
                </ListItem>
                <Divider component="li" />
              </React.Fragment>
            ))}
          </List>
        ) : (
          <Box sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              No notifications
            </Typography>
          </Box>
        )}
      </Menu>
    </>
  );
};

export default NotificationCenter;
