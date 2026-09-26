import { createServer } from 'node:http'
import { Router } from './http'
import { SessionStore, OrderRepository } from '../../../packages/database/src'
import { PaymentLock, ConfirmationLedger } from '../../../packages/payments/src'
import { Scheme } from '../../../packages/auth/src'
import { loadConfig } from '../../../packages/shared/src/env'
import { createLogger } from '../../../packages/shared/src/logger'
import { healthRouter } from './routes/health'
import { checkoutRouter } from './routes/checkout'
import { dispatchPaymentWebhook } from './webhooks/payment'
import type { CheckoutDeps } from '../../../packages/payments/src/checkout'

export function bootstrap(): { router: Router; deps: CheckoutDeps & { ledger: ConfirmationLedger }; config: ReturnType<typeof loadConfig> } {
  const config = loadConfig()
  const logger = createLogger('forgemart')

  const sessions = new SessionStore()
  const orders = new OrderRepository()
  const lock = new PaymentLock(logger)
  const ledger = new ConfirmationLedger(logger)
  const auth = new Scheme(config)

  const payments: CheckoutDeps = { lock, orders, sessions, logger }
  const router = new Router()

  const health = healthRouter(logger)
  const checkout = checkoutRouter({ payments, auth, logger })

  router.get('/webhooks/payment', () => {})
  router.post('/webhooks/payment', (req, res) => {
    void dispatchPaymentWebhook(
      { id: 'evt_replay', type: 'checkout.session.completed', data: { session_id: 'sess_example' }, occurred_at: Date.now() },
      { ...payments, ledger },
      logger,
    ).then((result) => res.json({ accepted: result.accepted }))
  })

  return { router, deps: { ...payments, ledger }, config }
}

export function createApp(): Router {
  return bootstrap().router
}

export function handle(req: import('node:http').IncomingMessage, res: import('node:http').ServerResponse): void {
  createApp().dispatch(req, res)
}

if (import.meta.url === `file://${process.argv[1] ?? ''}`) {
  const { router, config } = bootstrap()
  const server = createServer((req, res) => router.dispatch(req, res))
  server.listen(config.port, () => {
    createLogger('bootstrap').info('ForgeMart API listening', { port: config.port })
  })
}