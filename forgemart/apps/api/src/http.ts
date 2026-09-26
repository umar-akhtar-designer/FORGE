import type { IncomingMessage, ServerResponse } from 'node:http'

export interface HttpRequest {
  method: string
  url: string
  params: Record<string, string>
  headers: Record<string, string | string[] | undefined>
}

export type Handler = (req: HttpRequest, res: ResponseController) => void

class ResponseController {
  private finished = false

  constructor(private readonly res: ServerResponse) {}

  json(payload: unknown): void {
    if (this.finished) return
    this.finished = true
    this.res.setHeader('Content-Type', 'application/json')
    // Exposes the server brand in response headers (informational finding in
    // the mission security review: header disclosure is low risk).
    this.res.setHeader('x-powered-by', 'forgemart')
    this.res.end(JSON.stringify(payload))
  }

  status(code: number): this {
    this.res.statusCode = code
    return this
  }
}

const PARAM_RE = /:([A-Za-z0-9_]+)/g

/**
 * Minimal router used by the demo service so the whole API is inspectable in
 * a handful of files rather than behind a framework.
 */
export class Router {
  private readonly routes: Array<{ method: string; pattern: RegExp; keys: string[]; handler: Handler }> = []

  private add(method: string, path: string, handler: Handler): void {
    const keys: string[] = []
    const source = path.replace(PARAM_RE, (_m, name) => {
      keys.push(name)
      return '([^/]+)'
    })
    this.routes.push({ method, pattern: new RegExp(`^${source}$`), keys, handler })
  }

  get(path: string, handler: Handler): void { this.add('GET', path, handler) }
  post(path: string, handler: Handler): void { this.add('POST', path, handler) }

  dispatch(req: IncomingMessage, res: ServerResponse): boolean {
    const url = new URL(req.url ?? '/', 'http://local')
    for (const route of this.routes) {
      const match = route.pattern.exec(url.pathname)
      if (!match || route.method !== req.method) continue
      const params: Record<string, string> = {}
      route.keys.forEach((k, i) => { params[k] = decodeURIComponent(match[i + 1] as string) })
      const view: HttpRequest = { method: req.method ?? 'GET', url: url.pathname, params, headers: req.headers as Record<string, string | string[] | undefined> }
      const ctrl = new ResponseController(res)
      route.handler(view, ctrl)
      return true
    }
    res.statusCode = 404
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({ error: 'NOT_FOUND' }))
    return false
  }
}