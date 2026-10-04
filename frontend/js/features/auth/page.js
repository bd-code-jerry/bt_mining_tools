import { authApi } from "./api.js";
import { themeToggleHtml } from "../../shared/components/themeToggle.js";

function authLayout(title, intro, form, switchText) {
  return `
    <div class="auth-page">
      ${themeToggleHtml("theme-toggle-auth")}
      <section class="auth-brand-panel">
        <div class="auth-brand">BD</div>
        <div class="auth-brand-copy">
          <h1>Team balance dashboard</h1>
          <p>Manage account access and keep team balance history in one place.</p>
        </div>
        <div>API keys balances</div>
      </section>
      <section class="auth-form-wrap">
        <div class="auth-card card">
          <h2>${title}</h2>
          <p class="intro">${intro}</p>
          ${form}
          <p class="auth-switch">${switchText}</p>
        </div>
      </section>
    </div>
  `;
}

export function renderLoginPage(container, { onSignedIn }) {
  container.innerHTML = authLayout(
    "Sign in",
    "Use your BD team account.",
    `
      <form class="auth-form" data-login-form>
        <div class="field">
          <label for="identifier">Username or email</label>
          <input class="input" id="identifier" name="identifier" autocomplete="username" required />
        </div>
        <div class="field">
          <label for="password">Password</label>
          <input class="input" id="password" name="password" type="password" autocomplete="current-password" required />
        </div>
        <div class="error-text" data-error></div>
        <button class="btn btn-primary" type="submit" data-submit>Sign in</button>
      </form>
    `,
    'Need an account? <a href="#/register">Register</a>',
  );

  const form = container.querySelector("[data-login-form]");
  const error = container.querySelector("[data-error]");
  const submit = container.querySelector("[data-submit]");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    submit.disabled = true;
    try {
      const result = await authApi.login(Object.fromEntries(new FormData(form).entries()));
      onSignedIn(result.user);
    } catch (problem) {
      error.textContent = problem.message;
    } finally {
      submit.disabled = false;
    }
  });
}

function closedRegistrationHtml() {
  return authLayout(
    "Registration closed",
    "New account registration is currently disabled by the administrator.",
    `<div class="error-text">Registration is closed. Contact the dashboard administrator for access.</div>`,
    'Already have an account? <a href="#/login">Sign in</a>',
  );
}

function pendingRegistrationHtml() {
  return authLayout(
    "Request received",
    "Your account is waiting for admin approval. You can sign in after an administrator approves it.",
    `<div class="pending-notice" role="status">Your account request is pending approval.</div>`,
    'Return to <a href="#/login">sign in</a>',
  );
}

export async function renderRegisterPage(container, { onSignedIn }) {
  let config = { registration_code_required: false, registration_enabled: true };
  try {
    config = { ...config, ...(await authApi.getRegistrationConfig()) };
  } catch (_) {
    // The server remains authoritative if registration settings cannot be read.
  }

  if (config.registration_enabled === false) {
    container.innerHTML = closedRegistrationHtml();
    return;
  }

  container.innerHTML = authLayout(
    "Register",
    "Create your BD dashboard account. New accounts wait for admin approval.",
    `
      <form class="auth-form" data-register-form>
        <div class="field">
          <label for="username">Username</label>
          <input class="input" id="username" name="username" autocomplete="username" minlength="3" maxlength="32" required />
          <div class="help">Letters, numbers, dot, underscore, and hyphen.</div>
        </div>
        <div class="field">
          <label for="email">Email</label>
          <input class="input" id="email" name="email" type="email" autocomplete="email" required />
        </div>
        <div class="field">
          <label for="password">Password</label>
          <input class="input" id="password" name="password" type="password" autocomplete="new-password" minlength="8" required />
        </div>
        <div class="field">
          <label for="confirmPassword">Confirm password</label>
          <input class="input" id="confirmPassword" name="confirmPassword" type="password" autocomplete="new-password" minlength="8" required />
        </div>
        <div class="field">
          <label for="registrationCode">Team registration code ${config.registration_code_required ? "" : "(optional)"}</label>
          <input class="input" id="registrationCode" name="registrationCode" type="password" ${config.registration_code_required ? "required" : ""} />
          <div class="help">${config.registration_code_required ? "Ask the dashboard owner for this code." : "The server does not currently require a registration code."}</div>
        </div>
        <div class="error-text" data-error></div>
        <button class="btn btn-primary" type="submit" data-submit>Create account</button>
      </form>
    `,
    'Already registered? <a href="#/login">Sign in</a>',
  );

  const form = container.querySelector("[data-register-form]");
  const error = container.querySelector("[data-error]");
  const submit = container.querySelector("[data-submit]");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    const data = Object.fromEntries(new FormData(form).entries());
    if (data.password !== data.confirmPassword) {
      error.textContent = "Passwords do not match.";
      return;
    }
    submit.disabled = true;
    try {
      const result = await authApi.register({
        username: data.username,
        email: data.email,
        password: data.password,
        registration_code: data.registrationCode || null,
      });
      if (result.status === "pending") {
        container.innerHTML = pendingRegistrationHtml();
        return;
      }
      onSignedIn(result.user);
    } catch (problem) {
      error.textContent = problem.message;
    } finally {
      submit.disabled = false;
    }
  });
}
