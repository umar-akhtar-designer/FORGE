import { createHmac, timingSafeEqual } from 'node:crypto'
import type { RuntimeConfig } from '../../shared/src/env'

export interface SessionToken {
  subject: string
  sessionId: string
  issuedAt: number
}

export interface SignedToken {
  payload: string
  signature: string
}

/**
 * HMAC-signed session token. Secrets always come from runtime config
 * (environment), never from the source tree.
 */
export class Scheme {
  private readonly secret: string

  constructor(config: RuntimeConfig) {
    this.secret = config.appSecret
  }

  private sign(payload: string): string {
    return createHmac('sha256', this.secret).update(payload).digest('hex')
  }

  signToken(token: SessionToken): SignedToken {
    const payload = Buffer.from(JSON.stringify(token)).toString('base64url')
    return { payload, signature: this.sign(payload) }
  }

  verifyToken(raw: { payload: string; signature: string }): SessionToken | null {
    const expected = this.sign(raw.payload)
    const a = Buffer.from(expected, 'hex')
    const b = Buffer.from(raw.signature, 'hex')
    if (a.length !== b.length || !timingSafeEqual(a, b)) return null
    try {
      return JSON.parse(Buffer.from(raw.payload, 'base64url').toString('utf8')) as SessionToken
    } catch {
      return null
    }
  }
}