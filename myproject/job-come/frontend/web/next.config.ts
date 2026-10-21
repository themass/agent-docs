import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// Backend API origin for the dev proxy. Override with JC_API_PROXY_TARGET
// when the default port (8001) is unavailable locally (e.g. port conflicts).
const apiProxyTarget = process.env.JC_API_PROXY_TARGET || "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
  outputFileTracingRoot: rootDir,
  // Backend preview stream has a 240s whole-request budget (two language tracks).
  // Export review has its own 180s client watchdog; the proxy must not be the shorter deadline.
  experimental: { proxyTimeout: 300_000 },
  async rewrites() {
    return [
      {
        source: "/health/:path*",
        destination: `${apiProxyTarget}/health/:path*`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${apiProxyTarget}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
