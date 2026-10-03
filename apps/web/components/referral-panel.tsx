"use client";
import { useState } from "react";
import { Copy, Gift, Share2, Trophy } from "lucide-react";
import { Panel } from "@/components/dash";
import { Button, Input } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { errorMessage, useToast } from "@/components/toast";

export function ReferralPanel() {
  const {data, error} = useApi<any>("/billing/referrals");
  const {notify} = useToast();
  const [copied, setCopied] = useState(false);
  if (error) return <Panel title="Invite a teacher"><p className="text-sm text-muted">Your referral link is temporarily unavailable. Refresh to try again.</p></Panel>;
  if (!data) return null;
  const share = async () => {
    try {
      if (navigator.share) await navigator.share({title: "Try Clastio", text: "Create lessons in your own slide design.", url: data.url});
      else { await navigator.clipboard.writeText(data.url); setCopied(true); }
    } catch (e) { if ((e as Error).name !== "AbortError") notify({tone: "error", title: "Couldn't share", body: errorMessage(e)}); }
  };
  return <div className="grid gap-5 lg:grid-cols-2">
    {data.enabled && <Panel title="Invite a teacher, create together">
      <p className="mb-4 text-sm text-muted"><Gift className="me-1 inline h-4 w-4" />You and your friend each earn {data.reward_media_credits} media credits after their first paid subscription. Share your link before they sign up.</p>
      <Input aria-label="Your referral link" value={data.url} readOnly onFocus={(e) => e.target.select()} />
      <div className="my-4 flex flex-wrap gap-2"><Button size="sm" onClick={async () => { try { await navigator.clipboard.writeText(data.url); setCopied(true); } catch { notify({tone: "error", title: "Select the link above to copy it"}); } }}><Copy className="h-4 w-4" />{copied ? "Copied" : "Copy invite link"}</Button><Button size="sm" variant="ghost" onClick={share}><Share2 className="h-4 w-4" />Share</Button></div>
      <p className="text-sm text-ink-2">{data.invited} joined · {data.qualified} qualified · {data.earned_media_credits} media credits earned</p>
      <p className="mt-2 text-xs text-muted">New teacher accounts only. A verified email and a successful subscription payment are required. One reward per referred account. Media credits are separate from lesson credits.</p>
    </Panel>}
    <Panel title="Your teaching progress"><Trophy className="mb-3 h-6 w-6 text-brand-600" /><p className="text-3xl font-semibold">{data.progress.completed_tasks}</p><p className="mt-1 text-sm text-muted">Teaching tasks completed with Clastio</p><p className="mt-4 text-sm text-ink-2">{data.progress.next_milestone ? `${data.progress.next_milestone - data.progress.completed_tasks} more to your next milestone of ${data.progress.next_milestone}.` : "You've passed 100 completed tasks. Keep creating!"}</p></Panel>
  </div>;
}
