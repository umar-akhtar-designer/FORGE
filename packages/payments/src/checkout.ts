import type { PaymentLock } from './lock'
import type { OrderRepository } from '../../database/src/orders'
import type { SessionStore } from '../../database/src/sessions'
import type { Order } from '../../database/src/orders'
import type { Logger } from '../../shared/src/logger'
import type { ErrorCode } from '../../shared/src/errors'

export interface CheckoutDeps {
  lock: PaymentLock
  orders: OrderRepository
  sessions: SessionStore
  logger: Logger
}

export interface CheckoutResult {
  ok: boolean
  code: ErrorCode
  order: Order | null
}

/**
 * Finalize a checkout after payment has been confirmed.
 *
 * Safe implementation:
 *  1. Idempotency — if an order already exists for the session, return it.
 *     A late or duplicate confirmation (webhook replay, storefront retry) can
 *     never observe PAYMENT_NOT_LOCKED or create a second order.
 *  2. Hold check — only create the order while the payment hold is live.
 *  3. Atomic create — OrderRepository.create is idempotent and runs in one
 *     synchronous turn, so concurrent webhook + API completions serialize.
 */
export async function completeCheckout(sessionId: string, deps: CheckoutDeps): Promise<CheckoutResult> {
  const session = await deps.sessions.get(sessionId)
  if (!session) {
    return { ok: false, code: 'SESSION_NOT_FOUND', order: null }
  }

  const prior = deps.orders.findBySession(sessionId)
  if (prior) {
    deps.logger.info('checkout already completed; returning existing order', { sessionId, orderId: prior.id })
    return { ok: true, code: 'OK', order: prior }
  }

  const held = await deps.lock.isHeld(sessionId)
  if (!held) {
    deps.logger.warn('order stage reached without an active payment hold', { sessionId })
    return { ok: false, code: 'PAYMENT_NOT_LOCKED', order: null }
  }

  const order = deps.orders.create(session)
  await deps.lock.release(sessionId)
  deps.logger.info('checkout completed', { sessionId, orderId: order.id })
  return { ok: true, code: 'OK', order }
}