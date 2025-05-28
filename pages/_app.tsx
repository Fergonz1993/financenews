import { useState, useEffect } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { AppProps } from 'next/app';
import '../styles/globals.css';

// Create a theme instance
const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
  },
});

// Create a context for notifications
import { createContext, useContext } from 'react';

type NotificationType = {
  notifyInfo: (message: string) => void;
  notifySuccess: (message: string) => void;
  notifyError: (message: string) => void;
  notifyWarning: (message: string) => void;
};

const NotificationContext = createContext<NotificationType>({
  notifyInfo: () => {},
  notifySuccess: () => {},
  notifyError: () => {},
  notifyWarning: () => {},
});

export const useNotification = () => useContext(NotificationContext);

function MyApp({ Component, pageProps }: AppProps) {
  const [darkMode, setDarkMode] = useState(false);

  // Notification functions (simplified for now)
  const notifyInfo = (message: string) => {
    console.log('INFO:', message);
    // In a real app, you'd use a notification library or custom component
  };

  const notifySuccess = (message: string) => {
    console.log('SUCCESS:', message);
  };

  const notifyError = (message: string) => {
    console.log('ERROR:', message);
  };

  const notifyWarning = (message: string) => {
    console.log('WARNING:', message);
  };

  const notificationValue = {
    notifyInfo,
    notifySuccess,
    notifyError,
    notifyWarning,
  };

  // Detect user's preferred color scheme
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setDarkMode(window.matchMedia('(prefers-color-scheme: dark)').matches);
    }
  }, []);

  return (
    <ThemeProvider theme={darkMode ? darkTheme : lightTheme}>
      <CssBaseline />
      <NotificationContext.Provider value={notificationValue}>
        <Component {...pageProps} />
      </NotificationContext.Provider>
    </ThemeProvider>
  );
}

export default MyApp;
