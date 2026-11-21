import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Docker image uses a small self-contained server; Vercel and "next start" do not need it.
  output: process.env.NEXT_STANDALONE ? "standalone" : undefined,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
