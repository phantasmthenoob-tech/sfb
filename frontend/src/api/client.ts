// The static dashboard has no backend of its own. If the build environment does
// not provide VITE_API_BASE, production falls back to the deployed API so a
// plain `npm run build` still produces a working site. Local development keeps
// using Vite's same-origin proxy.
const PRODUCTION_API_BASE = "https://sfbackend-9nsb.onrender.com";
const configuredBase = (import.meta.env.VITE_API_BASE ?? "").trim();
const isLoopback = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
const API_BASE = (
  configuredBase || (import.meta.env.PROD && !isLoopback ? PRODUCTION_API_BASE : "")
).replace(/\/$/, "");

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export function wsMarketUrl(): string {
  const explicit = import.meta.env.VITE_WS_URL as string | undefined;
  if (explicit) return explicit;
  if (API_BASE) return `${API_BASE.replace(/^http/, "ws")}/ws/market`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/market`;
}

async function parse<T>(response: Response): Promise<T> {
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ?? detail?.reason ?? `Request failed (${response.status})`;
    throw new Error(message);
  }
  return body as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { headers: { Accept: "application/json" } });
  return parse<T>(response);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? "{}" : JSON.stringify(body),
  });
  return parse<T>(response);
}
