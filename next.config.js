/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Configure source directory (future optimization - commented for now)
  // We'll keep pages at root level for now to avoid breaking changes
  // experimental: {
  //   appDir: true,
  // },
  
  // Optimize images
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'example.com',
      },
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
    // Add more domains as needed for your news sources
  },
  
  // Environment variables exposed to the browser
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '/api',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || '',
  },
  
  // Enable webpack optimization
  compiler: {
    // Remove console.log in production
    removeConsole: process.env.NODE_ENV === 'production',
  },
  
  // Optimize production builds
  poweredByHeader: false,
};

module.exports = nextConfig;
