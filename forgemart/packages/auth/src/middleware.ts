import type { Scheme, SessionToken, SignedToken } from './tokens'
import type { Logger } from '../../shared/src/logger'

export interface AuthContext {
  subject: string
  sessionId: string
}

export type AuthResult =
  | { ok: true; context: AuthContext }
  | { ok: false; reason: 'MISSING' | 'INVALID' | 'EXPIRED' }

const MAX_AGE_MS = 24 * 60 * 60 * 1000

/**
 * Bearer-token middleware for the HTTP layer. Rejects unauthenticated or
 * malformed request contexts and never falls back silently.
 */
export function verifyAuth(
  authorization: string | undefined,
  scheme: Scheme,
  logger: Logger,
): AuthResult {
  if (!authorization) {
    logger.warn('request missing authorization header')
    return { ok: false, reason: 'MISSING' }
  }
  const match = /^Bearer (.+)$/.exec(authorization)
  if (!match) {
    logger.warn('authorization header not a bearer token')
    return { ok: false, reason: 'INVALID' }
  }
  let raw: SignedToken
  try {
    raw = JSON.parse(Buffer.from(match[1] as string, 'base64url').toString('utf8'))
  } catch {
    return { ok: false, reason: 'INVALID' }
  }
  const token: SessionToken | null = scheme.verifyToken(raw)
  if (!token) {
    logger.warn('bad token signature')
    return { ok: false, reason: 'INVALID' }
  }
  if (Date.now() - token.issuedAt > MAX_AGE_MS) {
    logger.warn('token expired', { subject: token.subject })
    return { ok: false, reason: 'EXPIRED' }
  }
  return { ok: true, context: { subject: token.subject, sessionId: token.sessionId } }
}