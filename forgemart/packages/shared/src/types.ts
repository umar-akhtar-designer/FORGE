export interface CartItem {
  id: string
  name: string
  qty: number
  unitPrice: number
}

export interface Money {
  currency: string
  amountMinor: number
}

export interface PaymentAuthorizedEvent {
  eventId: string
  sessionId: string
  occurredAt: number
}

export type CartSummary = { items: CartItem[]; totalMinor: number; currency: string }