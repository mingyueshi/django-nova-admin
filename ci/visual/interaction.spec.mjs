import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { palettes } from '../../dist/js/palette.js';

test('palette editor validates every preset and exports working scoped overrides', async ({
  page,
}) => {
  test.slow();
  const live = await page.context().newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/editor/palette-editor.html');
  const option = page.locator('#preset');
  await expect(option.locator('option')).toHaveCount(palettes.length);
  for (const [key] of palettes) {
    await option.selectOption(key);
    for (const mode of ['light', 'dark']) {
      await page.locator('[name=mode][value=' + mode + ']').check();
      await expect(page.locator('#checks tr')).toHaveCount(10);
      expect(await page.locator('#checks').innerText()).not.toContain('NaN');
      const editor = await page
        .locator('#colors input[type=color]')
        .evaluateAll((pickers) =>
          Object.fromEntries(
            pickers.map((picker) => [picker.id.slice('color'.length), picker.value]),
          ),
        );
      await live.goto('/case/' + key + '-standard-' + mode + '/login/');
      const actual = await live.locator('body').evaluate((element, roles) => {
        const style = getComputedStyle(element);
        return Object.fromEntries(
          roles.map((role) => [
            role,
            style
              .getPropertyValue(role)
              .trim()
              .toLowerCase()
              .replace(/^#(.)(.)(.)$/, '#$1$1$2$2$3$3'),
          ]),
        );
      }, Object.keys(editor));
      expect(editor, key + '/' + mode).toEqual(actual);
      await expect(page.locator('#settings-code')).toHaveValue(
        'NOVA_ADMIN_DEFAULT_PALETTE = "' + key + '"',
      );
    }
  }
  await page.locator('#full-export').check();
  await expect(page.locator('#css-code')).toHaveValue(/--button-hover-bg:/);
  await page.locator('#full-export').uncheck();
  await option.selectOption('teal');
  await page.locator('[value=light]').check();
  const body = page.getByRole('textbox', { name: '正文 HEX', exact: true });
  const panel = page.getByRole('textbox', { name: '面板 HEX' });
  await body.fill('invalid');
  await expect(body).toHaveAttribute('aria-invalid', 'true');
  await expect(page.locator('#copy')).toBeDisabled();
  await body.fill(await panel.inputValue());
  await expect(page.locator('#checks tr').first()).toContainText('1.00:1');
  await expect(page.locator('#checks tr').first()).toContainText('未通过');
  await body.fill('#123456');
  await expect(page.locator('#copy')).toBeEnabled();
  await expect(page.frameLocator('#preview').locator('h1')).toHaveCSS('color', 'rgb(18, 52, 86)');
  const css = await page.locator('#css-code').inputValue();
  for (const [profile, scheme, applies] of [
    ['teal-standard-light', 'dark', true],
    ['teal-standard-dark', 'light', false],
    ['standard-auto', 'light', true],
    ['standard-auto', 'dark', false],
    ['high-light', 'light', false],
  ]) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto('/case/' + profile + '/list/');
    expect(
      await page
        .locator('#nova-admin-palette option')
        .evaluateAll((options) => options.map((item) => item.value).sort()),
    ).toEqual(palettes.map(([name]) => name).sort());
    const before = await page.locator('body').evaluate((el) => getComputedStyle(el).color);
    await page.addStyleTag({ content: css });
    await expect(page.locator('body')).toHaveCSS('color', applies ? 'rgb(18, 52, 86)' : before);
  }
  expect(errors).toEqual([]);
});

async function contrast(locator, foreground = 'color') {
  return locator.evaluate((el, prop) => {
    const luminance = (color) => {
      const channels = color
        .match(/[\d.]+/g)
        .slice(0, 3)
        .map(Number)
        .map((v) => {
          const c = v / 255;
          return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
        });
      return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    };
    // The measured admin controls have opaque solid backgrounds or transparent ancestors.
    let parent = el;
    while (parent && getComputedStyle(parent).backgroundColor === 'rgba(0, 0, 0, 0)')
      parent = parent.parentElement;
    const a = luminance(getComputedStyle(el)[prop]);
    const b = luminance(getComputedStyle(parent).backgroundColor);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  }, foreground);
}

