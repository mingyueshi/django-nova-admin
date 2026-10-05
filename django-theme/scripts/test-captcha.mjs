import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { JSDOM } = require('jsdom');
const script = readFileSync(new URL('../src/nova_admin/static/nova_admin/captcha.js', import.meta.url), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; }
function setup({ invalid = false, disabled = false, imageError = false } = {}) {
  const dom = new JSDOM(`<form><input name="csrfmiddlewaretoken" value="csrf-test"><div data-nova-captcha data-refresh-url="/refresh/" data-loading-message="Loading" data-success-message="Ready" data-error-message="Reload page" data-image-error-message="Image failed"><img data-captcha-image src="/old.png"><a data-captcha-audio href="/old.wav">Listen</a><input type="hidden" value="signed-old"><input type="text" value="old answer" ${invalid ? 'aria-invalid="true"' : ''}><button type="button" data-captcha-refresh hidden>New image</button><p data-captcha-status role="status"></p></div><input type="submit" ${disabled ? 'disabled' : ''}></form>`, {runScripts:'outside-only', url:'https://test.invalid/login/'});
  const w = dom.window, d = w.document;
  Object.defineProperty(w.HTMLImageElement.prototype, 'complete', { get: () => false });
  const preloads = [];
  w.Image = class { set src(value) { preloads.push(value); queueMicrotask(() => imageError ? this.onerror() : this.onload()); } };
  const calls = [];
  const pending = deferred();
  w.fetch = (...args) => { calls.push(args); return pending.promise; };
  w.eval(script);
  return { dom, w, d, calls, preloads, pending, button:d.querySelector('button'), answer:d.querySelector('[type="text"]'), token:d.querySelector('[type="hidden"]'), submit:d.querySelector('[type="submit"]'), image:d.querySelector('img'), status:d.querySelector('[role="status"]') };
}
const ok = (key='signed-new') => ({ ok:true, json:async () => ({key, image_url:'/new.png', audio_url:'/new.wav'}) });
let count = 0;
async function test(label, options, check) { const x=setup(options); try { await check(x); count++; console.log('PASS',label); } finally {x.dom.window.close();} }
await test('Refresh performs CSRF POST; replaces image, key and audio together; focuses answer', {}, async x => {
  assert.equal(x.button.hidden,false); x.button.click();
  assert.equal(x.calls[0][1].method,'POST'); assert.equal(x.calls[0][1].credentials,'same-origin'); assert.equal(x.calls[0][1].headers['X-CSRFToken'],'csrf-test'); assert.equal(String(x.calls[0][1].body),'key=signed-old');
  x.pending.resolve(ok()); await settle();
  assert.equal(x.token.value,'signed-new'); assert.equal(x.answer.value,''); assert.equal(x.image.getAttribute('src'),'https://test.invalid/new.png'); assert.equal(x.d.querySelector('a').getAttribute('href'),'https://test.invalid/new.wav'); assert.equal(x.status.textContent,'Ready'); assert.equal(x.submit.disabled,false); assert.equal(x.d.activeElement,x.answer);
});
await test('Repeated clicks issue one request; submit blocked while request pending', {}, async x => {
  x.button.click(); x.button.click(); x.button.dispatchEvent(new x.w.Event('click'));
  assert.equal(x.calls.length,1); assert.equal(x.submit.disabled,true); assert.equal(x.answer.readOnly,true);
  const submit = new x.w.Event('submit',{cancelable:true}); x.d.querySelector('form').dispatchEvent(submit); assert.equal(submit.defaultPrevented,true);
  x.pending.resolve(ok()); await settle();
});
await test('HTTP/CSRF refresh failure remains blocked with actionable error', {}, async x => {
  x.button.click(); x.pending.resolve({ok:false}); await settle(); assert.equal(x.status.textContent,'Reload page'); assert.equal(x.submit.disabled,true); assert.equal(x.button.disabled,false); assert.equal(x.d.activeElement,x.button);
});
await test('Image load failure retains replacement token for another refresh, keeps submit blocked', {imageError:true}, async x => {
  x.button.click(); x.pending.resolve(ok()); await settle(); assert.equal(x.token.value,'signed-new'); assert.equal(x.image.getAttribute('src'),'/old.png'); assert.equal(x.submit.disabled,true); assert.equal(x.button.disabled,false);
});
await test('Page navigation invalidates late asynchronous response', {}, async x => {
  x.button.click(); x.w.dispatchEvent(new x.w.Event('pagehide')); x.pending.resolve(ok('stale-token')); await settle(); assert.equal(x.token.value,'signed-old'); assert.equal(x.image.getAttribute('src'),'/old.png');
});
await test('Existing disabled submit state is preserved after successful refresh', {disabled:true}, async x => {
  x.button.click(); x.pending.resolve(ok()); await settle(); assert.equal(x.submit.disabled,true);
});
await test('CAPTCHA validation error focuses labelled answer for correction', {invalid:true}, async x => {assert.equal(x.d.activeElement,x.answer);});
await test('Initial image error blocks submission while leaving keyboard refresh available', {}, async x => {
  x.image.dispatchEvent(new x.w.Event('error')); assert.equal(x.submit.disabled,true); assert.equal(x.status.textContent,'Image failed'); assert.equal(x.button.disabled,false);
});
await test('External refresh destination is rejected before fetch', {}, async x => {
  x.d.querySelector('[data-nova-captcha]').dataset.refreshUrl='https://third-party.invalid/refresh/';
  x.button.click(); await settle(); assert.equal(x.calls.length,0); assert.equal(x.preloads.length,0); assert.equal(x.submit.disabled,true); assert.equal(x.status.textContent,'Reload page');
});
await test('External response image URL is rejected before preload or asset assignment', {}, async x => {
  x.button.click(); x.pending.resolve({ok:true,json:async () => ({key:'signed-new',image_url:'//third-party.invalid/image.png',audio_url:'/new.wav'})}); await settle();
  assert.equal(x.preloads.length,0); assert.equal(x.image.getAttribute('src'),'/old.png'); assert.equal(x.d.querySelector('a').getAttribute('href'),'/old.wav'); assert.equal(x.submit.disabled,true); assert.equal(x.status.textContent,'Reload page');
});
await test('Non-HTTP response audio URL rejects the entire response before preload or assignment', {}, async x => {
  x.button.click(); x.pending.resolve({ok:true,json:async () => ({key:'signed-new',image_url:'/new.png',audio_url:'javascript:alert(1)'})}); await settle();
  assert.equal(x.preloads.length,0); assert.equal(x.image.getAttribute('src'),'/old.png'); assert.equal(x.d.querySelector('a').getAttribute('href'),'/old.wav'); assert.equal(x.submit.disabled,true); assert.equal(x.status.textContent,'Reload page');
});
console.log(`TOTAL ${count} CAPTCHA enhancement tests passed`);
