import fs from 'node:fs';
import { chromium } from 'playwright-core';

export function launchBrowser() {
  const candidates = [
    process.env.CHROME,
    chromium.executablePath(),
    ...(process.platform === 'darwin' ? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'] : []),
    ...(process.platform === 'linux' ? ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'] : []),
  ].filter(Boolean);
  const executablePath = process.env.CHROME || candidates.find(path => fs.existsSync(path));
  if (!executablePath || !fs.existsSync(executablePath)) throw new Error('Chrome is unavailable. Set CHROME to its executable or install Playwright Chromium before running browser tests.');
  return chromium.launch({ executablePath });
}
