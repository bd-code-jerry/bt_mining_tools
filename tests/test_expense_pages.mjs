import test from 'node:test';
import assert from 'node:assert/strict';
import { ledgerApi } from '../frontend/js/features/expenses/api.js';
import { expensePageHtml, categoryOptions } from '../frontend/js/features/expenses/view.js';
import { allocateCents, parseCents, buildReportQuery, newCostDraft, retryRequestId } from '../frontend/js/features/expenses/model.js';
import { createLatestLoader } from '../frontend/js/features/expenses/state.js';
import { renderOverviewPage } from '../frontend/js/features/overview/page.js';
import { renderUsedPage } from '../frontend/js/features/used/page.js';

const user = { capabilities: ['expenses:read', 'expenses:write', 'expenses:manage'] };
const people = [{ id: 1, username: '<Alice>', role: 'user', status: 'active', total_cents: 5000 }, { id: 2, username: 'Bob', role: 'member', status: 'active', total_cents: 5000 }];
const categories = [{ id: 1, name: 'VPS', path: 'VPS / <Cloud>', parent_id: null, archived: false, effective_archived: false }];
function state() { return { title: 'Overview', user, participants: people.map(p => ({ ...p, eligible: true })), categories, people: { people, total_cents: 10000 }, costs: { costs: [], filtered_total_cents: 10000, pagination: { page: 1, total_pages: 1, total_items: 0, page_size: 10 } }, summary: { origin_cents: 15000, received_cents: 12000, spent_cents: 10000, remaining_cents: 2000 }, transfers: { origin: { transfers: [] }, received: { transfers: [] } }, filters: { q: '', category_id: '', period: 'all', start_date: '', end_date: '', participant_id: '' }, costDraft: null, transferDraft: null, error: '', busy: false }; }

