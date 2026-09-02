import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const backendUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
    return [
      { source: "/health", destination: `${backendUrl}/health` },
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
    ];
  },
};

export default nextConfig;
