/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const gatewayBaseUrl = process.env.API_GATEWAY_URL;
    return [
      {
        source: '/api/v1/:path*',
        destination: gatewayBaseUrl
          ? `${gatewayBaseUrl}/api/v1/:path*`
          : 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
