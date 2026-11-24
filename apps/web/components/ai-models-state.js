// AI Models (AI-001): plain words for the Founder's cloud model settings.
// The server is the source of truth; keys never reach the browser after saving.

export const PROVIDER_INFO={
 openai:{name:'OpenAI',keyUrl:'https://platform.openai.com/api-keys',keyLooks:'sk-…',example:'pick from "Load models"'},
 anthropic:{name:'Claude',keyUrl:'https://console.anthropic.com/settings/keys',keyLooks:'sk-ant-…',example:'pick from "Load models"'},
 gemini:{name:'Gemini',keyUrl:'https://aistudio.google.com/apikey',keyLooks:'AIza…',example:'pick from "Load models"'},
 groq:{name:'Groq',keyUrl:'https://console.groq.com/keys',keyLooks:'gsk_…',example:'pick from "Load models"'},
};

export const ROUTE_INFO=[
 {route:'code',label:'Code writing',help:'The AI engineer writes source files and tests.'},
 {route:'qa',label:'QA review',help:'The AI tester checks finished work.'},
 {route:'chat',label:'Board chat',help:'JARVIS and the Board answer you.'},
];

const ERROR_TEXT={
 auth_failed:'The key was refused. Check it, or make a new key.',
 model_not_found:'This model name is not available for your key. Use "Load models".',
 rate_limited_or_no_credit:'Too many calls, or no credit left on this account.',
 request_rejected:'The provider rejected the request. Try another model.',
 provider_unavailable:'The provider is down right now. Try again later.',
 network_unreachable:'This computer could not reach the provider. Check the internet.',
 incomplete_answer:'The answer was cut off. Try a bigger model.',
 empty_answer:'The model gave an empty answer.',
 response_too_large:'The answer was too large.',
 unreadable_response:'The provider sent an answer AGO could not read.',
 monthly_cap_reached:'This month\'s call limit is used up. The local model does the work.',
};
/** One sentence for AGO's own failure code. */
export function errorText(code){
 return ERROR_TEXT[code]||(code?'Failed ('+String(code)+').':'');
}

/** Status chip for one provider row. */
export function providerStatus(p){
 if(!p?.saved)return {tone:'idle',text:'Not added'};
 if(p.test_status==='ok'&&!p.last_error)return {tone:'ok',text:'Working'};
 if(p.test_status==='ok')return {tone:'warn',text:'Working, last call failed'};
 if(p.test_status==='failed')return {tone:'bad',text:'Test failed'};
 return {tone:'warn',text:'Saved, test it'};
}

/** Providers the Founder may route work to: saved AND passed the test. */
export function routable(view){
 return (view?.providers||[]).filter(p=>p.saved&&p.test_status==='ok');
}

/** One line for this month's usage. */
export function usageLine(view){
 const u=view?.usage;if(!u)return '';
 const cap=view.monthly_call_cap;
 return u.calls+' of '+cap+' cloud calls used in '+u.month
  +(u.input_tokens||u.output_tokens?' · '+u.input_tokens.toLocaleString('en-IN')+' tokens in, '+u.output_tokens.toLocaleString('en-IN')+' out':'');
}

/** Which model does each kind of work, in words. */
export function routeSummary(view){
 const names=Object.fromEntries((view?.providers||[]).map(p=>[p.provider,PROVIDER_INFO[p.provider]?.name+(p.model?' ('+p.model+')':'')]));
 return ROUTE_INFO.map(r=>({...r,uses:view?.routes?.[r.route]?names[view.routes[r.route]]||view.routes[r.route]:'Local model (Ollama)'}));
}

/** The server's settings, or null when the answer is not that shape. */
export function settingsView(raw){
 if(!raw||typeof raw!=='object'||!Array.isArray(raw.providers)||!raw.routes||typeof raw.routes!=='object')return null;
 return {...raw,providers:raw.providers.filter(p=>p&&PROVIDER_INFO[p.provider]),
  usage:raw.usage&&typeof raw.usage==='object'?raw.usage:{month:'',calls:0,input_tokens:0,output_tokens:0},
  monthly_call_cap:Number.isInteger(raw.monthly_call_cap)?raw.monthly_call_cap:0};
}
