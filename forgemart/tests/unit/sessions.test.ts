import { describe, it, expect } from 'vitest'
import { SessionStore } from '../../packages/database/src/sessions'

function session(id: string) {
  return {
    id,
    status: 'authorized' as const,
    totalMinor: 4999,
    currency: 'usd',
    customerEmail: 'buyer@example.com',
    items: [{ id: 'sku_1', name: 'Pro plan', qty: 1, unitPrice: 4999 }],
    updatedAt: 0,
  }
}

describe('SessionStore', () => {
  it('saves and retrieves a session', async () => {
    const store = new SessionStore()
    await store.save(session('sess_a'))
    expect(await store.get('sess_a')).toMatchObject({ id: 'sess_a', status: 'authorized' })
  })

  it('returns null for unknown sessions', async () => {
    const store = new SessionStore()
    expect(await store.get('missing')).toBeNull()
  })

  it('marks status transitions', async () => {
    const store = new SessionStore()
    await store.save(session('sess_b'))
    await store.markStatus('sess_b', 'confirmed')
    expect((await store.get('sess_b'))?.status).toBe('confirmed')
  })
})