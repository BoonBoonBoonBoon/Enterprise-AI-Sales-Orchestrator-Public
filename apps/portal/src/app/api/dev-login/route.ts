import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function POST() {
  const gatewayBaseUrl = process.env.API_GATEWAY_URL || 'http://localhost:8000';
  const devSecret = process.env.DEV_LOGIN_SECRET || process.env.NEXT_PUBLIC_DEV_LOGIN_SECRET;

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (devSecret) {
    headers['X-Dev-Login-Secret'] = devSecret;
  }

  const response = await fetch(`${gatewayBaseUrl}/api/v1/auth/dev-login`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      tenant_id: 'agentic-dev',
      email: 'dev-admin@example.com',
      role: 'admin',
    }),
  });

  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: { 'Content-Type': response.headers.get('content-type') || 'application/json' },
  });
}
