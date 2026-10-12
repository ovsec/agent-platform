import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // self-contained server for the container image (Dockerfile)
};

export default nextConfig;
