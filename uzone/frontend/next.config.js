const defaultAllowedDevOrigins = ['localhost', '127.0.0.1']

function normalizeAllowedOrigin(origin) {
  const trimmedOrigin = origin.trim()

  if (!trimmedOrigin) {
    return null
  }

  try {
    return new URL(trimmedOrigin).hostname.toLowerCase()
  } catch {
    return trimmedOrigin
      .replace(/^[a-z]+:\/\//i, '')
      .split('/')[0]
      .split(':')[0]
      .toLowerCase()
  }
}

const allowedDevOrigins = Array.from(
  new Set([
    ...defaultAllowedDevOrigins,
    ...(process.env.UZONE_ALLOWED_ORIGINS || '')
      .split(',')
      .map(normalizeAllowedOrigin)
      .filter(Boolean),
  ])
)

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  allowedDevOrigins,
}

module.exports = nextConfig
