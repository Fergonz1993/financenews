import axios from 'axios';

// Create axios instance with base URL
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API functions for articles
export const getArticles = async (params = {}) => {
  try {
    const response = await api.get('/articles', { params });
    return response.data;
  } catch (error) {
    console.error('Error fetching articles:', error);
    throw error;
  }
};

export const getArticleById = async (id) => {
  try {
    const response = await api.get(`/articles/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching article ${id}:`, error);
    throw error;
  }
};

// API functions for analytics
export const getAnalytics = async () => {
  try {
    const response = await api.get('/analytics');
    return response.data;
  } catch (error) {
    console.error('Error fetching analytics:', error);
    throw error;
  }
};

// API functions for sources and topics
export const getSources = async () => {
  try {
    const response = await api.get('/sources');
    return response.data;
  } catch (error) {
    console.error('Error fetching sources:', error);
    throw error;
  }
};

export const getTopics = async () => {
  try {
    const response = await api.get('/topics');
    return response.data;
  } catch (error) {
    console.error('Error fetching topics:', error);
    throw error;
  }
};

// API functions for sentiment analysis
export const analyzeSentiment = async (text) => {
  try {
    const response = await api.post('/analyze/sentiment', { text });
    return response.data;
  } catch (error) {
    console.error('Error analyzing sentiment:', error);
    throw error;
  }
};

// API functions for user settings
export const getUserSettings = async () => {
  try {
    const response = await api.get('/user/settings');
    return response.data;
  } catch (error) {
    console.error('Error fetching user settings:', error);
    throw error;
  }
};

export const updateUserSettings = async (settings) => {
  try {
    const response = await api.post('/user/settings', settings);
    return response.data;
  } catch (error) {
    console.error('Error updating user settings:', error);
    throw error;
  }
};

// API functions for saved articles
export const getSavedArticles = async (userId) => {
  try {
    const response = await api.get(`/users/${userId}/saved-articles`);
    return response.data;
  } catch (error) {
    console.error('Error fetching saved articles:', error);
    throw error;
  }
};

export const saveArticle = async (userId, articleId) => {
  try {
    const response = await api.post(`/users/${userId}/saved-articles/${articleId}`);
    return response.data;
  } catch (error) {
    console.error(`Error saving article ${articleId}:`, error);
    throw error;
  }
};

export const unsaveArticle = async (userId, articleId) => {
  try {
    const response = await api.delete(`/users/${userId}/saved-articles/${articleId}`);
    return response.data;
  } catch (error) {
    console.error(`Error unsaving article ${articleId}:`, error);
    throw error;
  }
};

export const checkArticleSavedStatus = async (userId, articleId) => {
  try {
    const response = await api.get(`/users/${userId}/saved-articles/${articleId}/status`);
    return response.data.is_saved;
  } catch (error) {
    console.error(`Error checking saved status for article ${articleId}:`, error);
    return false;
  }
};

export default {
  getArticles,
  getArticleById,
  getAnalytics,
  getSources,
  getTopics,
  analyzeSentiment,
  getUserSettings,
  updateUserSettings,
  getSavedArticles,
  saveArticle,
  unsaveArticle,
  checkArticleSavedStatus,
};
