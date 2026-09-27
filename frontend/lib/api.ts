import type {
  MissionDetail,
  MissionReport,
  MissionSummary,
  RepositoryIndex,
  Skill,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? "";
const TIMEOUT_MS = 15000;

async function authHeaders(): Promise<Record<string, string>> {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {};
}

async function fetchJson(path: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      ...init,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`${path} -> timed out after ${TIMEOUT_MS / 1000}s`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetchJson(path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const attempt = async (): Promise<Response> =>
    fetchJson(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await authHeaders()) },
      body: JSON.stringify(body),
    });
  let res: Response | undefined;
  for (let tries = 0; tries < 3; tries += 1) {
    res = await attempt();
    if (res.ok || ![429, 502, 503, 504].includes(res.status)) break;
    await new Promise((r) => setTimeout(r, 700 * (tries + 1)));
  }
  if (!res) throw new Error(`${path} -> no response`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<{ status: string; uptime_s: number }>("/api/health"),
  missions: () => get<MissionSummary[]>("/api/missions"),
  mission: (id: string) => get<MissionDetail>(`/api/missions/${id}`),
  report: (id: string) => get<MissionReport>(`/api/missions/${id}/report`),
  repositories: () => get<RepositoryIndex[]>("/api/repositories"),
  skills: () => get<Skill[]>("/api/skills"),
  launch: (payload: { title?: string; mission_text: string; repository?: string; seed?: number }) =>
    post<{ mission_id: string; status: string }>("/api/missions", payload),
  uploadRepo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_URL}/api/repositories/upload`, {
      method: "POST",
      headers: API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {},
      body: form,
      cache: "no-store",
    }).then(async (res) => {
      if (!res.ok) {
        const detail = (await res.json().catch(() => null))?.detail;
        throw new Error(detail ?? `${"/api/repositories/upload"} -> ${res.status}`);
      }
      return res.json() as Promise<RepositoryIndex>;
    });
  },
  connectRepo: (url: string) =>
    post<{ status?: string; key?: string; name?: string }>("/api/repositories/connect", { url }),
  connectStatus: (url: string) =>
    get<{ status: string; key?: string; index?: RepositoryIndex; message?: string }>(
      `/api/repositories/connect/status?url=${encodeURIComponent(url)}`
    ),
  releaseGate: (id: string) => get<{ overall: string; checks: { name: string; status: string; detail: string }[] }>(`/api/missions/${id}/release-gate`),
  githubStatus: () => get<{ enabled: boolean; repository: string | null }>("/api/github/status"),
  openPr: (id: string) =>
    fetch(`${API_URL}/api/missions/${id}/pr`, {
      method: "POST",
      headers: API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {},
      cache: "no-store",
    }).then(async (res) => {
      if (!res.ok) {
        const detail = (await res.json().catch(() => null))?.detail;
        throw new Error(detail ?? `PR request -> ${res.status}`);
      }
      return res.json() as Promise<{ number: number; url: string; branch: string }>;
    }),
};