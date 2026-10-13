import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const css = await readFile(new URL('../frontend/styles/base.css', import.meta.url), 'utf8');
function tokensFor(theme) {
  const tokens = {};
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!selector.trim().split(',').some(part => part.trim() === ':root' || part.trim() === `html[data-theme="${theme}"]`)) continue;
    for (const [, name, value] of body.matchAll(/--([\w-]+):\s*([^;]+);/g)) tokens[name] = value.trim();
  }
  return tokens;
}
function luminance(color) {
  assert.match(color, /^#[a-f\d]{6}$/i);
  return [1,3,5].map(i => parseInt(color.slice(i,i+2),16)/255).map(v => v <= .04045 ? v/12.92 : ((v+.055)/1.055)**2.4).reduce((total,v,i) => total + v*[.2126,.7152,.0722][i],0);
}
function contrast(a,b) { const values = [luminance(a),luminance(b)].sort((a,b) => b-a); return (values[0]+.05)/(values[1]+.05); }
for (const theme of ['light','dark','sand','forest','midnight']) {
  test(`${theme} has readable shared text, status, action and sidebar tokens`, () => {
    const tokens = tokensFor(theme);
    assert.match(css, new RegExp(`html\\[data-theme="${theme}"\\]`));
    for (const [fg,bg] of [['text-900','surface'],['text-700','surface-control'],['text-500','page-bg'],['blue-700','blue-100'],['green-700','green-100'],['red-600','surface-danger-soft'],['sidebar-text','sidebar-bg'],['sidebar-muted','sidebar-bg']]) {
      assert.ok(contrast(tokens[fg],tokens[bg]) >= 4.5, `${theme}: ${fg} on ${bg}`);
    }
    assert.ok(contrast('#ffffff', tokens['blue-600']) >= 4.5, `${theme}: primary button`);
    assert.ok(contrast('#ffffff', tokens['danger-button-bg']) >= 4.5, `${theme}: danger button`);
  });
}
