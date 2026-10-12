import { quotaAvailable, type Quota } from "./usage";

export const authAccountSystemRoutes = [
  { slug: "session-expired", title: "Sign-in status", description: "Check your session and continue to the page you intended to open." },
  { slug: "account-suspended", title: "Account access", description: "Check current account access and contact support when access is restricted." },
  { slug: "account-deactivated", title: "Account availability", description: "Review account availability and the available recovery steps." },
  { slug: "account-deleted", title: "Account closure status", description: "Find help with an account closure or deletion request." },
  { slug: "delete-account", title: "Request account deletion", description: "Review the account closure process and confirm a deletion request." },
  { slug: "verification-success", title: "Email verification status", description: "Check the email verification state returned by your account." },
  { slug: "verification-failed", title: "Email verification help", description: "Check verification status and request a fresh verification email." },
  { slug: "link-expired", title: "Sign-in link help", description: "Get a fresh verification, reset or sign-in link." },
  { slug: "email-unsubscribe", title: "Email preferences", description: "Review email marketing preferences for your signed-in account." },
  { slug: "notification-preferences", title: "Notification preferences", description: "Choose available notification channels for your account." },
] as const;

export const billingSystemRoutes = [
  { slug: "payment-success", title: "Payment confirmation", description: "Check payment confirmation and the current subscription returned by billing." },
  { slug: "payment-failed", title: "Payment help", description: "Review confirmed payment issues and open the available recovery options." },
  { slug: "subscription-expired", title: "Subscription status", description: "Check current paid access and the available plan options." },
  { slug: "trial-expired", title: "Trial status", description: "Check whether your trial is active or has ended." },
  { slug: "usage-limit", title: "Usage and allowances", description: "Review current available and reserved allowances." },
  { slug: "upgrade-required", title: "Plan access", description: "Review your current plan and the allowance needed for your task." },
  { slug: "billing-portal", title: "Payment settings", description: "Open the secure billing portal for a supported subscription." },
  { slug: "checkout", title: "Checkout", description: "Resume a server-confirmed checkout or choose a plan." },
  { slug: "subscription-cancelled", title: "Cancellation status", description: "Check cancellation status and review a cancellation request." },
] as const;

export type AccountSystemKind = typeof authAccountSystemRoutes[number]["slug"];
export type BillingSystemKind = typeof billingSystemRoutes[number]["slug"];
export type StateView = { title: string; description: string; tone: "neutral" | "success" | "warn" | "danger" };
export type BillingState = {
  plan: { code: string; name: string };
  subscription?: { status: string; provider?: string; interval?: string; cancel_at_period_end?: boolean; current_period_end?: string | null } | null;
  pending_checkout?: { id?: string; status: string; provider?: string; url?: string | null; plan?: string; expires_at?: string } | null;
  trial?: { active?: boolean; ended?: boolean; days_left?: number; ends_at?: string } | null;
  usage?: Record<string, Quota>;
  payments?: { status: string; date?: string; invoice_url?: string | null }[];
};

export function confirmedPaidAccess(data: BillingState): boolean {
  return Boolean(data.plan?.code && data.plan.code !== "free" && !data.pending_checkout
    && data.subscription?.status === "active" && ["stripe", "dodo"].includes(data.subscription.provider || ""));
}

export function availableUsageResource(value: string | null | undefined): string {
  return ["credits", "ai_images", "whatsapp_messages", "storage_mb"].includes(value || "") ? value! : "credits";
}

