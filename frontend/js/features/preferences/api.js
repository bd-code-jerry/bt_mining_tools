import { request } from "../../shared/api/client.js";

export const preferencesApi = {
  updateTimezone: (timezone) => request("/api/preferences/timezone", {
    method: "PATCH",
    body: JSON.stringify({ timezone }),
  }),
};
