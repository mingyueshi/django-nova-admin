// Pass this function to playwright-cli run-code on the synthetic login preview.
// Real mouse events and Chromium-emulated touch; never use against an auth service.
async (page) => {
  const results = [];
  const check = (ok, label) => { if (!ok) throw new Error(label); results.push(label); };
  const base = new URL(page.url());
  const preview = new URL('login.html', base).href;
  const vendor = await (await page.request.get(new URL('vendor/nova-slider-captcha/slider.css', base).href)).text();
  const tokens = [...new Set([...vendor.split('\n.nsc {')[0].matchAll(/(--nsc-[\w-]+)\s*:/g)].map(match => match[1]))];
  const prepare = async (tab, theme) => {
    await tab.goto(preview);
    await tab.locator('#login-appearance').selectOption(theme);
    await tab.locator('#captcha-provider').selectOption('slider');
    await tab.locator('#captcha-policy').selectOption('always');
    await tab.locator('#demo-username').fill('demo_admin');
    await tab.locator('#demo-password').fill('NovaPreview123');
    await tab.locator('#login-submit').click();
    await tab.waitForFunction(() => document.querySelector('nova-slider-demo')?.state === 'ready');
    await tab.locator('nova-slider-demo').evaluate(el => {
      window.pointerProbe = { verifies: 0, events: [] };
      const original = el.post.bind(el);
      el.post = (action, ...args) => { if (action === 'verify') window.pointerProbe.verifies++; return original(action, ...args); };
      for (const type of ['pointerdown', 'pointerup', 'pointercancel'])
        el.range.addEventListener(type, event => window.pointerProbe.events.push({type, pointerType: event.pointerType}));
    });
  };
  const geometry = tab => tab.locator('nova-slider-demo').evaluate((el, names) => {
    const rect = node => { const b = node.getBoundingClientRect(); return {x: b.x, y: b.y, width: b.width, height: b.height}; };
    const handle = rect(el.querySelector('.nsc-handle')), range = rect(el.range);
    return {handle, range, track: rect(el.querySelector('.nsc-track')), max: el.maxX, x: el.x, target: el.demoPuzzle.x,
      tokens: Object.fromEntries(names.map(name => [name, getComputedStyle(el).getPropertyValue(name).trim()]))};
  }, tokens);
  for (const width of [1280, 390, 320]) for (const theme of ['light', 'dark']) {
    await page.setViewportSize({width, height: 850});
    await prepare(page, theme);
    const tag = `${theme}-${width}`;
    let g = await geometry(page);
    check(tokens.length === 19 && Object.values(g.tokens).every(Boolean), `${tag}: all 19 host variables resolve`);
    check(g.track.height >= 48 && g.range.height >= 44 && g.handle.width === 48 && g.handle.height === 48, `${tag}: visible handle and hit area have usable geometry`);
    check(await page.locator('dialog').evaluate(el => { const b = el.getBoundingClientRect(); return b.x >= 0 && b.right <= innerWidth && el.scrollWidth <= el.clientWidth; }), `${tag}: dialog fits viewport`);
    for (const fraction of [.2, .5, .85]) {
      g = await geometry(page);
      const startX = g.handle.x + g.handle.width / 2, y = g.handle.y + g.handle.height * fraction;
      const endX = g.range.x + g.handle.width / 2 + (g.range.width - g.handle.width) * 80 / g.max;
      check(await page.evaluate(({x,y}) => document.elementFromPoint(x,y)?.classList.contains('nsc-range'), {x: startX,y}), `${tag}: visible handle ${fraction} hits the range`);
      await page.mouse.move(startX,y); await page.mouse.down(); await page.mouse.move(endX,y,{steps: 12});
      const moved = await geometry(page);
      check(moved.x > 20 && moved.handle.x > g.handle.x + 10, `${tag}: real mouse at ${fraction} moves piece and visible handle`);
      if (fraction === .85) await page.screenshot({path: `output/playwright/captcha-pointer-20261030/${tag}-drag.png`});
      await page.mouse.up();
      await page.waitForFunction(() => document.querySelector('nova-slider-demo')?.state === 'ready');
    }
    check(await page.evaluate(() => window.pointerProbe.verifies) === 3, `${tag}: each mouse release verifies once`);
    await page.keyboard.press('Escape');
    check(!await page.locator('dialog').evaluate(el => el.open), `${tag}: cancel closes after dragging`);
    await page.locator('#login-submit').click();
    await page.waitForFunction(() => document.querySelector('nova-slider-demo')?.state === 'ready');
    g = await geometry(page);
    const y = g.handle.y + g.handle.height * .85;
    await page.mouse.move(g.handle.x + g.handle.width / 2,y); await page.mouse.down();
    await page.mouse.move(g.range.x + g.handle.width / 2 + (g.range.width - g.handle.width) * g.target / g.max,y,{steps: 18});
    await page.mouse.up();
    await page.locator('#login-success').waitFor({state:'visible'});
    check(true, `${tag}: lower-handle mouse solve resumes synthetic login`);
  }
  const browser = page.context().browser();
  const touchContext = await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
  try {
    const tab = await touchContext.newPage(); await prepare(tab,'dark');
    const cdp = await touchContext.newCDPSession(tab);
    let g = await geometry(tab);
    const point = (x,y) => ({x,y,id:1,radiusX:2,radiusY:2,force:1});
    let x = g.handle.x + g.handle.width / 2, y = g.handle.y + g.handle.height * .85;
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(x,y)]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point(x+50,y)]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchCancel',touchPoints:[]});
    check(await tab.evaluate(() => window.pointerProbe.verifies) === 0, 'emulated touch cancellation never verifies');
    await tab.locator('.nsc-refresh').click();
    await tab.waitForFunction(() => document.querySelector('nova-slider-demo')?.state === 'ready');
    g = await geometry(tab); x = g.handle.x + g.handle.width / 2; y = g.handle.y + g.handle.height * .85;
    const endX = g.range.x + g.handle.width / 2 + (g.range.width - g.handle.width) * g.target / g.max;
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(x,y)]});
    for (let step=1;step<=16;step++) await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point(x+(endX-x)*step/16,y)]});
    const moved = await geometry(tab);
    check(moved.x > 20 && moved.handle.x > g.handle.x + 10, 'emulated lower-handle touch moves piece and visible handle');
    check(await tab.evaluate(() => window.pointerProbe.events.some(event => event.pointerType==='touch')), 'browser generated touch pointer events');
    await tab.screenshot({path:'output/playwright/captcha-pointer-20261030/touch-dark-390-drag.png'});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await tab.locator('#login-success').waitFor({state:'visible'});
    check(await tab.evaluate(() => window.pointerProbe.verifies) === 1, 'emulated touch verifies once and resumes synthetic login');
  } finally { await touchContext.close(); }
  return {passed: results.length, checks: results, touch:'Chromium emulation; not physical-device acceptance'};
}
