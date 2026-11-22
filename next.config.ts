import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required by the production Dockerfile: Next emits a self-contained server.
  output: "standalone",
};

export default nextConfig;
