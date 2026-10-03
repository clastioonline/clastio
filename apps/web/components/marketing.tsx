import Link from "next/link";
import { Logo } from "@/components/brand";

/* Floating rounded navigation bar used on the landing page. */
export function LandingNav() {
  return (
    <div className="px-4 pt-4 sm:px-6">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between rounded-2xl bg-[var(--l-card)]/85 px-4 shadow-sm ring-1 ring-black/5 backdrop-blur">
        <Logo className="[&>span]:hidden sm:[&>span]:inline" />
        <nav className="hidden items-center gap-7 text-sm text-[var(--l-muted)] xl:flex" aria-label="Main">
          <a href="/#features" className="hover:text-[var(--l-ink)]">Features</a>
          <Link href="/how-it-works" className="hover:text-[var(--l-ink)]">How it works</Link>
          <Link href="/pricing" className="hover:text-[var(--l-ink)]">Pricing</Link>
          <Link href="/solutions" className="hover:text-[var(--l-ink)]">Teacher guides</Link>
          <Link href="/for-schools" className="hover:text-[var(--l-ink)]">For schools</Link>
          <Link href="/faq" className="hover:text-[var(--l-ink)]">FAQ</Link>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login" className="rounded-full px-3 py-2 text-sm font-medium text-[var(--l-ink)] hover:bg-black/5">Sign in</Link>
          <Link href="/signup" className="rounded-full bg-[#141414] px-4 py-2 text-sm font-medium text-white hover:bg-black">Start free</Link>
        </div>
      </header>
      <nav className="mx-auto mt-2 flex max-w-6xl flex-wrap justify-center gap-x-5 gap-y-1 rounded-xl bg-[var(--l-card)] px-3 py-2 text-sm xl:hidden" aria-label="Explore Clastio">
        <a href="/#features" className="focus-ring py-2">Features</a><a href="/#example" className="focus-ring py-2">Example</a><Link href="/pricing" className="focus-ring py-2">Pricing</Link><Link href="/solutions" className="focus-ring py-2">Teacher guides</Link><Link href="/faq" className="focus-ring py-2">FAQ</Link>
      </nav>
    </div>
  );
}

export function LandingFooter() {
  return (
    <footer className="border-t border-[var(--l-line)]">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 text-sm text-[var(--l-muted)] sm:px-6 md:grid-cols-4">
        <div className="space-y-3">
          <Logo />
          <p>Made for teachers in the UAE, India and beyond.</p>
        </div>
        <div className="space-y-2">
          <div className="font-semibold text-[var(--l-ink)]">Product</div>
          <Link href="/pricing" className="block hover:text-[var(--l-ink)]">Pricing</Link>
          <a href="/#features" className="block hover:text-[var(--l-ink)]">Features</a>
          <Link href="/for-schools" className="block hover:text-[var(--l-ink)]">Schools</Link>
          <Link href="/how-it-works" className="block hover:text-[var(--l-ink)]">How it works</Link>
          <Link href="/faq" className="block hover:text-[var(--l-ink)]">Questions</Link>
        </div>
        <div className="space-y-2">
          <div className="font-semibold text-[var(--l-ink)]">Legal & trust</div>
          <Link href="/legal/terms" className="block hover:text-[var(--l-ink)]">Terms & Conditions</Link>
          <Link href="/legal/privacy" className="block hover:text-[var(--l-ink)]">Privacy Policy</Link>
          <Link href="/legal/acceptable_use" className="block hover:text-[var(--l-ink)]">Acceptable Use</Link>
          <Link href="/legal/cookie" className="block hover:text-[var(--l-ink)]">Cookie Policy</Link>
          <Link href="/legal/refund" className="block hover:text-[var(--l-ink)]">Refund Policy</Link>
          <Link href="/status" className="block hover:text-[var(--l-ink)]">System status</Link>
        </div>
        <div className="space-y-2">
          <div className="font-semibold text-[var(--l-ink)]">Teacher resources</div>
          <Link href="/solutions" className="block hover:text-[var(--l-ink)]">All teacher guides</Link>
          <Link href="/solutions/personal-ai-teaching-assistant" className="block hover:text-[var(--l-ink)]">Personal teaching assistant</Link>
          <Link href="/solutions/edit-ppt-without-regenerating" className="block hover:text-[var(--l-ink)]">Edit PPTs with fewer credits</Link>
          <p>British · CBSE · ICSE · American · IB · UAE MoE · UAE AI curriculum</p>
        </div>
      </div>
      <div className="border-t border-[var(--l-line)] py-4 text-center text-xs text-[var(--l-muted)]">© {new Date().getFullYear()} Clastio</div>
    </footer>
  );
}
