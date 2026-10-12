export const legalDocumentTitles: Record<string, string> = {
  terms: "Terms & Conditions", privacy: "Privacy Policy", acceptable_use: "Acceptable Use Policy",
  cookie: "Cookie Policy", refund: "Refund Policy", dmca: "Copyright Policy",
};

export type LegalVersion = { type: string; title: string; version: string; effective_from: string | null; status: string; };
export type PublicLegalDocument = LegalVersion & { content: string; summary_of_changes: string | null; versions: LegalVersion[] };
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown, max: number): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= max;
export const validLegalVersion = (value: string) => /^[A-Za-z0-9.-]{1,20}$/.test(value);

function version(value: unknown): LegalVersion | null {
  if (!object(value) || typeof value.type !== "string" || !Object.hasOwn(legalDocumentTitles, value.type) || !text(value.title, 200) ||
      typeof value.version !== "string" || !validLegalVersion(value.version) || typeof value.status !== "string" || !["published", "archived"].includes(value.status) ||
      !(value.effective_from === null || value.effective_from === undefined || typeof value.effective_from === "string" && Number.isFinite(Date.parse(value.effective_from)))) return null;
  return { type: value.type, title: value.title, version: value.version, effective_from: value.effective_from as string || null, status: value.status };
}

export function parseLegalDocument(value: unknown, type: string): PublicLegalDocument | null {
  const base = version(value);
  if (!base || base.type !== type || !object(value) || !text(value.content, 200_000) || !Array.isArray(value.versions) || value.versions.length > 200) return null;
  const versions = value.versions.map(version);
  if (versions.some(item => !item || item.type !== type) || !(value.summary_of_changes === null || value.summary_of_changes === undefined || typeof value.summary_of_changes === "string" && value.summary_of_changes.length <= 5000)) return null;
  return { ...base, content: value.content, summary_of_changes: value.summary_of_changes as string || null, versions: versions as LegalVersion[] };
}

export function parseLegalIndex(value: unknown): LegalVersion[] {
  if (!object(value) || !Array.isArray(value.items) || value.items.length > 100) return [];
  return value.items.flatMap(item => { const parsed = version(item); return parsed?.status === "published" ? [parsed] : []; });
}
