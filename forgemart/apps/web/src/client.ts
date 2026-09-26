import type { CartSummary } from '../../../packages/shared/src/types'

export interface ConfirmResponse {
  order?: { id: string; sessionId: string; totalMinor: number }
  error?: string
}

/**
 * Client helper the storefront uses to confirm a checkout after the payment
 * provider reports success on the client side. Aborts if the API is slow so
 * the user is never left hanging twice.
 */
export async function confirmCheckoutClient(apiBase: string, sessionId: string, token: string, timeoutMs = 5000): Promise<ConfirmResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${apiBase}/checkout/${sessionId}/confirm`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      signal: controller.signal,
    })
    const body = (await res.json()) as ConfirmResponse
    if (!res.ok) return { error: body.error ?? `HTTP ${res.status}` }
    return body
  } catch (err) {
    return { error: err instanceof Error ? err.message : 'request failed' }
  } finally {
    clearTimeout(timer)
  }
}

export function invoiceSummary(items: CartSummary['items']): CartSummary {
  const totalMinor = items.reduce((acc, it) => acc + it.unitPrice * it.qty, 0)
  const currency = items[0]?.unitPrice ? '' : 'usd'
  return { items, totalMinor, currency }
}