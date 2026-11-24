// AI Models (AI-001): plain words for the Founder's cloud model settings.
// The server is the source of truth; keys never reach the browser after saving.

export const PROVIDER_INFO={
 openai:{name:'OpenAI',keyUrl:'https://platform.openai.com/api-keys',keyLooks:'sk-…',example:'pick from "Load models"'},
 anthropic:{name:'Claude',keyUrl:'https://console.anthropic.com/settings/keys',keyLooks:'sk-ant-…',example:'pick from "Load models"'},
 gemini:{name:'Gemini',keyUrl:'https://aistudio.google.com/apikey',keyLooks:'AIza…',example:'pick from "Load models"'},
 groq:{name:'Groq',keyUrl:'https://console.groq.com/keys',keyLooks:'gsk_…',example:'pick from "Load models"'},
};

// MGR-002: plain names for the kinds of work the Workforce Manager assigns.
export const WORK_NAMES={code:'Code writing',qa:'QA review',plan:'Planning',board:'Board review',chat:'Board chat',learn:'Writing a skill'};
export const PAID=new Set(['openai','anthropic']);

const ERROR_TEXT={
 auth_failed:'The key was refused. Check it, or make a new key.',
 access_denied:'The provider blocked this request (key permissions, account not activated, or region). Check the key\'s permissions in the provider console.',
 model_not_found:'This model name is not available for your key. Use "Load models".',
 rate_limited_or_no_credit:'Too many calls, or no credit left on this account.',
 request_rejected:'The provider rejected the request. Try another model.',
 provider_unavailable:'The provider is down right now. Try again later.',
 network_unreachable:'This computer could not reach the provider. Check the internet.',
 incomplete_answer:'The answer was cut off. Try a bigger model.',
 empty_answer:'The model gave an empty answer.',
 response_too_large:'The answer was too large.',
 unreadable_response:'The provider sent an answer AGO could not read.',
 monthly_cap_reached:'This month\'s paid-call limit is used up, or paid models are off. Free models do the work.',
 no_text_model:'This key has no text model AGO can use.',
 workspace_id_needed:'This Claude key works across workspaces. Add its Workspace ID (Console → Workspaces, starts with wrkspc_), or make a key for one workspace.',
};
/** One sentence for AGO's own failure code. */
export function errorText(code){
 return ERROR_TEXT[code]||(code?'Failed ('+String(code)+').':'');
}

/** Plain result of pressing Connect. */
export function connectText(name,c){
 if(!c)return '';
 const busy=(c.tried||[]).filter(t=>!t.ok).map(t=>t.model);
 const before=busy.length?' (tried first: '+busy.join(', ')+')':'';
 if(!c.ok)return name+': '+errorText(c.code)+before+(c.saved?'':' The key was not saved.');
 return name+' connected. Model: '+c.model+before+'. The Employee Manager can now use it.';
}

/** Status chip for one provider row. */
export function providerStatus(p){
 if(!p?.saved)return {tone:'idle',text:'Not connected'};
 if(p.test_status==='ok'&&!p.last_error)return {tone:'ok',text:'Working'};
 if(p.test_status==='ok')return {tone:'warn',text:'Working, last call failed'};
 if(p.test_status==='failed')return {tone:'bad',text:'Test failed'};
 return {tone:'warn',text:'Saved, test it'};
}

/** Connected models the Manager may use: saved AND passed the test. */
export function usable(view){
 return (view?.providers||[]).filter(p=>p.saved&&p.test_status==='ok');
}

/** One line for this month's usage. */
export function usageLine(view){
 const u=view?.usage;if(!u)return '';
 return u.calls+' cloud calls in '+u.month+' ('+(u.paid_calls||0)+' of '+view.monthly_call_cap+' paid)'
  +(u.input_tokens||u.output_tokens?' · '+u.input_tokens.toLocaleString('en-IN')+' tokens in, '+u.output_tokens.toLocaleString('en-IN')+' out':'');
}

/** What the Manager can use right now, in words. */
export function managerPool(view){
 const ok=usable(view);
 const free=ok.filter(p=>!PAID.has(p.provider)).map(p=>PROVIDER_INFO[p.provider].name);
 const paid=ok.filter(p=>PAID.has(p.provider)).map(p=>PROVIDER_INFO[p.provider].name);
 const parts=['Local model (Ollama)',...free];
 if(paid.length)parts.push(view.allow_paid?paid.join(', ')+' (paid, when the work needs it)':paid.join(', ')+' (paid, switched off)');
 return parts.join(' · ');
}

/** The server's settings, or null when the answer is not that shape. */
export function settingsView(raw){
 if(!raw||typeof raw!=='object'||!Array.isArray(raw.providers))return null;
 return {...raw,providers:raw.providers.filter(p=>p&&PROVIDER_INFO[p.provider]),
  allow_paid:raw.allow_paid!==false,
  usage:raw.usage&&typeof raw.usage==='object'?raw.usage:{month:'',calls:0,paid_calls:0,input_tokens:0,output_tokens:0},
  monthly_call_cap:Number.isInteger(raw.monthly_call_cap)?raw.monthly_call_cap:0};
}

/** The Manager's recent decisions, or [] when the answer is not that shape. */
export function decisionsView(raw){
 if(!raw||raw.kind!=='ago_model_decisions_v1'||!Array.isArray(raw.decisions))return [];
 return raw.decisions.filter(d=>d&&WORK_NAMES[d.work]&&typeof d.model_label==='string').map(d=>({
  id:String(d.id),work:WORK_NAMES[d.work],role:d.role||'',model:d.model_label,reason:String(d.reason||''),
  at:String(d.created_at||''),paid:PAID.has(d.model_label.split(':')[0])}));
}
