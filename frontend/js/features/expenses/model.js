export const EMPTY_FILTERS = { q: '', category_id: '', participant_id: '', period: 'all', start_date: '', end_date: '' };
export function money(cents) { return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format((Number(cents) || 0) / 100); }
export function parseCents(amount) {
  const value = String(amount ?? '').trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) return null;
  const [whole, decimal = ''] = value.split('.');
  const cents = Number(whole) * 100 + Number(decimal.padEnd(2, '0'));
  return Number.isSafeInteger(cents) && cents > 0 ? cents : null;
}
export function allocateCents(amount, ids) {
  const cents = parseCents(amount);
  const sorted = [...new Set(ids.map(Number))].sort((a,b)=>a-b);
  if (!cents || !sorted.length) return null;
  const share = Math.floor(cents / sorted.length), remainder = cents % sorted.length;
  return sorted.map((participant_id, index) => ({participant_id, share_cents: share + (index < remainder ? 1 : 0)}));
}
export function buildReportQuery(filters, includeParticipant = true) {
  const query = { ...filters };
  if (!includeParticipant) delete query.participant_id;
  if (query.period !== 'custom') { delete query.start_date; delete query.end_date; }
  return query;
}
export function todayInTimezone(timezone = 'UTC') {
  try { const parts = new Intl.DateTimeFormat('en-US', {timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()); const values=Object.fromEntries(parts.map(p=>[p.type,p.value])); return `${values.year}-${values.month}-${values.day}`; }
  catch { return new Date().toISOString().slice(0,10); }
}
export function newCostDraft(date) { return {id:null,amount:'',expense_date:date,category_id:'',note:'',participant_ids:[]}; }
export function newTransferDraft(kind,date) { return {id:null,kind,amount:'',transfer_date:date,note:''}; }
export function retryRequestId(draft, payload) {
  const fingerprint=JSON.stringify(payload);
  if (draft.requestFingerprint !== fingerprint) { draft.requestFingerprint=fingerprint; draft.requestId=globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`; }
  return draft.requestId;
}
export function permissions(user) { const caps=new Set(user?.capabilities || []); return {read:caps.has('expenses:read'),write:caps.has('expenses:write'),manage:caps.has('expenses:manage')}; }
