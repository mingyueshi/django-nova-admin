import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: '*.spec.mjs',
  outputDir: '../../output/visual/results',
  snapshotPathTemplate: '{testDir}/baselines/{arg}{ext}',
  updateSnapshots: 'none',
  fullyParallel: true,
  workers: 3,
  use: {
    baseURL: 'http://127.0.0.1:4189',
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 1,
    timezoneId: 'UTC',
    locale: 'en-US',
    reducedMotion: 'reduce',
  },
  expect: {
    toHaveScreenshot: { animations: 'disabled', caret: 'hide', threshold: 0.02, maxDiffPixels: 0 },
  },
  webServer: {
    command: 'python3 -X warn_default_encoding -W error::EncodingWarning:__main__ server.py',
    url: 'http://127.0.0.1:4189/ready/',
    stderr: process.env.NOVA_VISUAL_DEBUG ? 'pipe' : 'ignore',
  },
});
