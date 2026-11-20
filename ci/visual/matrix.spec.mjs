import { expect, test } from '@playwright/test';
import { palettes } from '../../dist/js/palette.js';

const names =
  process.env.NOVA_VISUAL_SCOPE === 'full' ? palettes.map(([key]) => key) : ['default', 'teal'];
for (const palette of names) {
  for (const density of ['standard', 'compact']) {
    for (const mode of ['light', 'dark']) {
      const profile = [palette, density, mode].join('-');
      test(profile, async ({ page }) => {
        const failed = [];
        page.on('response', (response) => {
          if (response.status() >= 400) failed.push(response.url());
        });
        for (const [name, selector] of [
          ['login', '#login-form'],
          ['list', '#result_list'],
          ['error', '.errornote'],
        ]) {
          await page.goto('/case/' + profile + '/' + (name === 'error' ? 'form' : name) + '/');
          if (name === 'error') {
            await page.locator('#id_name').fill('');
            await page.locator('input[name="_save"]').click();
            await page.evaluate(() => window.scrollTo(0, 0));
          }
          await expect(page.locator(selector)).toBeVisible();
          await expect(page.locator('body')).toHaveClass(
            new RegExp('nova-palette-' + palette + '\\b'),
          );
          await expect(page.locator('body')).toHaveClass(new RegExp('nova-mode-' + mode));
          expect(await page.locator('link[href$="enterprise-compact.css"]').count()).toBe(
            density === 'compact' ? 1 : 0,
          );
          await page.mouse.move(0, 0);
          await page.evaluate(async () => {
            await document.fonts.ready;
            await Promise.all(
              Array.from(document.images, async (image) => {
                image.loading = 'eager';
                await image.decode();
              }),
            );
          });
          await expect(page).toHaveScreenshot(profile + '-' + name + '.png');
        }
        expect(failed).toEqual([]);
      });
    }
  }
}
