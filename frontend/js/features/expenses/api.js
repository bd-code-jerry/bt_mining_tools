import { request } from '../../shared/api/client.js';
function get(path, params = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== '' && value != null));
  return request(`/api/expenses/${path}${query.size ? `?${query}` : ''}`);
}
const write = (path, method, body) => request(`/api/expenses/${path}`, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
export const ledgerApi = {
  getParticipants: () => get('participants'), getCategories: () => get('categories'), getSummary: () => get('summary'),
  getPeople: (params) => get('people', params), getCosts: (params) => get('costs', params), getTransfers: (params) => get('transfers', params),
  createCategory: (body) => write('categories', 'POST', body), updateCategory: (id, body) => write(`categories/${Number(id)}`, 'PATCH', body),
  createCost: (body) => write('costs', 'POST', body), updateCost: (id, body) => write(`costs/${Number(id)}`, 'PUT', body), deleteCost: (id) => write(`costs/${Number(id)}`, 'DELETE'),
  createTransfer: (body) => write('transfers', 'POST', body), updateTransfer: (id, body) => write(`transfers/${Number(id)}`, 'PUT', body), deleteTransfer: (id) => write(`transfers/${Number(id)}`, 'DELETE'),
};
