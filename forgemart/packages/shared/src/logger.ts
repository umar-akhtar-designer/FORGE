export type LogLevel = 'debug' | 'info' | 'warn' | 'error'

const LEVELS: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40 }

/**
 * Minimal structured logger. Writes JSON lines to stdout so mission
 * post-mortems can correlate what happened in what order.
 */
export class Logger {
  readonly scope: string
  private readonly threshold: number

  constructor(scope: string, threshold: LogLevel = 'info') {
    this.scope = scope
    this.threshold = LEVELS[threshold]
  }

  private emit(level: LogLevel, message: string, fields?: Record<string, unknown>): void {
    if (LEVELS[level] < this.threshold) return
    const line = { at: new Date().toISOString(), level, scope: this.scope, message, ...fields }
    // eslint-disable-next-line no-console
    if (level === 'error') console.error(JSON.stringify(line))
    else console.log(JSON.stringify(line))
  }

  debug(message: string, fields?: Record<string, unknown>): void { this.emit('debug', message, fields) }
  info(message: string, fields?: Record<string, unknown>): void { this.emit('info', message, fields) }
  warn(message: string, fields?: Record<string, unknown>): void { this.emit('warn', message, fields) }
  error(message: string, fields?: Record<string, unknown>): void { this.emit('error', message, fields) }

  child(scope: string): Logger {
    const level: LogLevel = this.threshold >= LEVELS.error ? 'error' : 'info'
    return new Logger(`${this.scope}/${scope}`, level)
  }
}

export function createLogger(scope: string): Logger {
  return new Logger(scope)
}