test('exact cents and deterministic participant-ID remainder allocations', () => {
 assert.equal(parseCents('100.00'), 10000);
 assert.equal(parseCents('1.234'), null);
 assert.deepEqual(allocateCents('100', [3,1,2]), [{participant_id:1,share_cents:3334},{participant_id:2,share_cents:3333},{participant_id:3,share_cents:3333}]);
 assert.deepEqual(allocateCents('0.01', [2,1]), [{participant_id:1,share_cents:1},{participant_id:2,share_cents:0}]);
});
test('AND report filters preserve query and distinguish people totals from selected history', () => {
 const filters = { q: 'Bob', participant_id: '2', category_id: '1', period: 'custom', start_date: '2026-10-01', end_date:'2026-10-10' };
 assert.deepEqual(buildReportQuery(filters, true), filters);
 assert.deepEqual(buildReportQuery(filters, false), {q:'Bob',category_id:'1',period:'custom',start_date:'2026-10-01',end_date:'2026-10-10'});
});
test('both report pages show each person, category paths and escaped names', () => {
 for (const title of ['Overview','Used']) { const s = state(); s.title = title; const html=expensePageHtml(s); assert.match(html,/&lt;Alice&gt;/); assert.match(html,/Bob/); assert.match(html,/\$50.00/); assert.match(html,/VPS \/ &lt;Cloud&gt;/); assert.doesNotMatch(html,/<Alice>|<Cloud>/); assert.match(html,/Category includes all subcategories/); }
});
test('cost entry has all fields, exact shares, select all and inline category creation without changing draft', () => {
 const s=state(); s.costDraft={...newCostDraft('2026-10-13'), amount:'100',category_id:'1', note:'<draft>', participant_ids:[1,2]}; s.categoryDraft={name:'',parent_id:''}; const html=expensePageHtml(s);
 for (const field of ['amount','expense_date','category_id','note','participant_ids']) assert.match(html,new RegExp(`name="${field}"`));
 assert.match(html,/Select all/); assert.match(html,/\$50.00/); assert.match(html,/&lt;draft&gt;/); assert.match(html,/data-form="category"/); assert.equal(s.costDraft.amount,'100');
});
test('Used funding cards show received minus recorded costs and separate dated histories', () => { const s=state(); s.title='Used'; const html=expensePageHtml(s); for(const text of ['Origin','Received','Remaining balance','Total recorded costs','Origin history','Received history']) assert.ok(html.includes(text)); assert.match(html,/\$20.00/); });
test('member sees reports without mutation controls; only can_edit rows have correction buttons', () => { const s=state(); s.user={capabilities:['expenses:read']}; s.costs.costs=[{id:8,expense_date:'2026-10-13',category_path:'VPS',note:'x',amount_cents:1000,allocated_cents:1000,can_edit:true,allocations:[]}]; assert.doesNotMatch(expensePageHtml(s),/data-action="(?:open-cost|edit-cost|delete-cost|manage-categories)"/); });
test('retry IDs remain stable for identical submit, and change for changed payload', () => { const draft={}; const first=retryRequestId(draft,{amount:'10'}); assert.equal(retryRequestId(draft,{amount:'10'}),first); assert.notEqual(retryRequestId(draft,{amount:'11'}),first); });
test('latest request ignores stale data', async () => { const requests=[]; let current; const loader=createLatestLoader(()=>new Promise(resolve=>requests.push(resolve)),data=>{current=data;}); const a=loader.load(); const b=loader.load(); requests[1]('latest'); await b; requests[0]('stale'); assert.equal(await a,false); assert.equal(current,'latest'); });
test('shared client sends ledger fields, filters and credentialed JSON', async () => { const original=globalThis.fetch; const calls=[]; globalThis.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({})};}; try { await ledgerApi.getCosts({q:'Bob',category_id:1,participant_id:2,period:'week',page:2}); await ledgerApi.createCost({amount:'100',request_id:'stable'}); assert.match(calls[0].url,/\/api\/expenses\/costs\?/); assert.equal(new URL(calls[0].url,'http://x').searchParams.get('participant_id'),'2'); assert.equal(calls[1].options.credentials,'include'); assert.equal(JSON.parse(calls[1].options.body).request_id,'stable'); }finally{globalThis.fetch=original;} });
test('page exports load per-person totals and unauthorized failures invoke callback', async () => { const originals={...ledgerApi}; const listeners={}; const container={innerHTML:'',addEventListener:(name,handler)=>{listeners[name]=handler;},querySelector:()=>null}; Object.assign(ledgerApi,{getParticipants:async()=>({participants:[]}),getCategories:async()=>({categories}),getPeople:async()=>({people,total_cents:10000}),getCosts:async()=>({costs:[],pagination:{page:1,total_pages:1}}),getSummary:async()=>state().summary,getTransfers:async()=>({transfers:[]})}); try { await renderOverviewPage(container,{user}); assert.match(container.innerHTML,/Bob/); await renderUsedPage(container,{user}); assert.match(container.innerHTML,/Received history/); let unauthorized=0; ledgerApi.getPeople=async()=>{const e=new Error('expired');e.status=401;throw e;}; await renderOverviewPage(container,{user,onUnauthorized:()=>unauthorized++}); assert.equal(unauthorized,1); }finally{Object.assign(ledgerApi,originals);} });

