import { Router } from '../http'
import type { CheckoutDeps } from '../../../../packages/payments/src/checkout'
import { verifyAuth } from '../../../../packages/auth/src/middleware'
import type { Scheme } from '../../../../packages/auth/src/tokens'
import type { Logger } from '../../../../packages/shared/src/logger'

/**
 * Checkout routes.
 *
 * The storefront confirms a checkout through this endpoint the moment the
 * client-side payment succeeds. The payment webhook also completes the same
 * checkout on the server. Both paths funnel into {@link completeCheckout};
 * making that hand-off safe is the responsibility of the payments package.
 */
export function checkoutRouter(deps: { payments: CheckoutDeps; auth: Scheme; logger: Logger }): Router {
  const router = new Router()

  router.post('/checkout/:sessionId/confirm', (req, res) => {
    const auth = verifyAuth(req.headers.authorization as string | undefined, deps.auth, deps.logger)
    if (!auth.ok) {
      res.status(401).json({ error: 'UNAUTHORIZED' })
      return
    }
    if (auth.context.sessionId !== req.params.sessionId) {
      res.status(403).json({ error: 'UNAUTHORIZED' })
      return
    }

    // Fire and track. The caller (storefront) waits for the JSON response.
    void completeCheckoutWithTracking(req.params.sessionId, deps.payments)
      .then((result) => {
        if (!result.ok) {
          res.status(409).json({ error: result.code, sessionId: req.params.sessionId })
          return
        }
        res.json({ order: result.order })
      })
      .catch((err) => {
        deps.logger.error('checkout route failure', { sessionId: req.params.sessionId, error: String(err) })
        res.status(500).json({ error: 'INTERNAL' })
      })
  })

  return router
}

async function completeCheckoutWithTracking(sessionId: string, deps: CheckoutDeps) {
  // Imported here to keep the route module readable.
  const { completeCheckout } = await import('../../../../packages/payments/src/checkout')
  return completeCheckout(sessionId, deps)
}