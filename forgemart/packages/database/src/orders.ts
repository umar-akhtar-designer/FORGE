import type { CheckoutSession } from './sessions'
import type { CartItem } from '../../shared/src/types'

export interface Order {
  id: string
  sessionId: string
  items: CartItem[]
  totalMinor: number
  currency: string
  status: 'created' | 'fulfilled'
  createdAt: number
}

let sequence = 0

function nextId(): string {
  sequence += 1
  return `ord_${Date.now().toString(36)}_${sequence}`
}

/**
 * In-memory order repository.
 *
 * NOTE (known gap): `create` has no uniqueness constraint on `sessionId` and
 * does not consult `findBySession` before inserting. Every call that reaches
 * it produces a brand-new order row.
 */
export class OrderRepository {
  private readonly orders = new Map<string, Order>()
  private readonly bySession = new Map<string, Order[]>()

  async findBySession(sessionId: string): Promise<Order | null> {
    const list = this.bySession.get(sessionId)
    return list && list.length > 0 ? (list[0] as Order) : null
  }

  async create(session: CheckoutSession): Promise<Order> {
    const order: Order = {
      id: nextId(),
      sessionId: session.id,
      items: session.items,
      totalMinor: session.totalMinor,
      currency: session.currency,
      status: 'created',
      createdAt: Date.now(),
    }
    this.orders.set(order.id, order)
    const list = this.bySession.get(session.id) ?? []
    list.push(order)
    this.bySession.set(session.id, list)
    return order
  }

  async count(): Promise<number> {
    return this.orders.size
  }

  list(sessionId: string): Order[] {
    return this.bySession.get(sessionId) ?? []
  }
}