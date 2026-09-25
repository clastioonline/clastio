import Link from "next/link";
import { Logo } from "@/components/brand";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-canvas/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav className="hidden items-center gap-7 text-sm text-ink-2 md:flex">
          <a href="/#how" className="hover:text-ink">How it works</a>
          <a href="/#features" className="hover:text-ink">Features</a>
          <Link href="/pricing" className="hover:text-ink">Pricing</Link>
          <a href="/#schools" className="hover:text-ink">For schools</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login" className="rounded-xl px-3 py-2 text-sm font-medium text-ink-2 hover:bg-surface-2">Sign in</Link>
          <Link href="/signup" className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-brand-700">Start free</Link>
        </div>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 text-sm text-muted sm:px-6 md:grid-cols-4">
        <div className="space-y-3">
          <Logo />
          <p>Made for teachers in the UAE, India and beyond.</p>
        </div>
        <div className="space-y-2">
          <div className="font-semibold text-ink">Product</div>
          <Link href="/pricing" className="block hover:text-ink">Pricing</Link>
          <a href="/#features" className="block hover:text-ink">Features</a>
          <a href="/#schools" className="block hover:text-ink">Schools</a>
        </div>
        <div className="space-y-2">
          <div className="font-semibold text-ink">Trust</div>
          <p>Your files stay yours. No student personal data required. Data export and deletion any time.</p>
        </div>
        <div className="space-y-2">
          <div className="font-semibold text-ink">Curricula</div>
          <p>British · CBSE · ICSE · American · IB · UAE MoE · UAE AI curriculum</p>
        </div>
      </div>
      <div className="border-t border-line py-4 text-center text-xs text-muted">© {new Date().getFullYear()} AI Teacher Assistant</div>
    </footer>
  );
}
