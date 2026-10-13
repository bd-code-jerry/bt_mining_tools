import { ledgerApi as api } from './api.js';
import { expensePageHtml, sharePreviewHtml, categoryOptions } from './view.js';
import { EMPTY_FILTERS, permissions, todayInTimezone, newCostDraft, newTransferDraft, parseCents, allocateCents, buildReportQuery, retryRequestId } from './model.js';
import { createLatestLoader } from './state.js';

const mounted = new WeakMap();
const value = (form,name) => form.querySelector?.(`[name="${name}"]`)?.value ?? form.elements?.namedItem?.(name)?.value ?? '';
function costPayload(draft) { return {amount:(parseCents(draft.amount)/100).toFixed(2),expense_date:draft.expense_date,category_id:Number(draft.category_id),note:draft.note,participant_ids:[...draft.participant_ids].map(Number).sort((a,b)=>a-b)}; }
export async function renderExpensePage(container,{user,onUnauthorized,registerTimezoneChangeHandler,confirmAction=(message)=>globalThis.confirm?.(message) ?? false}={},title='Overview') {
 mounted.get(container)?.();
 let active=true;
 const live=()=>active && container.isConnected !== false;
 const p=permissions(user);
 if(!p.read) { container.innerHTML='<div class="card empty-state">This account cannot read the team ledger.</div>'; return; }
 const state={title,user,timezone:user?.timezone||'UTC',participants:[],categories:[],people:{people:[],total_cents:0},costs:{costs:[],pagination:{}},summary:{},transfers:{origin:{transfers:[]},received:{transfers:[]}},filters:{...EMPTY_FILTERS},categorySearch:'',pages:{costs:1,origin:1,received:1},sizes:{costs:10,origin:10,received:10},costDraft:null,transferDraft:null,categoryDraft:null,manageCategories:false,error:'',notice:'',busy:false,loading:false};
 const render=()=>{if(live()) container.innerHTML=expensePageHtml(state);};
 const handleError=(error)=>{if(!live())return; if(error.status===401){active=false;loader.invalidate();onUnauthorized?.();return;} state.error=error.message||'The request could not be completed.';render();};
 const loader=createLatestLoader(async()=>{
   const filters={...state.filters},pages={...state.pages},sizes={...state.sizes};
   const operations=[api.getParticipants(),api.getCategories(),api.getPeople(buildReportQuery(filters,false)),api.getCosts({...buildReportQuery(filters),page:pages.costs,page_size:sizes.costs})];
   if(title==='Used') operations.push(api.getSummary(),api.getTransfers({kind:'origin',page:pages.origin,page_size:sizes.origin}),api.getTransfers({kind:'received',page:pages.received,page_size:sizes.received}));
   const [participants,categories,people,costs,summary,origin,received]=await Promise.all(operations);
   return {participants:participants.participants||[],categories:categories.categories||[],people,costs,...(summary?{summary,transfers:{origin,received}}:{})};
 },data=>{if(!live())return;Object.assign(state,data);state.loading=false;render();});
 const refresh=async()=>{if(!live())return;state.loading=true;render();try {await loader.load();}catch(error){state.loading=false;handleError(error);}};
 const scroll=(id)=>container.querySelector?.(id)?.scrollIntoView?.({behavior:'smooth',block:'start'});
 const mutate=async(operation,onSaved,notice)=>{
   if(state.busy||!live())return;
   state.busy=true;state.error='';state.notice='';render();
   try{const result=await operation();if(!live())return;onSaved?.(result);state.notice=notice;await refresh();}
   catch(error){handleError(error);}
   finally{state.busy=false;render();}
 };
 const findTransfer=(id)=>[...(state.transfers.origin.transfers||[]),...(state.transfers.received.transfers||[])].find(t=>Number(t.id)===id);
 const click=async(event)=>{
   const target=event.target?.closest?.('[data-action]')||event.target, action=target?.dataset?.action,id=Number(target?.dataset?.id);
   if(!action||target.disabled||state.busy||!live())return;
   const cost=state.costs.costs?.find(c=>Number(c.id)===id), transfer=findTransfer(id);
   if(action==='open-cost'&&p.write){state.costDraft=newCostDraft(todayInTimezone(state.timezone));state.categoryDraft=null;state.error='';render();scroll('#expense-cost-form');}
   else if(action==='close-cost'){state.costDraft=null;state.categoryDraft=null;render();}
   else if(action==='open-category'&&p.write&&state.costDraft){state.categoryDraft={name:'',parent_id:''};render();}
   else if(action==='close-category'){state.categoryDraft=null;render();}
   else if(action==='manage-categories'&&p.manage){state.manageCategories=true;render();}
   else if(action==='close-categories'){state.manageCategories=false;render();}
   else if(action==='edit-cost'&&p.write&&cost?.can_edit){state.costDraft={id:cost.id,amount:(cost.amount_cents/100).toFixed(2),expense_date:cost.expense_date,category_id:String(cost.category_id),note:cost.note||'',participant_ids:(cost.allocations||[]).map(a=>Number(a.participant_id))};state.categoryDraft=null;state.error='';render();scroll('#expense-cost-form');}
   else if(action==='delete-cost'&&p.write&&cost?.can_edit&&await confirmAction(`Delete this ${cost.expense_date} cost and all its allocations?`)){await mutate(()=>api.deleteCost(id),()=>{if(Number(state.costDraft?.id)===id)state.costDraft=null;},'Cost deleted.');}
   else if(action==='select-person'){state.filters.participant_id=String(id);state.pages.costs=1;state.error='';await refresh();}
   else if(action==='all-people'){state.filters.participant_id='';state.pages.costs=1;await refresh();}
   else if(action==='clear-filters'){state.filters={...EMPTY_FILTERS};state.categorySearch='';state.pages.costs=1;state.error='';await refresh();}
   else if(action==='paginate'){const section=target.dataset.section;if(!Object.hasOwn(state.pages,section))return;state.pages[section]=Math.max(1,Number(target.dataset.page)||1);await refresh();}
   else if(action==='open-transfer'&&p.write&&['origin','received'].includes(target.dataset.kind)){state.transferDraft=newTransferDraft(target.dataset.kind,todayInTimezone(state.timezone));state.error='';render();scroll('#expense-transfer-form');}
   else if(action==='close-transfer'){state.transferDraft=null;render();}
   else if(action==='edit-transfer'&&p.write&&transfer?.can_edit){state.transferDraft={id:transfer.id,kind:transfer.kind,amount:(transfer.amount_cents/100).toFixed(2),transfer_date:transfer.transfer_date,note:transfer.note||''};state.error='';render();scroll('#expense-transfer-form');}
   else if(action==='delete-transfer'&&p.write&&transfer?.can_edit&&await confirmAction(`Delete this ${transfer.kind} transfer dated ${transfer.transfer_date}?`)){await mutate(()=>api.deleteTransfer(id),()=>{if(Number(state.transferDraft?.id)===id)state.transferDraft=null;},'Transfer deleted.');}
 };
 const input=(event)=>{
   if(!active||state.busy)return;
   const target=event.target, form=target?.closest?.('form'), type=form?.dataset?.form,name=target?.name;
   if(target.hasAttribute?.('data-category-search')){state.categorySearch=target.value;const select=container.querySelector?.('[data-category-filter]');if(select)select.innerHTML=categoryOptions(state.categories,state.filters.category_id,{search:state.categorySearch});}
   const draft=type==='cost'?state.costDraft:type==='transfer'?state.transferDraft:type==='category'?state.categoryDraft:type==='filters'?state.filters:null;
   if(draft&&name&&name!=='participant_ids'&&Object.hasOwn(draft,name))draft[name]=target.value;
   if(type==='cost'&&state.costDraft){
     if(name==='participant_ids'){const id=Number(target.value);state.costDraft.participant_ids=target.checked?[...new Set([...state.costDraft.participant_ids,id])]:state.costDraft.participant_ids.filter(p=>Number(p)!==id);}
     if(target.hasAttribute?.('data-select-all')){state.costDraft.participant_ids=target.checked?state.participants.filter(p=>p.eligible).map(p=>Number(p.id)):[];container.querySelectorAll?.('[name="participant_ids"]').forEach(el=>{el.checked=state.costDraft.participant_ids.includes(Number(el.value));});}
     const preview=container.querySelector?.('[data-share-preview]');if(preview)preview.innerHTML=sharePreviewHtml(state.costDraft,state.participants);
   }
   if(type==='filters'&&name==='period'){for(const field of ['start_date','end_date']){const el=form.querySelector?.(`[name="${field}"]`);if(el)el.required=target.value==='custom';}}
 };
 const change=async(event)=>{input(event);const section=event.target?.dataset?.pageSize;if(section&&Object.hasOwn(state.sizes,section)){state.sizes[section]=Number(event.target.value)||10;state.pages[section]=1;await refresh();}};
 const submit=async(event)=>{
   const form=event.target,type=form?.dataset?.form;if(!type)return;event.preventDefault?.();if(state.busy||!live())return;state.error='';state.notice='';
   if(type==='filters'){
     for(const key of ['q','category_id','period','start_date','end_date'])state.filters[key]=value(form,key);
     if(state.filters.period==='custom'&&(!state.filters.start_date||!state.filters.end_date||state.filters.start_date>state.filters.end_date)){state.error='Choose a valid From and To date range.';render();return;}
     state.pages.costs=1;await refresh();
   } else if(type==='cost'&&p.write&&state.costDraft){
     const draft=state.costDraft;for(const key of ['amount','expense_date','category_id','note'])draft[key]=value(form,key);
     if(!parseCents(draft.amount)||!draft.expense_date||!draft.category_id||!allocateCents(draft.amount,draft.participant_ids)){state.error='Enter a positive USD amount with at most two decimals, a date, a category, and at least one participant.';render();return;}
     const payload=costPayload(draft);if(!draft.id)payload.request_id=retryRequestId(draft,payload);
     await mutate(()=>draft.id?api.updateCost(draft.id,payload):api.createCost(payload),()=>{state.costDraft=null;state.categoryDraft=null;state.pages.costs=1;},'Cost saved. Reports updated.');
   } else if(type==='category'&&p.write&&state.categoryDraft){
     const draft=state.categoryDraft;draft.name=value(form,'name');draft.parent_id=value(form,'parent_id');if(!draft.name.trim()){state.error='Enter a category name.';render();return;}
     await mutate(()=>api.createCategory({name:draft.name.trim(),parent_id:draft.parent_id?Number(draft.parent_id):null}),result=>{if(state.costDraft&&result.category)state.costDraft.category_id=String(result.category.id);state.categoryDraft=null;},'Category created. Your cost draft is preserved.');
   } else if(type==='manage-category'&&p.manage){
     const id=Number(form.dataset.id),name=value(form,'name').trim();if(!name){state.error='Enter a category name.';render();return;}
     const parent=value(form,'parent_id'), archived=Boolean(form.querySelector?.('[name="archived"]')?.checked);
     await mutate(()=>api.updateCategory(id,{name,parent_id:parent?Number(parent):null,archived}),null,'Category updated. Saved costs retain their purpose.');
   } else if(type==='transfer'&&p.write&&state.transferDraft){
     const draft=state.transferDraft;for(const key of ['amount','transfer_date','note'])draft[key]=value(form,key);
     if(!parseCents(draft.amount)||!draft.transfer_date){state.error='Enter a positive USD amount with at most two decimals and a transfer date.';render();return;}
     const payload={kind:draft.kind,amount:(parseCents(draft.amount)/100).toFixed(2),transfer_date:draft.transfer_date,note:draft.note};if(!draft.id)payload.request_id=retryRequestId(draft,payload);
     await mutate(()=>draft.id?api.updateTransfer(draft.id,payload):api.createTransfer(payload),()=>{state.transferDraft=null;state.pages[draft.kind]=1;},'Transfer saved. Funding totals updated.');
   }
 };
 container.addEventListener('click',click);container.addEventListener('input',input);container.addEventListener('change',change);container.addEventListener('submit',submit);
 const cleanup=()=>{active=false;loader.invalidate();container.removeEventListener?.('click',click);container.removeEventListener?.('input',input);container.removeEventListener?.('change',change);container.removeEventListener?.('submit',submit);};
 mounted.set(container,cleanup);
 registerTimezoneChangeHandler?.(async timezone=>{if(!live())return;state.timezone=timezone;await refresh();});
 container.innerHTML='<div class="loading-row">Loading team expenses…</div>';
 try{await loader.load();}catch(error){if(error.status===401){handleError(error);}else{state.error=error.message||'Unable to load team expenses.';render();}}
 return cleanup;
}
