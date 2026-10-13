import test from 'node:test';
import assert from 'node:assert/strict';
import * as historyUi from '../frontend/js/features/balances/components/history.js';
import { balancesApi } from '../frontend/js/features/balances/api.js';
import { renderApiBalancesPage } from '../frontend/js/features/balances/page.js';
import { workspacesApi } from '../frontend/js/features/workspaces/api.js';
import { usageApi } from '../frontend/js/features/usage/api.js';

const pagination = {page: 2, page_size: 5, total_items: 8, total_pages: 2};
const overview = {
  providers: [{provider_key:'openrouter',display_name:'OpenRouter',unit:'USD'}], latest: null,
  history: [{id:1,entry_date:'2035-01-01',entry_kind:'legacy',values:[]}], pagination,
  topup_history: [{id:9,entry_date:'2035-01-02',entry_kind:'topup',values:[
    {provider_key:'openrouter',display_name:'<OpenRouter>',unit:'USD',balance_before:18,added_balance:2.123456789,left_balance:20.123456789},
    {provider_key:'firecrawl',display_name:'Firecrawl',unit:'credits',balance_before:7,added_balance:3,left_balance:10},
    {provider_key:'parallel',display_name:'Parallel',unit:'USD',balance_before:0,added_balance:0,left_balance:0},
  ]}], topup_pagination: pagination,
};

test('top-up history shows positive additions with units, before/after, and its own pagination', () => {
  assert.equal(typeof historyUi.addedBalanceHistoryTableHtml, 'function');
  const html = historyUi.addedBalanceHistoryTableHtml(overview, {canWrite:true});
  assert.match(html, /Balance before/);
  assert.match(html, /Amount added/);
  assert.match(html, /Balance after/);
  assert.match(html, /2\.123456789/);
  assert.match(html, /credits/);
  assert.match(html, /&lt;OpenRouter&gt;/);
  assert.doesNotMatch(html, /<OpenRouter>|Parallel|data-history-page/);
  assert.match(html, /data-topup-page="2"/);
  assert.match(html, /data-edit-topup="9"/);
  assert.match(html, /data-delete-entry="9"/);
  const readonly = historyUi.addedBalanceHistoryTableHtml(overview);
  assert.doesNotMatch(readonly, /data-edit|data-delete/);
});

test('legacy snapshots show unclassified status and an explicit classification action for editors', () => {
  const html = historyUi.balanceHistoryTableHtml(overview, {canWrite:true});
  assert.match(html, /Legacy \/ unclassified/);
  assert.match(html, /data-classify-entry="1"/);
  assert.doesNotMatch(historyUi.balanceHistoryTableHtml(overview), /data-classify-entry/);
  assert.equal(typeof historyUi.addedBalanceHistoryTableHtml, 'function');
  assert.match(historyUi.addedBalanceHistoryTableHtml({...overview, topup_history:[]}), /No added balance history/);
});

test('overview carries both independent page states and topup correction carries authorized workspace', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {calls.push({url,options});return {ok:true, headers:{get:()=> 'application/json'},json:async()=>({})};};
  try {
    await balancesApi.getOverview(3,10,42,2,20);
    const query = new URL(calls[0].url,'http://localhost').searchParams;
    assert.equal(query.get('topup_page'),'2');
    assert.equal(query.get('topup_page_size'),'20');
    assert.equal(query.get('page'),'3');
    assert.equal(query.get('workspace_id'),'42');
    assert.equal(typeof balancesApi.updateAddedBalance, 'function');
    await balancesApi.updateAddedBalance(9,{entry_date:'2035-01-03',additions:{openrouter:3}},42);
    assert.equal(calls[1].url,'/api/balances/add-balance/9?workspace_id=42');
    assert.equal(calls[1].options.method,'PUT');
  } finally {globalThis.fetch = original;}
});

test('API balances renders two separated histories', async () => {
  const originals = [workspacesApi.getWorkspaces, balancesApi.getOverview,usageApi.getSummary];
  workspacesApi.getWorkspaces = async()=>({workspaces:[{id:1,kind:'shared',display_name:'Shared'}]});
  balancesApi.getOverview = async()=>overview;
  usageApi.getSummary = async()=>({});
  const container = {innerHTML:'',querySelector:()=>null,querySelectorAll:()=>[]};
  try {
    await renderApiBalancesPage(container,{user:{role:'member',capabilities:['balances:read']}});
    assert.match(container.innerHTML, /Added Balance History/);
    assert.match(container.innerHTML, /Balance History/);
    assert.match(container.innerHTML, /data-topup-page/);
    assert.match(container.innerHTML, /data-history-page/);
  } finally {[workspacesApi.getWorkspaces,balancesApi.getOverview,usageApi.getSummary] = originals;}
});

test('editing an imported snapshot with a partial provider catalog opens a usable editor', async () => {
  const originals = [workspacesApi.getWorkspaces, balancesApi.getOverview, usageApi.getSummary, balancesApi.getHistoryEntry, globalThis.document];
  const partial = {id:1,entry_date:'2035-01-01',entry_kind:'legacy',values:[{provider_key:'openrouter',display_name:'OpenRouter',unit:'USD',total_balance:20,used_balance:2,left_balance:18}]};
  const data = {...overview, providers:[...overview.providers,{provider_key:'parallel',display_name:'Parallel',unit:'USD'}], history:[partial]};
  workspacesApi.getWorkspaces = async()=>({workspaces:[{id:1,kind:'shared',display_name:'Shared'}]});
  balancesApi.getOverview = async()=>data;
  usageApi.getSummary = async()=>({});
  balancesApi.getHistoryEntry = async()=>partial;
  const listeners = {};
  const edit = {dataset:{editEntry:'1'},addEventListener:(type,fn)=> {listeners[type] = fn;}};
  const modal = {innerHTML:'',querySelectorAll:()=>[],querySelector:()=>({addEventListener:()=>{}})};
  globalThis.document = {getElementById:()=>modal,addEventListener:()=>{}};
  const container = {innerHTML:'',querySelector:()=>null,querySelectorAll:(selector)=>selector === '[data-edit-entry]' ? [edit] : []};
  try {
    await renderApiBalancesPage(container,{user:{role:'admin',capabilities:['balances:read','balances:write']}});
    await listeners.click();
    assert.match(modal.innerHTML, /Edit saved balances/);
    assert.match(modal.innerHTML, /value="20"/);
    assert.match(modal.innerHTML, /data-save-edit/);
  } finally {[workspacesApi.getWorkspaces,balancesApi.getOverview,usageApi.getSummary,balancesApi.getHistoryEntry,globalThis.document] = originals;}
});

