import { ReactNode } from 'react';
import Head from 'next/head';
import { Container, Box } from '@mui/material';
import Navigation from './Navigation';

interface LayoutProps {
  children: ReactNode;
  title?: string;
  description?: string;
}

const Layout = ({ children, title = 'Financial News Platform', description = 'Real-time financial news analysis with AI' }: LayoutProps) => {
  return (
    <>
      <Head>
        <title>{title}</title>
        <meta name="description" content={description} />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <Navigation />
        
        <Container component="main" maxWidth="lg" sx={{ flexGrow: 1, py: 4 }}>
          {children}
        </Container>
        
        <Box component="footer" sx={{ py: 3, px: 2, mt: 'auto', backgroundColor: 'background.paper' }}>
          <Container maxWidth="lg">
            <Box sx={{ textAlign: 'center', color: 'text.secondary', fontSize: '0.875rem' }}>
              © {new Date().getFullYear()} Financial News Platform. All rights reserved.
            </Box>
          </Container>
        </Box>
      </Box>
    </>
  );
};

export default Layout;
