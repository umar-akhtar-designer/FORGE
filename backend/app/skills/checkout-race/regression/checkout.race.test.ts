import { describe, it, expect } from 'vitest'
import { completeCheckout, type CheckoutDeps } from '../../packages/payments/src/checkout'
import { PaymentLock } from '../../packages/payments/src/lock'
import { OrderRepository } from '../../packages/database/src/orders'
import { SessionStore, type CheckoutSession } from '../../packages/database/src/sessions'
import { createLogger, type Logger } from '../../packages/shared/src/logger'

const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0))

function session(id: string): CheckoutSession {
  return {
    id,
    status: 'confirmed',
    totalMinor: 4999,
    currency: 'usd',
    customerEmail: 'buyer@example.com',
    items: [{ id: 'sku_1', name: 'Pro plan', qty: 1, unitPrice: 4999 }],
    updatedAt: 0,
  }
}

function makeDeps(): CheckoutDeps {
  const logger: Logger = createLogger('regression')
  return {
    lock: new PaymentLock(logger),
    orders: new OrderRepository(),
    sessions: new SessionStore(),
    logger,
  }
}

describe('checkout payment-confirmation race (regression)', () => {
  it('never creates duplicate orders when the webhook and the API confirm concurrently', async () => {
    const d = makeDeps()
    const sessionId = 'sess_race_001'
    await d.sessions.save(session(sessionId))

    // The payment webhook acquires the hold before it lands.
    await d.lock.acquire(sessionId)

    // Deterministically pause both confirmations inside the session read so
    // the interleaving is instrument-controlled, not timing-dependent.
    let release!: () => void
    const gate = new Promise<void>((resolve) => { release = resolve })
    const gatedSessions = Object.create(d.sessions) as SessionStore
    const originalGet = d.sessions.get.bind(d.sessions)
    gatedSessions.get = async (id: string) => {
      await gate
      return originalGet(id)
    }
    const gated: CheckoutDeps = { ...d, sessions: gatedSessions }

    const first = completeCheckout(sessionId, gated)
    await flush()
    const second = completeCheckout(sessionId, gated)
    await flush()
    release()

    const [r1, r2] = await Promise.all([first, second])
    expect(r1.ok).toBe(true)
    expect(r1.ok && r2.ok).toBe(true)
    expect(d.orders.list(sessionId)).toHaveLength(1)
  })

  it('returns the existing order when a storefront confirm arrives after the webhook released the hold', async () => {
    const d = makeDeps()
    const sessionId = 'sess_race_002'
    await d.sessions.save(session(sessionId))
    await d.lock.acquire(sessionId)

    const first = await completeCheckout(sessionId, d)
    expect(first.ok).toBe(true)
    expect(await d.lock.isHeld(sessionId)).toBe(false)

    const late = await completeCheckout(sessionId, d)
    expect(late.ok).toBe(true)
    expect(late.ok && late.order?.id).toBe(first.order?.id)
    expect(d.orders.list(sessionId)).toHaveLength(1)
  })
})