import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { sidebarHtml } from "../frontend/js/shared/components/sidebar.js";
import { themeToggleHtml } from "../frontend/js/shared/components/themeToggle.js";

const member = { username: '<member>', role: 'member', capabilities: ['expenses:read', 'balances:read', 'total_balances:read'] };

test('67 API keys is a collapsed group after Overview and Used, with capability gated children', () => {
  const html = sidebarHtml('overview', member);
  assert.match(html, /Overview/);
  assert.match(html, /Used/);
  assert.match(html, /<details class="nav-group"[^>]*>/);
  assert.doesNotMatch(html, /<details[^>]* open/);
  assert.match(html, /<summary[^>]*>[\s\S]*?67 API keys[\s\S]*?<\/summary>/);
  assert.doesNotMatch(html, /href="#\/67/);
  assert.ok(html.indexOf('Overview') < html.indexOf('Used'));
  assert.ok(html.indexOf('Used') < html.indexOf('67 API keys'));
  assert.doesNotMatch(html, /href="#\/users"/);
  assert.match(html, /&lt;member&gt;/);
  const restricted = sidebarHtml('overview', { capabilities: ['expenses:read'] });
  assert.doesNotMatch(restricted, /67 API keys|api-balances|total-balances/);
});

for (const route of ['api-balances', 'total-balances']) {
  test(`${route} opens the group and marks only the selected child current`, () => {
    const html = sidebarHtml(route, member);
    assert.match(html, /<details[^>]* open/);
    assert.match(html, new RegExp(`href="#/${route}"[^>]*aria-current="page"`));
    assert.equal((html.match(/aria-current="page"/g) || []).length, 1);
  });
}

test('appearance control is labeled, contains every preset and restores after auth rerenders', () => {
  const original = globalThis.document;
  globalThis.document = { documentElement: { dataset: { theme: 'forest' } } };
  try {
    const html = themeToggleHtml('theme-toggle-auth');
    assert.match(html, /<label[^>]*>[\s\S]*?Appearance/);
    assert.match(html, /<select[^>]*data-theme-select/);
    assert.match(html, /value="forest" selected/);
    for (const preset of ['light','dark','sand','forest','midnight']) assert.match(html, new RegExp(`value="${preset}"`));
    assert.doesNotMatch(html, /data-theme-toggle/);
  } finally { globalThis.document = original; }
});

test('early startup restores each preset and falls back when storage is blocked or invalid', async () => {
  const html = await readFile(new URL('../frontend/index.html', import.meta.url), 'utf8');
  const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  for (const [saved, theme, scheme] of [['light','light','light'],['dark','dark','dark'],['sand','sand','light'],['forest','forest','dark'],['midnight','midnight','dark'],['invalid','light','light'],['constructor','light','light'],['__proto__','light','light'],[null,'light','light']]) {
    const document = { documentElement: { dataset: {}, style: {} } };
    vm.runInNewContext(source, { document, localStorage: { getItem() { return saved; } } });
    assert.equal(document.documentElement.dataset.theme, theme);
    assert.equal(document.documentElement.style.colorScheme, scheme);
  }
  const document = { documentElement: { dataset: {}, style: {} } };
  vm.runInNewContext(source, { document, localStorage: { getItem() { throw Error('blocked'); } } });
  assert.equal(document.documentElement.dataset.theme, 'light');
  assert.equal(document.documentElement.style.colorScheme, 'light');
  assert.match(html, /\/static\/v1\.3\.1\/styles\/expenses.css/);
});

test('signed-in bootstrap defaults to Overview and preserves explicit protected links', async () => {
  const source = (await readFile(new URL('../frontend/js/app.js', import.meta.url), 'utf8')).replace(/^import .*;$/gm, '');
  for (const initialHash of ['', '#/api-balances', '#/users', '#/login']) {
    const location = { hash: initialHash };
    const document = { getElementById() { return { innerHTML: '', querySelector() { return null; } }; } };
    const rendered = [];
    const window = { location, addEventListener() {} };
    const context = { document, window, authApi: { async me() { return { user: member }; } }, initializeTheme() {}, bindThemeToggleEvents() {}, syncThemeButtons() {}, sidebarHtml() { return ''; }, renderTimezoneSelector() {}, showToast() {}, parseRouteHash(hash, fallback) { return hash.replace(/^#\//, '') || fallback; }, navigateTo(route) { location.hash = `#/${route}`; return false; }, resolvePage(route) { return { route, async render() { rendered.push(route); } }; }, pageRegistry: [{ route: 'overview' }, { route: 'used' }] };
    vm.runInNewContext(source, context);
    await new Promise(resolve => setImmediate(resolve));
    const expected = initialHash && initialHash !== '#/login' ? initialHash.slice(2) : 'overview';
    assert.equal(location.hash, `#/${expected}`);
    assert.deepEqual(rendered, [expected]);
  }
});


test('successful sign-in lands on Overview even after an old protected route', async () => {
  const source = (await readFile(new URL('../frontend/js/app.js', import.meta.url), 'utf8')).replace(/^import .*;$/gm, '');
  const location = { hash: '#/api-balances' };
  let onSignedIn;
  const rendered = [];
  const context = {
    document: { getElementById() { return { innerHTML: '', querySelector() { return null; } }; } },
    window: { location, addEventListener() {} },
    authApi: { async me() { throw Object.assign(new Error('Unauthenticated'), { status: 401 }); } },
    initializeTheme() {}, bindThemeToggleEvents() {}, syncThemeButtons() {}, sidebarHtml() { return ''; }, renderTimezoneSelector() {}, showToast() {},
    renderLoginPage(container, options) { onSignedIn = options.onSignedIn; },
    parseRouteHash(hash, fallback) { return hash.replace(/^#\//, '') || fallback; },
    navigateTo(route) { location.hash = `#/${route}`; return false; },
    resolvePage(route) { return { route, async render() { rendered.push(route); } }; }, pageRegistry: [{ route: 'overview' }, { route: 'used' }],
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(location.hash, '#/login');
  onSignedIn(member);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(location.hash, '#/overview');
  assert.deepEqual(rendered, ['overview']);
});
