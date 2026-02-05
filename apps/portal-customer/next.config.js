/** @type {import('next').NextConfig} */
const requiredEnv = [
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_ANON_KEY',
];

const missing = requiredEnv.filter((key) => !process.env[key]);
if (missing.length > 0) {
  throw new Error(
    `Missing required env vars for portal-customer: ${missing.join(', ')}`
  );
}

if (!process.env.OPENAI_API_KEY && !process.env.ANTHROPIC_API_KEY) {
  throw new Error(
    'Missing AI provider key: set OPENAI_API_KEY or ANTHROPIC_API_KEY'
  );
}

const nextConfig = {
  reactStrictMode: true,
};

module.exports = nextConfig;
