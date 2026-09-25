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
  await shot("01-landing");
  await page.goto(BASE + "/pricing");
  await page.getByText("AI Teaching Assistant").first().waitFor();
  await shot("02-pricing");
  ok("marketing pages render");

  step("Sign up");
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto(BASE + "/signup");
  await page.getByLabel("Your name").fill("Amira Hassan");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL("**/onboarding");
  ok("redirected to onboarding");

  step("Onboarding: basics");
  await page.getByText("Welcome to your AI Teaching Assistant").waitFor();
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
  await page.getByText("Your assistant is ready").waitFor();
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
  ok("assistant answered via SSE");

  step("Other pages render without errors");
  for (const [route, text, name] of [
    ["/dashboard", "Today's classes", "10-dashboard"],
    ["/templates", "Your templates", "11-templates"],
    ["/calendar", "Week plan", "12-calendar"],
    ["/curriculum", "Classes & curriculum", "13-curriculum"],
    ["/teacher-memory", "Teacher memory", "14-memory"],
    ["/lessons", "Lessons & documents", "15-library"],
    ["/whatsapp", "WhatsApp assistant", "16-whatsapp"],
    ["/billing", "Plan & billing", "17-billing"],
    ["/settings", "Settings", "18-settings"],
    ["/tutorials", "Tutorials & help", "18a-tutorials"],
    ["/media", "Media studio", "18b-media"],
  ]) {
    await page.goto(BASE + route);
    await page.getByText(text).first().waitFor();
    await page.waitForTimeout(700);
    await shot(name);
    ok(`${route}`);
  }

  step("Demo teacher: dashboard with a timetable");
  await ctx.clearCookies();
  await page.goto(BASE + "/login");
  await page.getByLabel("Email").fill("sara@example.com");
  await page.getByLabel("Password").fill("teacher-demo-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
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
  await page.getByLabel("Email").fill("admin@example.com");
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
  await page.getByRole("heading", { name: "Users" }).waitFor();
  await shot("22b-admin-users");
  await page.goto(BASE + "/admin/ai-costs");
  await page.getByRole("heading", { name: "Model routing", exact: true }).waitFor();
  await shot("23-admin-ai-costs");
  await page.goto(BASE + "/admin/media");
  await page.getByRole("heading", { name: "Payment gateway" }).waitFor();
  await shot("24-admin-media");

  const serious = errors.filter((e) => !/hydrat|favicon|401|Unauthorized|Not signed in/i.test(e));
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
