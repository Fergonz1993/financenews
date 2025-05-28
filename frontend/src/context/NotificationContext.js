import React, { createContext, useState, useContext } from 'react';
import { Snackbar, Alert } from '@mui/material';

// Create context
const NotificationContext = createContext();

// Provider component
export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState(null);

  // Add a notification
  const addNotification = (message, severity = 'info', autoHideDuration = 6000) => {
    const id = Math.random().toString(36).substring(2, 9);
    const notification = {
      id,
      message,
      severity,
      autoHideDuration,
    };
    
    setNotifications(prev => [...prev, notification]);
    
    // If no notification is currently showing, show this one
    if (!open) {
      setCurrent(notification);
      setOpen(true);
    }
  };

  // Handle closing a notification
  const handleClose = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }

    setOpen(false);
    
    // Remove the current notification and show the next one (if any)
    setTimeout(() => {
      setNotifications(prev => {
        const updated = prev.filter(n => n.id !== current.id);
        
        if (updated.length > 0) {
          setCurrent(updated[0]);
          setOpen(true);
        } else {
          setCurrent(null);
        }
        
        return updated;
      });
    }, 300);
  };

  // Shorthand functions for different notification types
  const notifySuccess = (message, autoHideDuration) => 
    addNotification(message, 'success', autoHideDuration);
    
  const notifyError = (message, autoHideDuration) => 
    addNotification(message, 'error', autoHideDuration);
    
  const notifyInfo = (message, autoHideDuration) => 
    addNotification(message, 'info', autoHideDuration);
    
  const notifyWarning = (message, autoHideDuration) => 
    addNotification(message, 'warning', autoHideDuration);

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        addNotification,
        notifySuccess,
        notifyError,
        notifyInfo,
        notifyWarning,
      }}
    >
      {children}
      
      {/* Notification display */}
      {current && (
        <Snackbar
          open={open}
          autoHideDuration={current.autoHideDuration}
          onClose={handleClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert 
            onClose={handleClose} 
            severity={current.severity} 
            variant="filled"
            sx={{ width: '100%' }}
          >
            {current.message}
          </Alert>
        </Snackbar>
      )}
    </NotificationContext.Provider>
  );
};

// Custom hook to use the notification context
export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
};

export default NotificationContext;
