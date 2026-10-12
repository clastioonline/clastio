/** Public catalogue only. The server fetch is called after the pricing route receives a request. */
export type Plan = {
  code: string;
  name: string;
  price_monthly_aed: number;
  price_annual_aed: number;
  features: string[];
  limits: Record<string, any>;
};

export type PlansResponse = {
  items: Plan[];
  currency?: "AED";
  vat_rate: number;
  online_payments: boolean;
  payment_provider: string | null;
  trial: { enabled: boolean; plan: string; days: number; credits: number };
};

const MAX_BYTES = 64 * 1024;
const TIMEOUT_MS = 3000;
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown, max: number): value is string =>
  typeof value === "string" && !!value.trim() && value.length <= max;
const amount = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 10_000_000;
const count = (value: unknown): value is number => amount(value) && Number.isSafeInteger(value);
const code = (value: unknown): value is string =>
  typeof value === "string" && /^[a-z0-9][a-z0-9_-]{0,63}$/.test(value);

/** Reject malformed prices and whitelist the public fields passed into the page. */
export function parsePublicPricing(value: unknown): PlansResponse | null {
  if (!object(value) || (value.currency !== undefined && value.currency !== "AED") || !Array.isArray(value.items) ||
      value.items.length < 1 || value.items.length > 32 ||
      typeof value.online_payments !== "boolean" ||
      !(value.payment_provider === null || text(value.payment_provider, 64)) ||
      !amount(value.vat_rate) || value.vat_rate > 1 || !object(value.trial)) return null;
  const items: Plan[] = [];
  for (const item of value.items) {
    if (!object(item) || !code(item.code) || !text(item.name, 100) ||
        !amount(item.price_monthly_aed) || !amount(item.price_annual_aed) ||
        !Array.isArray(item.features) || item.features.length > 50 ||
        !item.features.every((feature) => text(feature, 1000)) || !object(item.limits) ||
        !count(item.limits.credits) || !count(item.limits.max_lectures)) return null;
    items.push({ code: item.code, name: item.name, price_monthly_aed: item.price_monthly_aed,
      price_annual_aed: item.price_annual_aed, features: item.features,
      limits: { credits: item.limits.credits, max_lectures: item.limits.max_lectures } });
  }
  if (new Set(items.map((item) => item.code)).size !== items.length) return null;
  const trial = value.trial;
  if (typeof trial.enabled !== "boolean" || !code(trial.plan) || !count(trial.days) ||
      !count(trial.credits) || (trial.enabled &&
        (!trial.days || !items.some((item) => item.code === trial.plan)))) return null;
  return { items, currency: "AED", vat_rate: value.vat_rate,
    online_payments: value.online_payments, payment_provider: value.payment_provider,
    trial: { enabled: trial.enabled, plan: trial.plan, days: trial.days, credits: trial.credits } };
}

/** No incoming headers, cookies or API keys; no persistent price cache or redirect. */
export async function fetchPublicPricing(baseUrl = process.env.API_URL || "http://localhost:8000"): Promise<PlansResponse | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const base = new URL(baseUrl);
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password) return null;
    const response = await fetch(new URL("/api/v1/billing/plans", base), {
      method: "GET", headers: { accept: "application/json" }, credentials: "omit",
      redirect: "error", cache: "no-store", signal: controller.signal,
    });
    if (!response.ok || !response.headers.get("content-type")?.includes("application/json") ||
        Number(response.headers.get("content-length")) > MAX_BYTES || !response.body) {
      await response.body?.cancel();
      return null;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let bytes = 0;
    let body = "";
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        bytes += value.byteLength;
        if (bytes > MAX_BYTES) {
          await reader.cancel();
          return null;
        }
        body += decoder.decode(value, { stream: true });
      }
      body += decoder.decode();
    } finally {
      reader.releaseLock();
    }
    return parsePublicPricing(JSON.parse(body));
  } catch {
    // Keep the public page usable without claiming an unavailable catalogue's prices.
    return null;
  } finally {
    clearTimeout(timer);
  }
}
