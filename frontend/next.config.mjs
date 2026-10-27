const getBackendDestination = () => {
  const backendUrl = process.env.BACKEND_URL;
  const publicApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (backendUrl) {
    return `${backendUrl.replace(/\/+$/, '')}/api/:path*`;
  }
  if (publicApiUrl) {
    const cleaned = publicApiUrl.replace(/\/+$/, '');
    return cleaned.endsWith('/api') ? `${cleaned}/:path*` : `${cleaned}/api/:path*`;
  }
  return 'http://127.0.0.1:5000/api/:path*';
};

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: getBackendDestination(),
      },
    ];
  },
  async redirects() {
    return [
      {
        source: '/documents',
        destination: '/schemes',
        permanent: false,
      },
      {
        source: '/documents/:path*',
        destination: '/schemes',
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
