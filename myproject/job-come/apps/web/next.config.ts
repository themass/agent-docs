import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  outputFileTracingRoot: rootDir,
  devIndicators: {
    appIsrStatus: false,
  },
  async rewrites() {
    return [
      {
        source: "/health/:path*",
        destination: "http://127.0.0.1:8000/health/:path*",
      },
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
