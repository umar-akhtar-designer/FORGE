import { describe, it, expect } from 'vitest'
import { completeCheckout } from '../../packages/payments/src/checkout'
import { PaymentLock } from '../../packages/payments/src/lock'
import { OrderRepository } from '../../packages/database/src/orders'
import { SessionStore } from '../../packages/database/src/sessions'
import { createLogger } from '../../packages/shared/src/logger'
import type { CheckoutDeps } from '../../packages/payments/src/checkout'

function deps(): CheckoutDeps {
  const logger = createLogger('test')
  return { lock: new PaymentLock(logger), orders: new OrderRepository(), sessions: new SessionStore(), logger }
}

describe('completeCheckout (single path)', () => {
  it('books an order when payment holds the session', async () => {
    const d = deps()
    await d.sessions.save({
      id: 'sess_happy',
      status: 'confirmed',
      totalMinor: 4999,
      currency: 'usd',
      customerEmail: 'buyer@example.com',
      items: [{ id: 'sku_1', name: 'Pro plan', qty: 1, unitPrice: 4999 }],
      updatedAt: 0,
    })
    await d.lock.acquire('sess_happy')
    const result = await completeCheckout('sess_happy', d)
    expect(result.ok).toBe(true)
    expect(result.order?.sessionId).toBe('sess_happy')
    expect(await d.lock.isHeld('sess_happy')).toBe(false)
  })

  it('refuses to book an order without an active payment hold', async () => {
    const d = deps()
    await d.sessions.save({
      id: 'sess_unlocked',
      status: 'payment_received',
      totalMinor: 4999,
      currency: 'usd',
      customerEmail: 'buyer@example.com',
      items: [{ id: 'sku_1', name: 'Pro plan', qty: 1, unitPrice: 4999 }],
      updatedAt: 0,
    })
    const result = await completeCheckout('sess_unlocked', d)
    expect(result.ok).toBe(false)
    expect(result.code).toBe('PAYMENT_NOT_LOCKED')
    expect(await d.orders.count()).toBe(0)
  })

  it('reports missing sessions', async () => {
    const d = deps()
    await d.lock.acquire('sess_ghost')
    const result = await completeCheckout('sess_ghost', d)
    expect(result.code).toBe('SESSION_NOT_FOUND')
  })
})