test('late history detail from a previous workspace cannot open an editor', async () => {
  const originals = [workspacesApi.getWorkspaces, balancesApi.getOverview, usageApi.getSummary, balancesApi.getHistoryEntry, globalThis.document];
  const workspaces = [{id:1,kind:'shared',display_name:'Shared'},{id:2,kind:'private',display_name:'Other'}];
  workspacesApi.getWorkspaces = async()=>({workspaces});
  balancesApi.getOverview = async()=>overview;
  usageApi.getSummary = async()=>({});
  let resolveDetail;
  balancesApi.getHistoryEntry = () => new Promise((resolve)=> {resolveDetail=resolve;});
  const events = {};
  const edit = {dataset:{editEntry:'1'},addEventListener:(type,fn)=> {events.edit = fn;}};
  const select = {addEventListener:(type,fn)=> {events.switch = fn;}};
  const modal = {innerHTML:'',querySelectorAll:()=>[],querySelector:()=>({addEventListener:()=>{}})};
  globalThis.document = {getElementById:()=>modal,addEventListener:()=>{}};
  const container = {innerHTML:'',querySelector:(selector)=>selector === '[data-workspace-select]' ? select : null,
    querySelectorAll:(selector)=>selector === '[data-edit-entry]' ? [edit] : []};
  try {
    await renderApiBalancesPage(container,{user:{role:'admin',capabilities:['balances:read','balances:write','workspaces:manage']}});
    const editing = events.edit();
    await events.switch({target:{value:'2'}});
    resolveDetail({id:1,entry_date:'2035-01-01',entry_kind:'legacy',values:[]});
    await editing;
    assert.equal(modal.innerHTML, '');
    assert.match(container.innerHTML, /value="2" selected/);
  } finally {[workspacesApi.getWorkspaces,balancesApi.getOverview,usageApi.getSummary,balancesApi.getHistoryEntry,globalThis.document] = originals;}
});

test('separate history controls keep page states and ignore stale pagination after a workspace change', async () => {
  const originals = [workspacesApi.getWorkspaces, balancesApi.getOverview, usageApi.getSummary];
  workspacesApi.getWorkspaces = async()=>({workspaces:[{id:1,kind:'shared',display_name:'Shared'},{id:2,kind:'private',display_name:'Other'}]});
  usageApi.getSummary = async()=>({});
  const calls = [];
  let resolveSlow;
  const result = (page,size,workspace,topupPage,topupSize) => ({...overview,
    providers:[{provider_key:'openrouter',display_name:`Provider in workspace ${workspace}`,unit:'USD'}],
    history:[{id:workspace,entry_date:'2035-01-01',entry_kind:'balance',values:[]}],
    topup_history:[{...overview.topup_history[0],values:[{...overview.topup_history[0].values[0],display_name:`Added in workspace ${workspace}`}]}],
    pagination:{page,page_size:size,total_items:15,total_pages:3},topup_pagination:{page:topupPage,page_size:topupSize,total_items:15,total_pages:3},
  });
  balancesApi.getOverview = async (...args) => {
    calls.push(args);
    if (args[2] === 1 && args[3] === 3) return new Promise(resolve=>{resolveSlow=()=>resolve(result(...args));});
    return result(...args);
  };
  const events = {};
  const historyButton = {disabled:false,dataset:{historyPage:'2'},addEventListener:(type,fn)=>{events.history=fn;}};
  const topupButton = {disabled:false,dataset:{topupPage:'2'},addEventListener:(type,fn)=>{events.topup=fn;}};
  const select = {addEventListener:(type,fn)=>{events.switch=fn;}};
  const container = {innerHTML:'',querySelector:selector=>selector === '[data-workspace-select]' ? select : null,
    querySelectorAll:selector=>selector === '[data-history-page]' ? [historyButton] : selector === '[data-topup-page]' ? [topupButton] : []};
  try {
    await renderApiBalancesPage(container,{user:{role:'admin',capabilities:['balances:read','balances:write','workspaces:manage']}});
    await events.history();
    assert.deepEqual(calls.at(-1),[2,5,1,1,5]);
    await events.topup();
    assert.deepEqual(calls.at(-1),[2,5,1,2,5]);
    topupButton.dataset.topupPage = '3';
    const slow = events.topup();
    await events.switch({target:{value:'2'}});
    assert.deepEqual(calls.at(-1),[1,5,2,1,5]);
    resolveSlow();
    await slow;
    assert.match(container.innerHTML,/Provider in workspace 2/);
    assert.match(container.innerHTML,/Added in workspace 2/);
    assert.doesNotMatch(container.innerHTML,/Provider in workspace 1|Added in workspace 1/);
    assert.match(container.innerHTML,/data-topup-page="1"/);
  } finally {[workspacesApi.getWorkspaces,balancesApi.getOverview,usageApi.getSummary] = originals;}
});
