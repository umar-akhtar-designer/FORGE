import { describe, it, expect } from 'vitest'
import { OrderRepository } from '../../packages/database/src/orders'

function session(id: string) {
  return {
    id,
    status: 'confirmed' as const,
    totalMinor: 9990,
    currency: 'usd',
    customerEmail: 'buyer@example.com',
    items: [{ id: 'sku_2', name: 'Team plan', qty: 1, unitPrice: 9990 }],
    updatedAt: 0,
  }
}

describe('OrderRepository', () => {
  it('creates an order from a confirmed session', async () => {
    const repo = new OrderRepository()
    const order = await repo.create(session('sess_o1'))
    expect(order.sessionId).toBe('sess_o1')
    expect(await repo.count()).toBe(1)
  })

  it('finds an order by session id', async () => {
    const repo = new OrderRepository()
    const order = await repo.create(session('sess_o2'))
    expect(await repo.findBySession('sess_o2')).toEqual(order)
  })

  it('creates distinct orders per unique session', async () => {
    const repo = new OrderRepository()
    await repo.create(session('sess_o3a'))
    await repo.create(session('sess_o3b'))
    expect(repo.list('sess_o3a')).toHaveLength(1)
    expect(repo.list('sess_o3b')).toHaveLength(1)
    expect(await repo.count()).toBe(2)
  })
})