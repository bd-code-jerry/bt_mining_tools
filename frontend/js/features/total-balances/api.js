import { request } from "../../shared/api/client.js";

export const totalBalancesApi = {
  getSummary: () => request("/api/total-balances/summary"),
};
