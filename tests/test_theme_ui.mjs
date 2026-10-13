import test from "node:test";
import assert from "node:assert/strict";

import { authApi } from "../frontend/js/features/auth/api.js";
import { sidebarHtml } from "../frontend/js/shared/components/sidebar.js";
import { renderLoginPage, renderRegisterPage } from "../frontend/js/features/auth/page.js";

function fakeAuthContainer() {
  let html = "";
  const form = { addEventListener() {} };
  const field = {};
  return {
    get innerHTML() { return html; },
    set innerHTML(value) { html = value; },
    querySelector(selector) {
      if (selector === "[data-login-form]" || selector === "[data-register-form]") return form;
      if (selector === "[data-error]" || selector === "[data-submit]") return field;
      throw new Error(`Unexpected selector: ${selector}`);
    },
  };
}

test("signed-in navigation includes an appearance selector", () => {
  const html = sidebarHtml("dashboard", { username: "tester" });
  assert.match(html, /data-theme-select/);
});

test("sign-in page includes an appearance selector", () => {
  const container = fakeAuthContainer();
  renderLoginPage(container, { onSignedIn() {} });
  assert.match(container.innerHTML, /data-theme-select/);
});

test("registration page includes an appearance selector", async () => {
  const original = authApi.getRegistrationConfig;
  authApi.getRegistrationConfig = async () => ({ registration_code_required: false, registration_enabled: true });
  try {
    const container = fakeAuthContainer();
    await renderRegisterPage(container, { onSignedIn() {} });
    assert.match(container.innerHTML, /data-theme-select/);
  } finally {
    authApi.getRegistrationConfig = original;
  }
});

test("BD branding is rendered on sign-in, registration, and sidebar screens", async () => {
  const login = fakeAuthContainer();
  renderLoginPage(login, { onSignedIn() {} });
  assert.match(login.innerHTML, /<div class="auth-brand">BD<\/div>/);
  assert.doesNotMatch(login.innerHTML, /RSG/i);

  const original = authApi.getRegistrationConfig;
  authApi.getRegistrationConfig = async () => ({ registration_code_required: false, registration_enabled: true });
  try {
    const register = fakeAuthContainer();
    await renderRegisterPage(register, { onSignedIn() {} });
    assert.match(register.innerHTML, /<div class="auth-brand">BD<\/div>/);
    assert.doesNotMatch(register.innerHTML, /RSG/i);
  } finally {
    authApi.getRegistrationConfig = original;
  }

  const sidebar = sidebarHtml("dashboard", { username: "tester" });
  assert.match(sidebar, /<div class="brand">BD<\/div>/);
  assert.doesNotMatch(sidebar, /RSG/i);
});
