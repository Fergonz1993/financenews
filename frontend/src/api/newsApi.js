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

export default {
  getArticles,
  getArticleById,
  getAnalytics,
  getSources,
  getTopics,
};
