import { describe, it, expect } from 'vitest'
import { Scheme } from '../../packages/auth/src/tokens'
import { verifyAuth } from '../../packages/auth/src/middleware'
import { createLogger } from '../../packages/shared/src/logger'
import type { RuntimeConfig } from '../../packages/shared/src/env'

const config: RuntimeConfig = { env: 'test', appSecret: 'unit-test-secret', stripeWebhookSecret: 'whsec_unit', paymentProvider: 'mock', port: 0 }

describe('auth scheme', () => {
  it('signs and verifies a session token', () => {
    const scheme = new Scheme(config)
    const raw = scheme.signToken({ subject: 'user_1', sessionId: 'sess_a', issuedAt: Date.now() })
    const token = scheme.verifyToken(raw)
    expect(token?.subject).toBe('user_1')
    expect(token?.sessionId).toBe('sess_a')
  })

  it('rejects tampered payloads', () => {
    const scheme = new Scheme(config)
    const raw = scheme.signToken({ subject: 'user_1', sessionId: 'sess_a', issuedAt: Date.now() })
    const tampered = { ...raw, payload: 'bm90LXRoZS1wYXlsb2Fk' }
    expect(scheme.verifyToken(tampered)).toBeNull()
  })
})

describe('middleware', () => {
  it('rejects a missing header', () => {
    expect(verifyAuth(undefined, new Scheme(config), createLogger('test')).ok).toBe(false)
  })

  it('accepts a well-formed bearer token for the right session', () => {
    const scheme = new Scheme(config)
    const logger = createLogger('test')
    const raw = scheme.signToken({ subject: 'user_1', sessionId: 'sess_b', issuedAt: Date.now() })
    const encoded = Buffer.from(JSON.stringify(raw)).toString('base64url')
    const result = verifyAuth(`Bearer ${encoded}`, scheme, logger)
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.context.sessionId).toBe('sess_b')
  })
})