import { v4 as uuid } from 'uuid'
import type { Logger } from '../../shared/src/logger'
import type { SessionStore } from '../../database/src/sessions'

export interface ConfirmationRecord {
  eventId: string
  sessionId: string
  confirmedAt: number
}

/**
 * Records idempotency keys for payment confirmations. A real integration
 * would persist these so replays of the same Stripe event are ignored.
 */
export class ConfirmationLedger {
  private readonly ledger = new Map<string, ConfirmationRecord>()
  private readonly logger: Logger

  constructor(logger: Logger) {
    this.logger = logger
  }

  async record(eventId: string, sessionId: string): Promise<ConfirmationRecord> {
    const record: ConfirmationRecord = { eventId, sessionId, confirmedAt: Date.now() }
    this.ledger.set(eventId, record)
    this.logger.info('payment confirmation recorded', { eventId, sessionId })
    return record
  }

  async has(eventId: string): Promise<boolean> {
    return this.ledger.has(eventId)
  }

  async get(eventId: string): Promise<ConfirmationRecord | null> {
    return this.ledger.get(eventId) ?? null
  }
}

export interface ConfirmResult {
  ok: boolean
  code?: string
  sessionId: string
  confirmationId?: string
}

/**
 * Confirm a payment for a checkout session.
 */
export async function confirmPayment(sessionId: string, deps: {
  sessions: SessionStore
  ledger: ConfirmationLedger
  logger: Logger
}): Promise<ConfirmResult> {
  const session = await deps.sessions.get(sessionId)
  if (!session) {
    deps.logger.warn('attempted to confirm unknown session', { sessionId })
    return { ok: false, code: 'SESSION_NOT_FOUND', sessionId }
  }
  const eventId = `evt_${uuid()}`
  const record = await deps.ledger.record(eventId, sessionId)
  await deps.sessions.markStatus(sessionId, 'confirmed')
  deps.logger.info('payment confirmed', { sessionId, eventId })
  return { ok: true, sessionId, confirmationId: record.eventId }
}