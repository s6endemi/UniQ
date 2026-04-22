import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow the dev server to accept requests from 127.0.0.1 as well as
  // localhost. Without this Next.js 16 blocks /_next/webpack-hmr from
  // 127.0.0.1 and live CSS/React reload silently stops working —
  // which looks like "the page is broken" even when the initial load
  // is fine.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  experimental: {
    // Enables React's <ViewTransition> integration for route navigations.
    // Browsers that don't support the API (older Safari) still get a
    // normal instant nav — no fallback code required.
    viewTransition: true,
  },
};

export default nextConfig;