test('high contrast in explicit and system modes, including forced colors', async ({ page }) => {
  for (const [mode, scheme] of [
    ['light', 'dark'],
    ['dark', 'light'],
    ['auto', 'light'],
    ['auto', 'dark'],
  ]) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto('/case/high-' + mode + '/login/');
    const expected =
      (mode === 'auto' ? scheme : mode) === 'dark' ? 'rgb(16, 16, 16)' : 'rgb(255, 255, 255)';
    await expect(page.locator('body')).toHaveCSS('background-color', expected);
    for (const selector of [
      '#login-form label[for=id_username]',
      '#id_username',
      '#login-form [type=submit]',
    ]) {
      expect(await contrast(page.locator(selector)), mode + ' ' + selector).toBeGreaterThanOrEqual(
        7,
      );
    }
    expect(await contrast(page.locator('#id_username'), 'borderTopColor')).toBeGreaterThanOrEqual(
      3,
    );
    await page.goto('/case/high-' + mode + '/form/');
    await page.locator('#id_name').fill('');
    await page.locator('input[name="_save"]').click();
    for (const [selector, minimum] of [
      ['.errornote', 7],
      ['.breadcrumbs a', 7],
      ['.submit-row a.deletelink', 7],
      ['#content h1', 4.5],
    ]) {
      expect(await contrast(page.locator(selector).first()), selector).toBeGreaterThanOrEqual(
        minimum,
      );
    }
  }
  await page.emulateMedia({ forcedColors: 'active' });
  const input = page.locator('#id_name');
  await input.focus();
  await expect(input).toHaveCSS('forced-color-adjust', 'auto');
  expect(await input.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none');
  expect(await contrast(input)).toBeGreaterThanOrEqual(7);
});

test('RTL long labels, keyboard dialog, sticky columns, resize, scrolling and Django sorting', async ({
  page,
}) => {
  await page.goto('/case/rtl/list/');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('script[data-all]')).toHaveAttribute('data-all', '4 عناصر محددة');
  const search = page.locator('[data-nova-command-open]');
  await search.focus();
  await page.keyboard.press('Control+k');
  await expect(page.locator('#nova-command-query')).toBeFocused();
  await expect(page.locator('#nova-command-help')).toContainText('مفاتيح الأسهم');
  await page.keyboard.press('ArrowDown');
  await expect(page.locator('#nova-command-results a:focus')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(search).toBeFocused();
  const header = page.locator('th.column-sku');
  const grip = header.getByRole('separator');
  await grip.focus();
  await expect(grip).toHaveAttribute('aria-description', /مفاتيح الأسهم/);
  const before = Number(await grip.getAttribute('aria-valuenow'));
  await grip.press('ArrowLeft');
  expect(Number(await grip.getAttribute('aria-valuenow'))).toBeGreaterThan(before);
  const widened = Number(await grip.getAttribute('aria-valuenow'));
  await grip.scrollIntoViewIfNeeded();
  const rect = await grip.boundingBox();
  const x = rect.x + rect.width / 2,
    y = rect.y + rect.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x - 24, y);
  await page.mouse.up();
  expect(Number(await grip.getAttribute('aria-valuenow'))).toBeGreaterThan(widened);
  const pin = page.locator('tbody .nova-pinned').first();
  await expect(pin).toHaveCSS('position', 'sticky');
  await expect(pin).toHaveCSS('right', '0px');
  await expect(page.locator('td.field-sku').first()).toHaveCSS('unicode-bidi', 'plaintext');
  await expect(page.locator('.nova-results-scrollbar')).toHaveAttribute('dir', 'rtl');
  await page.locator('.nova-results-scrollbar').press('End');
  expect(await page.locator('.results').evaluate((el) => el.scrollLeft)).toBeLessThan(0);
  const sort = header.locator('a[href*="o="]').first();
  await sort.click();
  await expect(page).toHaveURL(/[?&]o=/);
  await expect(header).toHaveClass(/sorted/);
  await page.locator('.nova-appearance > summary').click();
  await page.selectOption('#nova-admin-contrast', 'high');
  await page.locator('.nova-theme-switcher button').click();
  await expect(page.locator('body')).toHaveClass(/nova-contrast-high/);
  await expect(page).toHaveURL(/[?&]o=/);
});

test('mobile RTL navigation, long labels, messages, and login forms fit the viewport', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/case/rtl/messages/');
  const nav = page.locator('#nova-mobile-nav-toggle');
  await nav.click();
  await expect(nav).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(nav).toBeFocused();
  await expect(nav).toHaveAttribute('aria-expanded', 'false');
  await page.locator('[data-nova-message-toggle]').click();
  await expect(page.locator('[data-nova-message-list]')).toBeHidden();
  const summary = page.locator('.nova-appearance > summary');
  await expect(summary).toContainText('تخصيص المظهر');
  await summary.click();
  await expect(page.locator('#nova-admin-contrast')).toBeVisible();
  for (const route of [
    '',
    '/case/rtl/login/',
    '/case/rtl/form/',
    '/case/rtl/delete/',
    '/case/rtl/dashboard/',
  ]) {
    if (route) await page.goto(route);
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
      route,
    ).toBeLessThanOrEqual(390);
  }
});

