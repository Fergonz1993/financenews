import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

// Import pages
import Home from './pages/Home';
import ArticleDetail from './pages/ArticleDetail';
import Analytics from './pages/Analytics';
import Tools from './pages/Tools';
import Settings from './pages/Settings';
import SentimentDashboard from './pages/SentimentDashboard';
import SavedArticles from './pages/SavedArticles';

// Import API functions
import { getUserSettings } from './api/newsApi';

// Import context providers
import { NotificationProvider } from './context/NotificationContext';

// Import components
import Layout from './components/Layout';

// Create theme function
const createAppTheme = (darkMode = false) => {
  return createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: darkMode ? '#90caf9' : '#1976d2',
      },
      secondary: {
        main: darkMode ? '#f48fb1' : '#dc004e',
      },
      background: {
        default: darkMode ? '#121212' : '#f5f5f5',
        paper: darkMode ? '#1e1e1e' : '#ffffff',
      },
    },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      h1: {
        fontSize: '2.5rem',
        fontWeight: 500,
      },
      h2: {
        fontSize: '2rem',
        fontWeight: 500,
      },
    },
    components: {
      MuiCard: {
        styleOverrides: {
          root: {
            transition: 'box-shadow 0.3s ease-in-out',
          },
        },
      },
    },
  });
};

function App() {
  const [darkMode, setDarkMode] = useState(false);
  
  // Load user settings on initial render
  useEffect(() => {
    const loadUserSettings = async () => {
      try {
        const settings = await getUserSettings();
        setDarkMode(settings.darkMode);
      } catch (error) {
        console.error('Failed to load user settings:', error);
      }
    };
    
    loadUserSettings();
  }, []);
  
  // Create theme based on dark mode setting
  const theme = createAppTheme(darkMode);
  
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <NotificationProvider>
        <Router>
          <Layout setDarkMode={setDarkMode}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/articles/:id" element={<ArticleDetail />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/tools" element={<Tools />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/sentiment" element={<SentimentDashboard />} />
              <Route path="/saved" element={<SavedArticles />} />
            </Routes>
          </Layout>
        </Router>
      </NotificationProvider>
    </ThemeProvider>
  );
}

export default App;
