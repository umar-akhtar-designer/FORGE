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
 * This version of the pipeline is what ships inside ForgeMart. It guards order
 * creation with the payment hold, but the guard has a subtle lifetime problem:
 * the hold is only meaningful while payment is being confirmed, and order
 * creation is not idempotent — nothing prevents a second path from reaching
 * this function for the same session while the first path is still booking the
 * order (or just after the hold has been released).
 */
export async function completeCheckout(sessionId: string, deps: CheckoutDeps): Promise<CheckoutResult> {
  const held = await deps.lock.isHeld(sessionId)
  if (!held) {
    deps.logger.warn('order stage reached without an active payment hold', { sessionId })
    return { ok: false, code: 'PAYMENT_NOT_LOCKED', order: null }
  }

  const session = await deps.sessions.get(sessionId)
  if (!session) {
    return { ok: false, code: 'SESSION_NOT_FOUND', order: null }
  }

  const order = await deps.orders.create(session)
  await deps.lock.release(sessionId)
  deps.logger.info('checkout completed', { sessionId, orderId: order.id })
  return { ok: true, code: 'OK', order }
}