const locales = JSON.parse(
  readFileSync(new URL('../../django-theme/tests/locales.json', import.meta.url)),
);
for (const locale of locales) {
  test('localized controls and keyboard instructions: ' + locale.code, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 740 });
    await page.goto('/case/locale-' + locale.code + '/list/');
    await expect(page.locator('html')).toHaveAttribute('dir', locale.dir);
    const summary = page.locator('.nova-appearance > summary');
    await expect(summary).toContainText(locale.appearance);
    // Exercise expansion without shipping artificial copy in a locale.
    await summary.evaluate((element) => {
      element.firstChild.textContent = element.firstChild.textContent.repeat(3);
    });
    expect(
      await summary.evaluate((element) => element.scrollWidth - element.clientWidth),
    ).toBeLessThanOrEqual(1);
    await summary.click();
    const box = await page.locator('.nova-appearance-panel').boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(320);
    await summary.click();
    await expect(page.locator('.nova-column-grip').first()).toHaveAttribute(
      'aria-description',
      new RegExp(locale.resize),
    );
    await page.locator('[data-nova-command-open]').click();
    await expect(page.locator('#nova-command-help')).toContainText(locale.keyboard);
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-nova-command-open]')).toBeFocused();
  });
}

test('RTL actions, column preferences, pagination, print sheet, form sections and charts', async ({
  page,
}) => {
  await page.goto('/case/rtl/list/');
  await page.locator('.action-select').first().check();
  await expect(page.locator('.action-select:checked')).toHaveCount(1);
  await page.locator('.nova-columns > summary').click();
  const sku = page.locator('.nova-columns [name=visible][value=sku]');
  await sku.uncheck();
  await page.locator('.nova-columns [value=save]').click();
  await expect(page.locator('#result_list th.column-sku:visible')).toHaveCount(0);
  const sizes = page.locator('#nova-page-size');
  const other = await sizes.locator('option:not(:checked)').first().getAttribute('value');
  await sizes.selectOption(other);
  await page.locator('button[form=nova-page-size-form]').click();
  await page.waitForURL((url) => url.searchParams.get('_nova_page_size') === other);
  await expect(page.locator('[data-nova-print]')).toBeVisible();
  await page.evaluate(() => {
    window.addEventListener(
      'beforeprint',
      () => {
        const table = document.querySelector('.nova-print-sheet table');
        window.novaPrintedTable = table && {
          rows: table.rows.length,
          direction: getComputedStyle(table).direction,
        };
      },
      { once: true },
    );
  });
  await page.pdf();
  const printed = await page.evaluate(() => window.novaPrintedTable);
  expect(printed?.direction).toBe('rtl');
  expect(printed.rows).toBeGreaterThan(1);
  await page.goto('/case/rtl/form/');
  const field = page.locator('#id_sku');
  await field.fill('SKU-منتج-123');
  await expect(field).toHaveValue('SKU-منتج-123');
  await page.locator('.nova-form-sections a').last().click();
  await expect(page.locator('h2:focus')).toBeVisible();
  await expect(page.locator('.inline-group')).toBeVisible();
  await page.goto('/case/rtl/dashboard/');
  await expect(page.locator('.nova-kpis dt').first()).toBeVisible();
  await expect(page.locator('.nova-category-chart canvas').first()).toBeVisible();
  await expect(page.locator('.nova-category-chart tbody tr').first()).toBeVisible();
  await expect(page.locator('.nova-daily-chart time').first()).toBeVisible();
});

test('RTL Markdown editing and optional verification dialogs at mobile width', async ({ page }) => {
  await page.goto('/case/rtl/login/');
  await page.setViewportSize({ width: 320, height: 740 });
  for (const kind of ['image', 'slider']) {
    await page.goto('/components/' + kind + '/');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    const notes = page.locator('#notes');
    await notes.focus();
    await notes.press('Control+a');
    await page.locator('.nova-md-bold').click();
    await expect(notes).toHaveValue('**منتج SKU-123**');
    const submit = page.locator('#login-form [type=submit]');
    await submit.click();
    const dialog = page.locator('.nova-captcha-dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('h2')).toBeFocused();
    if (kind === 'image') {
      await expect(dialog.locator('.nova-captcha-image')).toBeVisible();
      await dialog.locator('summary').click();
      await expect(dialog.getByText('تعليمات بديلة لتسجيل الدخول')).toBeVisible();
    } else {
      await expect(dialog.locator('nova-slider')).toHaveAttribute('purpose', 'login');
      await expect(dialog.locator('[data-nova-captcha-unavailable]')).toBeVisible();
    }
    const box = await dialog.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(320);
    await page.keyboard.press('Escape');
    await expect(submit).toBeFocused();
  }
});
