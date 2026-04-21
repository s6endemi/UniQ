import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Enables React's <ViewTransition> integration for route navigations.
    // Browsers that don't support the API (older Safari) still get a
    // normal instant nav — no fallback code required.
    viewTransition: true,
  },
};

export default nextConfig;
