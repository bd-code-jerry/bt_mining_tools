import test from "node:test";
import assert from "node:assert/strict";

import { authApi } from "../frontend/js/features/auth/api.js";
import { renderLoginPage, renderRegisterPage } from "../frontend/js/features/auth/page.js";

function fakeContainer(values = {}) {
  let html = "";
  const listeners = {};
  const form = {
    values,
    addEventListener(type, handler) { listeners[type] = handler; },
    submit() { return listeners.submit?.({ preventDefault() {} }); },
  };
  const error = { textContent: "" };
  const submit = { disabled: false };
  const elements = new Map([
    ["[data-login-form]", form],
    ["[data-register-form]", form],
    ["[data-error]", error],
    ["[data-submit]", submit],
  ]);
  return {
    get innerHTML() { return html; },
    set innerHTML(value) { html = value; },
    querySelector(selector) { return elements.get(selector) || null; },
    form,
    error,
    submitButton: submit,
  };
}

function withFormData(callback) {
  const original = globalThis.FormData;
  globalThis.FormData = class {
    constructor(form) { this.values = form.values; }
    entries() { return Object.entries(this.values); }
  };
  return Promise.resolve().then(callback).finally(() => { globalThis.FormData = original; });
}

test("sign-in accepts username or email and shows theme control", async () => {
  const original = authApi.login;
  let submitted;
  let signedIn;
  authApi.login = async (body) => {
    submitted = body;
    return { user: { id: 5, role: "member" } };
  };
  try {
    const container = fakeContainer({ identifier: "person@example.com", password: "password" });
    renderLoginPage(container, { onSignedIn(user) { signedIn = user; } });
    assert.match(container.innerHTML, /Username or email/);
    assert.match(container.innerHTML, /data-theme-select/);
    await withFormData(() => container.form.submit());
    assert.deepEqual(submitted, { identifier: "person@example.com", password: "password" });
    assert.equal(signedIn.role, "member");
  } finally {
    authApi.login = original;
  }
});

test("registration requires email and shows pending approval without signing in", async () => {
  const configOriginal = authApi.getRegistrationConfig;
  const registerOriginal = authApi.register;
  let submitted;
  let signedIn = false;
  const originalDocument = globalThis.document;
  globalThis.document = { documentElement: { dataset: { theme: "sand" } } };
  authApi.getRegistrationConfig = async () => ({ registration_code_required: false, registration_enabled: true });
  authApi.register = async (body) => {
    submitted = body;
    return { status: "pending", message: "waiting for admin approval" };
  };
  try {
    const container = fakeContainer({
      username: "person",
      email: "person@example.com",
      password: "password",
      confirmPassword: "password",
      registrationCode: "",
    });
    await renderRegisterPage(container, { onSignedIn() { signedIn = true; } });
    assert.match(container.innerHTML, /type="email"/);
    assert.match(container.innerHTML, /name="email"[^>]*required/);
    assert.match(container.innerHTML, /data-theme-select/);
    await withFormData(() => container.form.submit());
    assert.equal(submitted.email, "person@example.com");
    assert.match(container.innerHTML, /waiting for admin approval/i);
    assert.match(container.innerHTML, /value="sand" selected/);
    assert.equal(signedIn, false);
  } finally {
    authApi.getRegistrationConfig = configOriginal;
    authApi.register = registerOriginal;
    globalThis.document = originalDocument;
  }
});

test("closed registration explains the status and duplicate identifiers show a clear error", async () => {
  const configOriginal = authApi.getRegistrationConfig;
  const registerOriginal = authApi.register;
  authApi.getRegistrationConfig = async () => ({ registration_code_required: false, registration_enabled: false });
  try {
    const closed = fakeContainer();
    await renderRegisterPage(closed, { onSignedIn() {} });
    assert.match(closed.innerHTML, /registration is closed/i);
    assert.doesNotMatch(closed.innerHTML, /data-register-form/);

    authApi.getRegistrationConfig = async () => ({ registration_code_required: false, registration_enabled: true });
    authApi.register = async () => { throw new Error("That username or email address is already in use."); };
    const duplicate = fakeContainer({
      username: "person",
      email: "person@example.com",
      password: "password",
      confirmPassword: "password",
      registrationCode: "",
    });
    await renderRegisterPage(duplicate, { onSignedIn() {} });
    await withFormData(() => duplicate.form.submit());
    assert.match(duplicate.error.textContent, /username or email address is already in use/i);
  } finally {
    authApi.getRegistrationConfig = configOriginal;
    authApi.register = registerOriginal;
  }
});
