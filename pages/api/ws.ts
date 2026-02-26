import { NextApiRequest, NextApiResponse } from 'next';
import { Server } from 'socket.io';
import { Server as HttpServer } from 'http';
import type { Socket } from 'socket.io';

const SocketHandler = (req: NextApiRequest, res: NextApiResponse) => {
  const socketServer = (res.socket as { server?: HttpServer & { io?: Server } } | null | undefined)?.server;

  if (!socketServer) {
    return res.status(500).send('Socket server not available');
  }

    if (socketServer.io) {
    console.log('Socket is already running');
  } else {
    console.log('Socket is initializing');
    const io = new Server(socketServer, {
      path: '/api/ws',
      cors: {
        origin: '*',
      },
    });
    socketServer.io = io;

    io.on('connection', socket => {
      console.log(`Client connected: ${socket.id}`);
      
      // Send connection confirmation
      socket.emit('message', JSON.stringify({
        type: 'connection_established',
        timestamp: new Date().toISOString()
      }));

      // Setup demo alerts (simulating backend events)
      const stopDemoAlerts = setupDemoAlerts(socket);

      socket.on('disconnect', () => {
        stopDemoAlerts();
        console.log(`Client disconnected: ${socket.id}`);
      });
    });
  }
  res.end();
};

// Function to simulate backend events for demo purposes
function setupDemoAlerts(socket: Socket): () => void {
  // Market alerts
  const marketAlerts = [
    {
      title: 'Market volatility increased',
      details: 'VIX index jumped 15% in early trading due to geopolitical tensions.',
      source: 'Market Data',
      severity: 'warning'
    },
    {
      title: 'Fed announces interest rate decision',
      details: 'Federal Reserve keeps interest rates unchanged as expected.',
      source: 'Federal Reserve',
      severity: 'info'
    },
    {
      title: 'S&P 500 reaches new all-time high',
      details: 'The index closed at a record level, led by technology and healthcare sectors.',
      source: 'Market Data',
      severity: 'success'
    }
  ];

  // News updates
  const newsUpdates = [
    {
      title: 'Tech Giant Exceeds Earnings Expectations',
      summary: 'The company reported a 25% increase in quarterly revenue, beating analyst estimates.',
      source: 'Financial Times',
      url: '/articles/article-1'
    },
    {
      title: 'Major Merger Announced in Banking Sector',
      summary: 'Two of the largest banks have agreed to merge in a $50 billion deal, pending regulatory approval.',
      source: 'Bloomberg',
      url: '/articles/article-2'
    }
  ];

  let active = true;
  let timer: ReturnType<typeof setTimeout> | undefined;

  // Send random alerts periodically
  const sendRandomAlert = () => {
    if (!active || !socket.connected) {
      return;
    }

    const now = new Date();
    const hour = now.getHours();
    
    // Only send alerts during business hours in demo
    if (hour >= 9 && hour <= 17) {
      const isMarketAlert = Math.random() > 0.5;
      
      if (isMarketAlert) {
        const alert = marketAlerts[Math.floor(Math.random() * marketAlerts.length)];
        socket.emit('message', JSON.stringify({
          type: 'market_alert',
          alert,
          timestamp: now.toISOString()
        }));
      } else {
        const news = newsUpdates[Math.floor(Math.random() * newsUpdates.length)];
        socket.emit('message', JSON.stringify({
          type: 'news_update',
          news,
          timestamp: now.toISOString()
        }));
      }
    }
    
    // Schedule next alert
    const delay = 30000 + Math.random() * 60000; // 30-90 seconds
    timer = setTimeout(sendRandomAlert, delay);
  };

  // Start sending alerts after a short delay
  timer = setTimeout(sendRandomAlert, 5000);

  return () => {
    active = false;
    if (timer) {
      clearTimeout(timer);
    }
  };
}

export default SocketHandler;
