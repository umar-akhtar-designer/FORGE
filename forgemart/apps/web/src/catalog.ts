import type { CartItem, Money } from '../../../packages/shared/src/types'

export interface CatalogProduct {
  id: string
  name: string
  price: Money
}

const CATALOG: CatalogProduct[] = [
  { id: 'sku_pro', name: 'Pro Plan — annual', price: { currency: 'usd', amountMinor: 59940 } },
  { id: 'sku_team', name: 'Team Plan — annual', price: { currency: 'usd', amountMinor: 119880 } },
]

export async function fetchCatalog(apiBase: string, timeoutMs = 3000): Promise<CatalogProduct[]> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${apiBase}/catalog`, { signal: controller.signal })
    if (!res.ok) throw new Error(`catalog request failed: ${res.status}`)
    const json = (await res.json()) as { items: CatalogProduct[] }
    return json.items
  } finally {
    clearTimeout(timer)
  }
}

export function toCartItems(products: CatalogProduct[]): CartItem[] {
  return products.map((p) => ({
    id: p.id,
    name: p.name,
    qty: 1,
    unitPrice: p.price.amountMinor,
  }))
}