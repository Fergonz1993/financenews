 push/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  // Optimize images
  images: {
    domains: ['example.com', 'images.unsplash.com'],
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
  },
  // Configure API routes
  serverRuntimeConfig: {
    // Will only be available on the server side
    apiBodySizeLimit: '1mb',
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
