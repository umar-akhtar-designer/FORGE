import { completeCheckout } from '../../../../packages/payments/src/checkout'
import type { CheckoutDeps } from '../../../../packages/payments/src/checkout'
import { confirmPayment, ConfirmationLedger } from '../../../../packages/payments/src/confirm'
import type { Logger } from '../../../../packages/shared/src/logger'

export interface StripeLikeEvent {
  id: string
  type: string
  data: { session_id: string }
  occurred_at: number
}

/**
 * Payment webhook dispatch.
 *
 * Stripe (test mode) delivers `checkout.session.completed` here. The handler
 * acquires the payment hold, records a confirmation idempotency key, marks the
 * session confirmed, and then completes the checkout itself.
 */
export async function dispatchPaymentWebhook(
  event: StripeLikeEvent,
  deps: CheckoutDeps & { ledger: ConfirmationLedger },
  logger: Logger,
): Promise<{ accepted: boolean }> {
  if (!event || event.type !== 'checkout.session.completed') {
    return { accepted: false }
  }
  const sessionId = event.data.session_id

  if (await deps.ledger.has(event.id)) {
    logger.info('duplicate webhook event ignored', { eventId: event.id })
    return { accepted: true }
  }

  await deps.lock.acquire(sessionId)
  await confirmPayment(sessionId, { sessions: deps.sessions, ledger: deps.ledger, logger })
  const result = await completeCheckout(sessionId, deps)
  if (!result.ok) {
    logger.warn('webhook checkout completion did not succeed', { sessionId, code: result.code })
  }
  return { accepted: true }
}