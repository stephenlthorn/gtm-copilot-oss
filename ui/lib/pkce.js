import crypto from 'crypto';

const GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth';
const GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token';

function getClientId() {
  return process.env['GOOGLE_CLIENT_ID'] || process.env['GOOGLE_DRIVE_CLIENT_ID'] || '';
}

function getClientSecret() {
  return process.env['GOOGLE_CLIENT_SECRET'] || process.env['GOOGLE_DRIVE_CLIENT_SECRET'] || '';
}

function getRedirectUri() {
  const base = process.env['NEXT_PUBLIC_APP_URL'] || process.env['NEXTAUTH_URL'] || 'http://localhost:3000';
  return `${base}/api/auth/exchange`;
}

export function generateVerifier() {
  return crypto.randomBytes(32).toString('base64url');
}

export function generateChallenge(verifier) {
  const hash = crypto.createHash('sha256').update(verifier).digest();
  return Buffer.from(hash).toString('base64url');
}

export function buildAuthUrl(verifier) {
  const challenge = generateChallenge(verifier);
  const state = crypto.randomBytes(16).toString('hex');
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: getClientId(),
    redirect_uri: getRedirectUri(),
    scope: 'openid email profile',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
    access_type: 'offline',
    prompt: 'select_account',
  });
  return {
    url: `${GOOGLE_AUTH_URL}?${params}`,
    state,
  };
}

export async function exchangeCode(code, verifier) {
  const res = await fetch(GOOGLE_TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: getClientId(),
      client_secret: getClientSecret(),
      code,
      code_verifier: verifier,
      redirect_uri: getRedirectUri(),
    }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Token exchange failed: ${res.status} ${body}`);
  }
  return res.json();
}

export function parseIdToken(idToken) {
  const parts = idToken.split('.');
  if (parts.length < 2) return {};
  try {
    return JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
  } catch {
    return {};
  }
}
