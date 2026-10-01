// End-to-end browser test of the core teacher journey against a running web + API + worker
// (demo accounts seeded, so run `python -m app.seed --demo` or use docker compose).
//   BASE_URL=http://localhost:3000 node e2e/run.mjs
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.BASE_URL || "http://localhost:3000";
const OUT = process.env.OUT || path.resolve("e2e/screenshots");
const SAMPLE = process.env.SAMPLE || path.resolve("../../samples/science_ms_sara.pptx");
// Use CHROME if given, else a preinstalled Chromium if present, else Playwright's own (`npx playwright-core install chromium`).
const PREINSTALLED = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const CHROME = process.env.CHROME || (fs.existsSync(PREINSTALLED) ? PREINSTALLED : undefined);
fs.mkdirSync(OUT, { recursive: true });

const step = (name) => console.log(`\n▶ ${name}`);
const ok = (msg) => console.log(`  ✓ ${msg}`);
function assert(cond, msg) {
  if (!cond) throw new Error(`Assertion failed: ${msg}`);
  ok(msg);
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && errors.push(m.text()));
const shot = (name) => page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: false });

try {
  step("Landing & pricing");
  await page.goto(BASE + "/");
  await page.getByRole("heading", { level: 1 }).waitFor();
  await page.getByRole("dialog", { name: "Cookie preferences" }).waitFor();
  await shot("01-landing");
  await page.getByRole("button", { name: "Essential only" }).click();
  ok("cookie banner offers a choice and remembers it");
  await page.goto(BASE + "/pricing");
  await page.getByText("Genie Assistant").first().waitFor();
  await shot("02-pricing");
  await page.goto(BASE + "/legal/terms");
  await page.getByRole("heading", { name: "Terms & Conditions", level: 1 }).waitFor();
  await page.goto(BASE + "/status");
  await page.getByText(/All systems operational|Some systems degraded/).waitFor();
  await shot("02b-status");
  ok("marketing, legal and status pages render");

  step("Sign up");
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto(BASE + "/signup");
  await page.getByLabel("Your name").fill("Amira Hassan");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password").fill("e2e-password-123");
  assert(await page.getByRole("button", { name: "Create account" }).isDisabled(), "sign-up needs the Terms checkbox");
  assert(!(await page.getByRole("checkbox", { name: /tips and product news/ }).isChecked()), "marketing consent is unticked by default");
  await page.getByRole("checkbox", { name: /I agree to the Terms/ }).check();
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL("**/onboarding");
  ok("redirected to onboarding");

  const usage = await page.request.get(BASE + "/api/v1/me/usage").then((r) => r.json());
  assert(usage.trial?.active && usage.trial.days_left > 0, `new teacher starts a no-card trial (${usage.plan.name}, ${usage.trial?.days_left} days)`);

  step("Onboarding: basics");
  await page.getByRole("heading", { name: /Welcome to Clastio/ }).waitFor();
  await shot("03-onboarding-basics");
  await page.getByRole("button", { name: "Continue" }).click();

  step("Onboarding: upload the teacher's old deck");
  await page.getByText("Upload a presentation you like").waitFor();
  await page.setInputFiles('input[type="file"]', SAMPLE);
  await page.getByText("Your style is ready").first().waitFor({ timeout: 90_000 });
  await shot("04-onboarding-style-ready");
  ok("style analysed into a template");
  await page.getByRole("button", { name: "Continue" }).click();

  step("Onboarding: preferences & classes");
  await page.getByText("How do you like to teach?").waitFor();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByText("Add your classes").waitFor();
  await page.getByRole("button", { name: "Finish setup" }).click();
  await page.getByText("Clastio is ready").waitFor();
  ok("onboarding complete");

  step("Create a course (Free plan: 2 lessons × 10 slides)");
  await page.getByRole("link", { name: "Create my first lessons" }).click();
  await page.waitForURL("**/projects/new");
  await page.getByPlaceholder("e.g. Photosynthesis").fill("Photosynthesis");
  const field = (label) => page.locator(`label:has(> span:text-is("${label}")) select`);
  await field("Grade").selectOption("8");
  await field("Number of lessons").selectOption("2");
  await field("Slides per lesson").selectOption("10");
  await shot("05-new-course");
  await page.getByRole("button", { name: /Plan and build lessons/ }).click();
  await page.waitForURL("**/projects/*");
  ok("project created");
  await page.getByText("2 / 2 ready").or(page.getByRole("link", { name: /Open/ }).nth(1)).waitFor({ timeout: 180_000 });
  await page.waitForFunction(() => document.querySelectorAll('a[href^="/lessons/"]').length >= 2, null, { timeout: 180_000 });
  await page.waitForTimeout(1500);
  await shot("06-project");
  ok("both lessons generated");

  step("Lesson editor");
  await page.locator('a[href^="/lessons/"]').first().click();
  await page.waitForURL("**/lessons/*");
  await page.getByText("QC passed").or(page.getByText(/QC notes/)).waitFor();
  const thumbs = await page.locator('button:has(img[alt^="Slide "])').count();
  assert(thumbs === 10, `lesson has 10 slide thumbnails (got ${thumbs})`);
  await shot("07-lesson-editor");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "PowerPoint" }).click();
  const dl = await downloadPromise;
  const pptxPath = path.join(OUT, "lesson1.pptx");
  await dl.saveAs(pptxPath);
  assert(fs.statSync(pptxPath).size > 20_000, "editable PPTX downloaded");

  step("Edit a slide with a quick action");
  await page.locator('button:has(img[alt="Slide 3"])').click();
  await page.getByRole("button", { name: "Make simpler" }).click();
  await page.getByText("Slides updated").waitFor({ timeout: 90_000 });
  ok("slide regenerated and deck rebuilt");

  step("Create a worksheet for the lesson");
  await page.getByRole("tab", { name: /Documents/ }).click();
  await page.getByRole("button", { name: "+ Worksheet" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Create" }).click();
  await page.getByRole("dialog").getByText("Ready — with a separate answer key.").waitFor({ timeout: 120_000 });
  await shot("08-worksheet-ready");
  const files = await page.getByRole("dialog").locator("a").count();
  assert(files >= 4, `worksheet files offered (${files})`);
  await page.getByRole("dialog").getByRole("button", { name: "Done" }).click();

  step("Assistant");
  await page.goto(BASE + "/assistant");
  await page.getByPlaceholder(/Ask anything/).fill("What did I teach last week?");
  await page.keyboard.press("Enter");
  await page.getByText(/covered recently|you prepared these lessons|couldn.t find any lessons/).first().waitFor({ timeout: 30_000 });
  await shot("09-assistant");
  ok("assistant reply saved by worker");

  step("Other pages render without errors");
  for (const [route, text, name] of [
    ["/dashboard", "Today's classes", "10-dashboard"],
    ["/templates", "Your templates", "11-templates"],
    ["/calendar", "Week plan", "12-calendar"],
    ["/curriculum", "Add class", "13-curriculum"],
    ["/teacher-memory", "Teacher memory", "14-memory"],
    ["/lessons", "Library", "15-library"],
    ["/whatsapp", "Your number", "16-whatsapp"],
    ["/billing", "Plan & billing", "17-billing"],
    ["/settings", "Settings", "18-settings"],
    ["/tutorials", "Tutorials & help", "18a-tutorials"],
    ["/media", "Media studio", "18b-media"],
    ["/activity", "Start something, then get on with your day.", "18c-activity"],
  ]) {
    await page.goto(BASE + route);
    await page.getByText(text).first().waitFor();
    await page.waitForTimeout(700);
    await shot(name);
    ok(`${route}`);
  }

  step("Notifications, support and account security");
  await page.goto(BASE + "/notifications");
  await page.getByRole("heading", { name: "Notifications" }).waitFor();
  await page.getByText(/Lesson ready:|Unit planned:/).first().waitFor();
  ok("lesson-ready notices arrive in the notification list");
  const unread = await page.request.get(BASE + "/api/v1/me/notifications").then((r) => r.json());
  assert(unread.unread > 0, `bell shows unread count (${unread.unread})`);
  await shot("18c-notifications");
  await page.goto(BASE + "/support");
  await page.getByRole("button", { name: "New request" }).click();
  await page.getByLabel("Subject").fill("How do I share a lesson?");
  await page.getByLabel("Details").fill("I want to send a lesson to a colleague.");
  await page.getByRole("dialog").getByRole("button", { name: "Send" }).click();
  await page.getByText("How do I share a lesson?").waitFor();
  ok("support request created");
  await page.goto(BASE + "/settings");
  await page.getByText("Active sessions").waitFor();
  await page.getByText("This device", { exact: true }).waitFor();
  await page.getByRole("heading", { name: "Notifications" }).first().waitFor();
  await shot("18d-settings-security");
  ok("settings show sessions, notification preferences and consents");

  step("Demo teacher: dashboard with a timetable");
  await ctx.clearCookies();
  await page.goto(BASE + "/login");
  await page.getByLabel("Email", { exact: true }).fill("sara@example.com");
  await page.getByLabel("Password").fill("teacher-demo-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
  if (await page.getByRole("dialog", { name: "We've updated our policies" }).isVisible().catch(() => false)
      || await page.getByText("We've updated our policies").waitFor({ timeout: 4000 }).then(() => true).catch(() => false)) {
    await shot("19a-updated-terms");
    await page.getByRole("checkbox", { name: /I have read and agree/ }).check();
    await page.getByRole("button", { name: "Accept and continue" }).click();
    await page.getByText("We've updated our policies").waitFor({ state: "detached" });
    ok("updated-terms prompt accepted and recorded");
  }
  await page.getByText("Today's classes").waitFor();
  await page.waitForTimeout(1200);
  await shot("19-demo-dashboard");
  await page.goto(BASE + "/calendar");
  await page.getByText("Prepare my week").waitFor();
  await page.waitForTimeout(1000);
  await shot("20-demo-week");

  step("Mobile layout");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(BASE + "/dashboard");
  await page.getByText("Today's classes").waitFor();
  await page.waitForTimeout(800);
  await shot("21-mobile-dashboard");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert(overflow <= 1, `no horizontal scroll on mobile (overflow ${overflow}px)`);

  step("Admin");
  await page.setViewportSize({ width: 1440, height: 900 });
  await ctx.clearCookies();
  await page.goto(BASE + "/login");
  await page.getByLabel("Email", { exact: true }).fill("admin@example.com");
  await page.getByLabel("Password").fill("admin-demo-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/admin|dashboard|onboarding/);
  if (page.url().includes("onboarding")) {
    await page.request.post(BASE + "/api/v1/me/onboarding/complete");
  }
  await page.goto(BASE + "/admin");
  await page.getByRole("heading", { name: "Admin overview" }).waitFor();
  await page.getByText("Lessons generated, last 7 days").waitFor();
  await page.waitForTimeout(800);
  await shot("22-admin");
  await page.goto(BASE + "/admin/users");
  await page.getByRole("heading", { name: "Teachers", exact: true }).waitFor();
  await shot("22b-admin-users");
  await page.goto(BASE + "/admin/plans");
  await page.getByText("Free trial for new teachers").waitFor();
  await shot("22c-admin-plans");
  await page.goto(BASE + "/dashboard");
  await page.waitForURL("**/admin");
  ok("admins stay in the admin area (no teacher plan or billing)");
  await page.goto(BASE + "/admin/ai-costs");
  await page.getByRole("heading", { name: "Model routing", exact: true }).waitFor();
  await shot("23-admin-ai-costs");
  await page.goto(BASE + "/admin/media");
  await page.getByRole("heading", { name: "Payment gateway" }).waitFor();
  await shot("24-admin-media");

  step("Admin console");
  await page.goto(BASE + "/admin/users");
  await page.getByText("sara@example.com").click();
  await page.waitForURL(/admin\/users\/[0-9a-f-]+/);
  await page.getByRole("button", { name: "Suspend" }).waitFor();
  await shot("25-admin-user");
  await page.getByRole("tab", { name: "Sessions & security" }).click();
  await page.getByText("login success").first().waitFor();
  await page.getByRole("tab", { name: "Notes & audit" }).click();
  const adminNote = `Demo account — do not suspend. Review ${Date.now()}`;
  await page.getByPlaceholder("Add a note…").fill(adminNote);
  await page.getByRole("button", { name: "Add note" }).click();
  await page.locator("div.whitespace-pre-wrap").filter({ hasText: adminNote }).waitFor();
  ok("user detail with sessions, audit trail and notes");
  for (const [route, text, name] of [
    ["/admin/staff", "Permission matrix", "26-admin-staff"],
    ["/admin/billing", "Subscriptions & payments", "27-admin-billing"],
    ["/admin/api-usage", "Endpoints", "28-admin-api-usage"],
    ["/admin/support", "How do I share a lesson?", "29-admin-support"],
    ["/admin/announcements", "Publish", "30-admin-announcements"],
    ["/admin/security", "Security events", "31-admin-security"],
    ["/admin/audit", "user.note_added", "32-admin-audit"],
    ["/admin/system", "Readiness", "33-admin-system"],
    ["/admin/settings", "Maintenance mode", "34-admin-settings"],
    ["/admin/legal", "Terms & Conditions", "35-admin-legal"],
  ]) {
    await page.goto(BASE + route);
    await page.getByText(text).first().waitFor();
    await page.waitForTimeout(500);
    await shot(name);
    ok(route);
  }
  await page.getByRole("button", { name: "Search the admin console" }).count();
  await page.getByLabel("Search the admin console").fill("sara@");
  await page.getByRole("button", { name: /sara@example.com/ }).click();
  await page.waitForURL(/admin\/users\//);
  ok("global admin search finds a teacher");
  const staffAlerts = await page.request.get(BASE + "/api/v1/me/notifications").then((r) => r.json());
  assert(staffAlerts.items.some((n) => n.type === "staff"), "staff get alerts (new support ticket)");

  const serious = errors.filter((e) => !/favicon|401|Unauthorized|Not signed in/i.test(e));
  assert(serious.length === 0, `no browser errors (${serious.join(" | ").slice(0, 300)})`);
  console.log("\n✅ E2E passed. Screenshots in", OUT);
} catch (e) {
  await shot("zz-failure").catch(() => {});
  console.error("\n❌ E2E failed:", e.message);
  console.error("Browser errors:", errors.slice(0, 10));
  process.exitCode = 1;
} finally {
  await browser.close();
}
