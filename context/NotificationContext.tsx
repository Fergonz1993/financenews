import { createContext, useContext, useState, ReactNode } from 'react';
import { Alert, Snackbar, AlertColor } from '@mui/material';

type Notification = {
  id: number;
  message: string;
  type: AlertColor;
  open: boolean;
};

type NotificationContextType = {
  notifyInfo: (message: string) => void;
  notifySuccess: (message: string) => void;
  notifyError: (message: string) => void;
  notifyWarning: (message: string) => void;
};

const NotificationContext = createContext<NotificationContextType>({
  notifyInfo: () => {},
  notifySuccess: () => {},
  notifyError: () => {},
  notifyWarning: () => {},
});

export const useNotification = () => useContext(NotificationContext);

type NotificationProviderProps = {
  children: ReactNode;
};

export const NotificationProvider = ({ children }: NotificationProviderProps) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  let nextId = 0;

  const addNotification = (message: string, type: AlertColor) => {
    const id = nextId++;
    setNotifications(prev => [...prev, { id, message, type, open: true }]);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      closeNotification(id);
    }, 5000);
  };

  const closeNotification = (id: number) => {
    setNotifications(prev => 
      prev.map(notification => 
        notification.id === id 
          ? { ...notification, open: false } 
          : notification
      )
    );
    
    // Remove from state after animation completes
    setTimeout(() => {
      setNotifications(prev => prev.filter(notification => notification.id !== id));
    }, 300);
  };

  const notifyInfo = (message: string) => addNotification(message, 'info');
  const notifySuccess = (message: string) => addNotification(message, 'success');
  const notifyError = (message: string) => addNotification(message, 'error');
  const notifyWarning = (message: string) => addNotification(message, 'warning');

  return (
    <NotificationContext.Provider value={{ notifyInfo, notifySuccess, notifyError, notifyWarning }}>
      {children}
      
      {/* Render notifications */}
      {notifications.map(notification => (
        <Snackbar 
          key={notification.id}
          open={notification.open}
          autoHideDuration={6000}
          onClose={() => closeNotification(notification.id)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          sx={{ mb: notifications.indexOf(notification) * 8 }} // Stack notifications
        >
          <Alert 
            onClose={() => closeNotification(notification.id)} 
            severity={notification.type}
            variant="filled"
            sx={{ width: '100%' }}
          >
            {notification.message}
          </Alert>
        </Snackbar>
      ))}
    </NotificationContext.Provider>
  );
};
