/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['res.cloudinary.com'],
  },
  env: {
    // Environment variables that work for both local and Railway
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws',
  },
  async rewrites() {
    // Only use proxy for local development
    if (process.env.NODE_ENV === 'development') {
      return [
        // API proxy for regular HTTP requests
        {
          source: '/api/:path*',
          destination: 'http://localhost:8000/api/:path*', // Proxy to backend
        },
        // WebSocket proxy (note: Next.js can't proxy WebSockets, but include this for documentation)
        {
          source: '/ws',
          destination: 'http://localhost:8000/ws', // WebSocket endpoint
        },
        // Health check endpoint
        {
          source: '/health',
          destination: 'http://localhost:8000/api/health',
        },
      ]
    }
    return []
  },
}

module.exports = nextConfig
/* Force frontend redeploy Fri Nov 8 20:00:00 UTC+8 2025 */
