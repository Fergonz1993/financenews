// API utility for fetching news from FastAPI backend
export const fetchNews = async () => {
  const response = await fetch(`${process.env.REACT_APP_API_URL}/api/news`);
  if (!response.ok) throw new Error('Failed to fetch news');
  return response.json();
};
