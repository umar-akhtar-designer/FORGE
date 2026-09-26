export type ErrorCode =
  | 'OK'
  | 'PAYMENT_NOT_LOCKED'
  | 'SESSION_NOT_FOUND'
  | 'ORDER_ALREADY_EXISTS'
  | 'UNAUTHORIZED'
  | 'BAD_ARGS'
  | 'PAYMENT_CONFIRMATION_FAILED'
  | 'INTERNAL'

export interface Result<T = unknown> {
  ok: boolean
  value: T | null
  error?: ErrorCode
}

export function ok<T>(value: T): Result<T> {
  return { ok: true, value }
}

export function fail(error: ErrorCode): Result<never> {
  return { ok: false, value: null, error }
}