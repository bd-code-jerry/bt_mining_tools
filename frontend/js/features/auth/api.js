import { request } from "../../shared/api/client.js";

export const authApi = {
  getRegistrationConfig: () => request("/api/auth/registration-config"),
  me: () => request("/api/auth/me"),
  register: (body) => request("/api/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body) => request("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request("/api/auth/logout", { method: "POST" }),
};
