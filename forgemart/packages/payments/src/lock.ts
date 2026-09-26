import type { Logger } from '../../shared/src/logger'

export interface PaymentHold {
  held: boolean
  sessionId: string
  acquiredAt: number
}

/**
 * Payment lock. Represents the distributed lock that a real Stripe
 * integration acquires when a payment becomes chargeable so that exactly one
 * worker finalizes the checkout.
 */
export class PaymentLock {
  private readonly holds = new Map<string, PaymentHold>()
  private readonly logger: Logger

  constructor(logger: Logger) {
    this.logger = logger
  }

  async acquire(sessionId: string): Promise<boolean> {
    if (this.holds.has(sessionId)) {
      this.logger.debug('payment hold already present', { sessionId })
      return false
    }
    this.holds.set(sessionId, { held: true, sessionId, acquiredAt: Date.now() })
    this.logger.info('payment hold acquired', { sessionId })
    return true
  }

  async isHeld(sessionId: string): Promise<boolean> {
    return this.holds.get(sessionId)?.held ?? false
  }

  /** Number of current holds — surfaced in mission telemetry. */
  async size(): Promise<number> {
    return this.holds.size
  }

  async release(sessionId: string): Promise<boolean> {
    const released = this.holds.delete(sessionId)
    if (released) this.logger.info('payment hold released', { sessionId })
    return released
  }
}