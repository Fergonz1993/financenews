import React, { useState, useEffect } from 'react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Container,
  Divider,
  Link,
  Tooltip,
  Button,
  Avatar,
  Badge,
  useTheme,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Home as HomeIcon,
  Analytics as AnalyticsIcon,
  Article as ArticleIcon,
  Info as InfoIcon,
  Build as ToolsIcon,
  Settings as SettingsIcon,
  Search as SearchIcon,
  Brightness4 as DarkModeIcon,
  Brightness7 as LightModeIcon,
  Notifications as NotificationIcon,
  Bookmark as BookmarkIcon,
} from '@mui/icons-material';
import { getUserSettings } from '../api/newsApi';
import SearchBar from './SearchBar';
import NotificationCenter from './NotificationCenter';

// Drawer width
const drawerWidth = 240;

const Layout = ({ children, setDarkMode }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const theme = useTheme();
  const [isDarkMode, setIsDarkMode] = useState(theme.palette.mode === 'dark');

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };
  
  // Handle dark mode toggle
  const handleThemeChange = (event) => {
    const newDarkMode = event.target.checked;
    setIsDarkMode(newDarkMode);
    setDarkMode(newDarkMode);
  };

  const menuItems = [
    { text: 'Home', path: '/', icon: <HomeIcon /> },
    { text: 'Analytics', path: '/analytics', icon: <AnalyticsIcon /> },
    { text: 'Saved Articles', path: '/saved', icon: <BookmarkIcon /> },
    { text: 'Tools', path: '/tools', icon: <ToolsIcon /> },
    { text: 'Settings', path: '/settings', icon: <SettingsIcon /> },
    { text: 'Documentation', path: '/docs', icon: <InfoIcon /> },
  ];

  const drawer = (
    <div>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          FinNews
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItem
            button
            key={item.text}
            component={RouterLink}
            to={item.path}
            selected={location.pathname === item.path}
          >
            <ListItemIcon>{item.icon}</ListItemIcon>
            <ListItemText primary={item.text} />
          </ListItem>
        ))}
      </List>
    </div>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          ml: { sm: `${drawerWidth}px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Financial News Analysis Platform
          </Typography>
          
          {/* Dark mode toggle */}
          <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={isDarkMode}
                  onChange={handleThemeChange}
                  icon={<LightModeIcon />}
                  checkedIcon={<DarkModeIcon />}
                />
              }
              label={isDarkMode ? 'Dark' : 'Light'}
              labelPlacement="start"
            />
          </Box>
          
          {/* Notification Center */}
          <NotificationCenter />
          
          {/* Hide search bar on small screens, show icon instead */}
          <Box sx={{ display: { xs: 'none', md: 'block' }, width: '50%', mx: 2 }}>
            <SearchBar />
          </Box>
          <Box sx={{ display: { xs: 'block', md: 'none' } }}>
            <Tooltip title="Search">
              <IconButton color="inherit" onClick={() => navigate('/')}>
                <SearchIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
        aria-label="mailbox folders"
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          marginTop: '64px', // AppBar height
        }}
      >
        <Container maxWidth="lg">{children}</Container>
        <Box 
          component="footer" 
          sx={{ 
            mt: 5, 
            py: 3, 
            textAlign: 'center',
            borderTop: theme.palette.mode === 'dark' 
              ? '1px solid rgba(255, 255, 255, 0.12)' 
              : '1px solid #eaeaea'
          }}
        >
          <Typography variant="body2" color="text.secondary">
            © {new Date().getFullYear()} Financial News Analysis Platform
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <Link href="#" color="inherit">
              Terms
            </Link>
            {' | '}
            <Link href="#" color="inherit">
              Privacy
            </Link>
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default Layout;