function fakeContainer() {
 const handlers = {};
 return { innerHTML:'',isConnected:true,querySelector:()=>null,querySelectorAll:()=>[],addEventListener:(name,handler)=>{handlers[name]=handler;},removeEventListener:(name)=>{delete handlers[name];},async click(action,extra={}){const target={dataset:{action,...extra}};await handlers.click({target});},async input(form,name,fieldValue,extra={}) { const target={name,value:fieldValue,closest:()=>({dataset:{form}}),...extra};await handlers.input({target}); },async submit(type,fields={},extra={}) { const form={dataset:{form:type,...extra},querySelector:(selector)=>{const match=/\[name="([^"]+)"\]/.exec(selector);return match?{value:fields[match[1]]??'',checked:fields[match[1]]===true}:null;}};await handlers.submit({target:form,preventDefault(){}}); } };
}
function fakeLedger(overrides={}) {
 const original={...ledgerApi}; Object.assign(ledgerApi,{getParticipants:async()=>({participants:people.map(p=>({...p,eligible:true}))}),getCategories:async()=>({categories}),getPeople:async()=>({people,total_cents:10000}),getCosts:async()=>({costs:[],pagination:{page:1,total_pages:1}}),getSummary:async()=>state().summary,getTransfers:async()=>({transfers:[]}),...overrides}); return ()=>Object.assign(ledgerApi,original);
}
test('disconnected page does not sign out a newly mounted route on an old 401 response', async () => {
 let rejectRequest,unauthorized=0;const restore=fakeLedger({getPeople:()=>new Promise((_,reject)=>{rejectRequest=reject;})});
 try {const container=fakeContainer();const rendering=renderOverviewPage(container,{user,onUnauthorized:()=>unauthorized++});container.isConnected=false;const error=new Error('expired');error.status=401;rejectRequest(error);await rendering;assert.equal(unauthorized,0);}finally{restore();}
});
test('live cost draft survives inline category save and cost retry retains request UUID before refreshing totals', async()=>{
 const container=fakeContainer(),saves=[];let attempts=0,peopleLoads=0;
 const restore=fakeLedger({getPeople:async()=>{peopleLoads++;return {people,total_cents:10000};},createCategory:async()=>({category:{...categories[0],id:2,path:'VPS / New'}}),createCost:async body=>{saves.push(body);if(++attempts===1)throw new Error('Connection lost');return {cost:{id:1}};}});
 try{await renderOverviewPage(container,{user});await container.click('open-cost');await container.input('cost','amount','100');await container.input('cost','expense_date','2026-10-13');await container.input('cost','note','draft note');await container.input('cost','participant_ids','1',{checked:true});await container.input('cost','participant_ids','2',{checked:true});await container.click('open-category');await container.submit('category',{name:'New',parent_id:'1'});assert.match(container.innerHTML,/value="100"/);assert.match(container.innerHTML,/draft note/);const fields={amount:'100',expense_date:'2026-10-13',category_id:'2',note:'draft note'};await container.submit('cost',fields);assert.match(container.innerHTML,/Connection lost/);await container.submit('cost',fields);assert.equal(saves[0].request_id,saves[1].request_id);assert.deepEqual(saves[1].participant_ids,[1,2]);assert.match(container.innerHTML,/Cost saved/);assert.doesNotMatch(container.innerHTML,/data-form="cost"/);assert.ok(peopleLoads>=3);}finally{restore();}
});
test('timezone callback refreshes presets while preserving selected date-only cost draft',async()=>{
 let callback;const container=fakeContainer();const restore=fakeLedger();
 try{await renderUsedPage(container,{user,registerTimezoneChangeHandler:handler=>{callback=handler;}});await container.click('open-cost');await container.input('cost','expense_date','2020-05-01');await callback('America/New_York');assert.match(container.innerHTML,/value="2020-05-01"/);assert.match(container.innerHTML,/America\/New_York/);}finally{restore();}
});

test('category search finds current and saved historical paths while preserving selected categories',()=> { const catalog=[{id:1,path:'Cloud / New',historical_paths:['VPS / Old']},{id:2,path:'Office'},{id:3,path:'Unrelated'}]; const html=categoryOptions(catalog,2,{search:'vps'});assert.match(html,/Cloud \/ New/);assert.match(html,/Office/);assert.doesNotMatch(html,/Unrelated/); const current=categoryOptions(catalog,'',{search:'cloud'});assert.match(current,/Cloud \/ New/); const s=state();assert.match(expensePageHtml(s),/data-category-search/); });
