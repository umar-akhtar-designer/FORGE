import { describe, it, expect } from 'vitest'
import { loadConfig, isSecretInline } from '../../packages/shared/src/env'

describe('runtime config', () => {
  it('loads secrets from the environment', () => {
    process.env.APP_SECRET = 'env-secret-abc'
    process.env.STRIPE_WEBHOOK_SECRET = 'whsec_env_xyz'
    const config = loadConfig()
    expect(config.appSecret).toBe('env-secret-abc')
  })

  it('flags inline production-style keys', () => {
    expect(isSecretInline('sk_live_0123456789abcdefghij')).toBe(true)
    expect(isSecretInline('sk_test_0123456789abcdefghij')).toBe(true)
    expect(isSecretInline('from ${process.env.SECRET}')).toBe(false)
  })
})