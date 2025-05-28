import { useState, useEffect } from 'react';
import { Grid, Typography, Paper, Box } from '@mui/material';
import Layout from '../components/Layout';

export default function HomePage() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch articles from the API
    const fetchArticles = async () => {
      try {
        const response = await fetch('/api/articles?limit=10');
        if (!response.ok) throw new Error('Failed to fetch articles');
        const data = await response.json();
        setArticles(data);
      } catch (error) {
        console.error('Error fetching articles:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchArticles();
  }, []);

  return (
    <Layout title="Financial News Dashboard" description="Real-time financial news analysis and insights">
        <Box sx={{ mb: 4 }}>
          <Typography variant="h3" component="h1" gutterBottom>
            Financial News Dashboard
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Real-time financial news analysis and insights
          </Typography>
        </Box>

        {loading ? (
          <Typography>Loading latest financial news...</Typography>
        ) : (
          <Grid container spacing={3}>
            {articles.map((article: any) => (
              <Grid item xs={12} key={article.id}>
                <Paper 
                  elevation={2} 
                  sx={{ 
                    p: 3, 
                    borderLeft: 6, 
                    borderColor: 
                      article.sentiment === 'positive' ? 'success.main' : 
                      article.sentiment === 'negative' ? 'error.main' : 
                      'warning.main' 
                  }}
                >
                  <Typography variant="h5" component="h2" gutterBottom>
                    {article.title}
                  </Typography>
                  
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Source: {article.source}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(article.published_at).toLocaleString()}
                    </Typography>
                  </Box>
                  
                  <Typography variant="body1" paragraph>
                    {article.summarized_headline}
                  </Typography>
                  
                  <Box component="ul">
                    {article.summary_bullets?.map((bullet: string, index: number) => (
                      <Typography component="li" key={index}>
                        {bullet}
                      </Typography>
                    ))}
                  </Box>
                  
                  <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {article.topics?.map((topic: string) => (
                      <Box 
                        key={topic} 
                        sx={{ 
                          px: 1, 
                          py: 0.5, 
                          bgcolor: 'primary.light', 
                          color: 'white',
                          borderRadius: 1,
                          fontSize: '0.8rem'
                        }}
                      >
                        {topic}
                      </Box>
                    ))}
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
        )}
    </Layout>
  );
}
