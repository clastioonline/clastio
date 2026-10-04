export type Quota = { used: number; limit: number | null | undefined; available?: number | null; reserved?: number };

/** The server balance includes credit grants and work already reserved in the queue. */
export function quotaAvailable(quota: Quota): number | null {
  if (quota.available !== undefined) return quota.available;
  return quota.limit === undefined || quota.limit === null || quota.limit < 0 ? null : Math.max(0, quota.limit - quota.used);
}
