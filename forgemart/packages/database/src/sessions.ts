export type SessionStatus = 'authorized' | 'payment_received' | 'confirmed' | 'failed'

export interface CheckoutSession {
  id: string
  status: SessionStatus
  totalMinor: number
  currency: string
  customerEmail: string
  items: Array<{ id: string; name: string; qty: number; unitPrice: number }>
  updatedAt: number
}

/**
 * In-memory session store. In production this would be a real database row;
 * the shape and semantics deliberately mirror one so the mission logic is
 * faithful.
 */
export class SessionStore {
  private readonly rows = new Map<string, CheckoutSession>()

  async save(session: CheckoutSession): Promise<CheckoutSession> {
    const next = { ...session, updatedAt: Date.now() }
    this.rows.set(session.id, next)
    return next
  }

  async get(id: string): Promise<CheckoutSession | null> {
    return this.rows.get(id) ?? null
  }

  async markStatus(id: string, status: SessionStatus): Promise<CheckoutSession | null> {
    const current = this.rows.get(id)
    if (!current) return null
    return this.save({ ...current, status })
  }
}