export function billingStateView(kind: BillingSystemKind, data: BillingState, resource = "credits"): StateView {
  const sub = data.subscription;
  const paid = confirmedPaidAccess(data);
  const plan = data.plan?.name || "your current plan";
  if (kind === "trial-expired") {
    if (data.trial?.active) return { title: "Your trial is active", description: `Billing currently shows an active ${plan} trial. Review its remaining allowance before generating.`, tone: "success" };
    if (data.trial?.ended) return { title: "Your trial has ended", description: `Your current plan is ${plan}. Review the allowance available now or choose a paid plan.`, tone: "warn" };
    return { title: "Check your trial status", description: "Billing does not show an ended trial for this account. Review current plan access and any available trial in Plan & billing.", tone: "neutral" };
  }
  if (kind === "subscription-cancelled") {
    if (sub?.cancel_at_period_end) return { title: "Cancellation is scheduled", description: `Billing confirms cancellation at the end of the current period. Your current plan is ${plan}; review the access date below.`, tone: "warn" };
    if (sub?.status === "canceled" || sub?.status === "cancelled") return { title: "Your subscription is cancelled", description: `The billing service reports a cancelled subscription. Your current plan is ${plan}.`, tone: "neutral" };
    return { title: "Review cancellation status", description: "Billing has not confirmed a cancellation for the current subscription. You can review its details or explicitly request cancellation below.", tone: "neutral" };
  }
  if (kind === "usage-limit" || kind === "upgrade-required") {
    const quota = data.usage?.[availableUsageResource(resource)];
    if (!quota) return { title: "Check your plan allowance", description: `Your current plan is ${plan}. Open Plan & billing to review the allowance for the task you want to perform.`, tone: "neutral" };
    const balance = quotaAvailable(quota);
    if (balance === 0 && (quota.reserved || 0) > 0) return { title: "Allowance is reserved for queued work", description: "Your available balance includes work already in progress. Review Activity and the reserved amount before deciding to generate more.", tone: "warn" };
    if (balance === 0) return { title: "This allowance is currently unavailable", description: `The billing service reports no available ${availableUsageResource(resource).replaceAll("_", " ")} for ${plan}. Review plan options or contact support if the balance looks wrong.`, tone: "warn" };
    return { title: "Your allowance is available", description: balance === null ? "Billing reports an unlimited allowance for this resource. Check the current task estimate before generating." : `Billing reports ${balance} available for this resource. A task can still require more than the remaining balance; check its estimate before continuing.`, tone: "success" };
  }
  if (kind === "payment-failed") {
    if (paid) return { title: "Your current subscription is active", description: `Billing confirms active ${plan} access. Review payment history if you need to check a particular transaction.`, tone: "success" };
    if (["past_due", "unpaid", "incomplete"].includes(sub?.status || "") || data.payments?.[0]?.status === "failed") return { title: "A payment needs attention", description: "The billing service reports a payment issue. Review the current subscription and use the secure payment settings when available.", tone: "warn" };
    if (data.pending_checkout) return { title: "Payment confirmation is pending", description: "There is a checkout awaiting completion or confirmation. Review its current status before starting another checkout.", tone: "neutral" };
    return { title: "Review your payment status", description: "A failed payment has not been confirmed for this account. Review Plan & billing or contact support about a specific transaction.", tone: "neutral" };
  }
  if (kind === "payment-success") {
    if (paid) return { title: "Your subscription is active", description: `The billing service confirms active ${plan} access. Your payment history provides any available receipt or invoice.`, tone: "success" };
    return { title: "Checking payment confirmation", description: data.pending_checkout ? "Your checkout is still open or awaiting confirmation. Your current plan stays in place until the payment service confirms the change." : "This page cannot confirm a new payment yet. Your current plan is shown below; refresh billing or contact support if you expected a change.", tone: "neutral" };
  }
  if (kind === "checkout") return data.pending_checkout
    ? { title: data.pending_checkout.status === "processing" ? "Payment confirmation is pending" : "Resume your checkout", description: "Review the existing checkout below. The account’s current access remains the plan confirmed by billing.", tone: "neutral" }
    : { title: "Choose a plan", description: "There is no pending checkout in the current billing response. Review current prices and choose a plan when you are ready.", tone: "neutral" };
  if (kind === "billing-portal") return { title: "Manage payment settings", description: sub && ["stripe", "dodo"].includes(sub.provider || "") ? "Open the secure billing portal to review payment methods, invoices and subscription options." : "A supported online subscription is not shown for this account. Review Plan & billing or contact support about school-provided access.", tone: "neutral" };
  return { title: `Current plan: ${plan}`, description: "Review the access currently confirmed by billing. If you expected a different plan, check the subscription details or contact support.", tone: data.plan?.code === "free" ? "neutral" : "success" };
}

/** Redirect destinations are taken only from a successful API response, never a query string. */
export function safePaymentDestination(value: string, origin: string): string | null {
  try {
    if (!value.trim() || /[\\\u0000-\u001f\u007f]/.test(value)) return null;
    const url = new URL(value, origin);
    if (url.username || url.password) return null;
    return url.protocol === "https:" || url.origin === origin ? url.href : null;
  } catch { return null; }
}
