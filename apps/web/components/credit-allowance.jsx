"use client";
import {useCallback,useEffect,useState} from 'react';
import {CREDITS_PER_CHAIN_RUN,creditBalance} from './task-self-check-state';

/** Founder control for the internal AI credit allowance (POST /v1/insights/budget). */
export function CreditAllowance({api,me,onBalance}){
 const canRead=me.permissions?.includes('insights:read');
 const canManage=canRead&&me.roles?.includes('founder')&&me.permissions?.includes('economy:manage');
 const [balance,setBalance]=useState(undefined),[value,setValue]=useState(''),[confirm,setConfirm]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const publish=useCallback(next=>{setBalance(next);onBalance?.(next);},[onBalance]);
 const load=useCallback(async()=>{
  if(!canRead)return;
  try{publish(creditBalance(await api.request('/v1/insights/scorecard')));}
  catch{publish(null);}
 },[api,canRead,publish]);
 useEffect(()=>{load();},[load]);
 if(!canRead)return null;
 const ceiling=Number(value);
 const valid=Number.isInteger(ceiling)&&ceiling>0&&ceiling<=1000000&&(!balance||ceiling>=balance.consumed);
 async function save(){
  if(busy||!valid||!confirm)return;
  setBusy(true);setError('');setNotice('');
  try{
   const result=creditBalance({virtual_credit_budget:await api.request('/v1/insights/budget',{method:'POST',body:{ceiling}})});
   if(!result||result.ceiling!==ceiling)throw new Error('The server did not confirm the new allowance. Refresh before trying again.');
   publish(result);setValue('');setConfirm(false);
   setNotice('AI credit allowance saved: '+result.remaining+' of '+result.ceiling+' credits available. Nothing was run.');
  }catch(e){setError(e.message||'Allowance not saved.');}
  finally{setBusy(false);}
 }
 const runs=balance?Math.floor(balance.remaining/CREDITS_PER_CHAIN_RUN):0;
 return <section className="credit-allowance" aria-label="AI credit allowance">
  <h4>AI credit allowance</h4>
  {balance===undefined?<p role="status">Reading the recorded allowance…</p>:
   balance===null?<p role="status">The allowance could not be read. The server still checks it at every AI call.</p>:
   <p><strong>{balance.remaining}</strong> of {balance.ceiling} internal credits available ({balance.consumed} used).
    {' '}Each AI role call uses 1 credit; one full AI-team run uses {CREDITS_PER_CHAIN_RUN}, so this allows {runs} run{runs===1?'':'s'}.
    {' '}Credits are not money and never pay a provider.</p>}
  {canManage&&balance!==undefined&&<div className="credit-allowance-form">
   <label>New total allowance<input type="number" min={Math.max(1,balance?.consumed||0)} max={1000000} step={1} value={value} disabled={busy}
    onChange={e=>{setValue(e.target.value);setConfirm(false);setError('');}}/></label>
   {value!==''&&!valid&&<small role="status">Enter a whole number from {Math.max(1,balance?.consumed||0)} to 1,000,000.</small>}
   {valid&&<label className="credit-confirm"><input type="checkbox" checked={confirm} disabled={busy} onChange={e=>setConfirm(e.target.checked)}/>
    Set the internal AI credit allowance to {ceiling} (about {Math.floor((ceiling-(balance?.consumed||0))/CREDITS_PER_CHAIN_RUN)} AI-team runs). This runs nothing.</label>}
   <button type="button" disabled={busy||!valid||!confirm} onClick={save}>{busy?'Saving…':'Save allowance'}</button>
  </div>}
  {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
 </section>;
}
