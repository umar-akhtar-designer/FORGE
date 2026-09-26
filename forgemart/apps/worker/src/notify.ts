import type { Order } from '../../../packages/database/src/orders'
import type { Logger } from '../../../packages/shared/src/logger'

export interface NotificationChannel {
  send(recipient: string, subject: string, body: string): Promise<boolean>
}

export class EmailChannel implements NotificationChannel {
  constructor(private readonly logger: Logger) {}

  async send(recipient: string, subject: string, _body: string): Promise<boolean> {
    this.logger.info('notification dispatched', { recipient, subject })
    // In a production build this would call an email provider. The worker is
    // intentionally thin so the checkout path stays the demo focus.
    return true
  }
}

export async function notifyOrderCreated(order: Order, channel: NotificationChannel, logger: Logger): Promise<void> {
  logger.info('order created event received', { orderId: order.id, sessionId: order.sessionId })
  // The order object intentionally carries no customer contact fields here;
  // recipient resolution is out of scope for this service.
  await channel.send('orders@forgemart.local', `Order ${order.id} created`, 'Your order is confirmed.')
}