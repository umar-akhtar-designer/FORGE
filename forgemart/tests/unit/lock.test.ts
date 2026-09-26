import { describe, it, expect } from 'vitest'
import { createLogger } from '../../packages/shared/src/logger'
import { PaymentLock } from '../../packages/payments/src/lock'

const logger = createLogger('test')

describe('PaymentLock', () => {
  it('acquires and releases a hold for a session', async () => {
    const lock = new PaymentLock(logger)
    expect(await lock.acquire('sess_1')).toBe(true)
    expect(await lock.isHeld('sess_1')).toBe(true)
    expect(await lock.release('sess_1')).toBe(true)
    expect(await lock.isHeld('sess_1')).toBe(false)
  })

  it('does not double-acquire a hold', async () => {
    const lock = new PaymentLock(logger)
    await lock.acquire('sess_2')
    expect(await lock.acquire('sess_2')).toBe(false)
  })

  it('tracks distinct sessions independently', async () => {
    const lock = new PaymentLock(logger)
    await lock.acquire('sess_3')
    expect(await lock.isHeld('sess_other')).toBe(false)
  })
})