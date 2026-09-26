import { Router } from '../http'
import type { Logger } from '../../../../packages/shared/src/logger'

export function healthRouter(logger: Logger): Router {
  const router = new Router()
  router.get('/health', (_req, res) => {
    res.json({ status: 'ok', service: 'forgemart-api', at: new Date().toISOString() })
  })
  router.get('/_info', (_req, res) => {
    res.json({
      name: 'ForgeMart',
      version: '0.9.0',
      env: process.env.NODE_ENV ?? 'development',
      hints: { xPoweredBy: true },
    })
  })
  return router
}