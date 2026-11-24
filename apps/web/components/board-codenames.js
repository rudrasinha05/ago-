// Founder's chosen call names for the five Board seats (2026-11-24). A call
// name is presentation only: authority still comes from the approved seat
// appointment and the real employee record shown next to it.
export const BOARD_CODENAMES={
 'Strategy & Vision':{codename:'JARVIS',role:'CEO',color:'#8fb3ff',duty:'Strategy and the final call on projects'},
 'Technology Oversight':{codename:'STARK',role:'CTO',color:'#f2a65a',duty:'Architecture, code and technical risk'},
 'Finance & Budget':{codename:'LUTHOR',role:'CFO',color:'#e7c488',duty:'Money, credits and spend'},
 'Risk & Compliance':{codename:'SPECTRE',role:'Risk',color:'#b5a1ff',duty:'Rules, security and contracts'},
 'Quality & Release':{codename:'DR. STRANGE',role:'Quality',color:'#7be6ce',duty:'QA evidence and release'},
};
export const BOARD_SEAT_ORDER=Object.keys(BOARD_CODENAMES);

/** Two letters for the call-name badge, e.g. "JA", "DS". */
export function initials(codename){
 const words=String(codename||'').replace(/[^A-Za-z ]/g,' ').trim().split(/\s+/).filter(Boolean);
 if(!words.length)return '?';
 return (words.length>1?words[0][0]+words[words.length-1][0]:words[0].slice(0,2)).toUpperCase();
}

/** Seats with call names and their approved, still-listed member (or null). */
export function boardMembers(board,employees){
 const byId=new Map((Array.isArray(employees)?employees:[]).map(e=>[e.id,e]));
 return BOARD_SEAT_ORDER.map(seat=>{
  const appointment=(Array.isArray(board)?board:[]).find(b=>b&&b.seat===seat);
  const member=appointment?byId.get(appointment.employee_id)||null:null;
  return {seat,...BOARD_CODENAMES[seat],initials:initials(BOARD_CODENAMES[seat].codename),member};
 });
}

const REPLY_PREFIX=/^Local model reply \(not task execution\/QA evidence\):\s*/;
/** The spoken part of a recorded AI chat reply: no label, no routing lines. */
export function replyText(body){
 return String(body||'').replace(REPLY_PREFIX,'').split('\n')
  .filter(line=>!/^\s*DELEGATE_ID:/i.test(line)).join('\n').trim();
}

/** The message the Founder sends: who it is for is in the text, for the record. */
export function boardMessage(member,text){
 return 'Voice chat with '+member.codename+' ('+member.seat+'): '+String(text||'').trim();
}

const RESPOND_STATUS={
 local_model_disabled:'Local AI replies are turned off on this server, so nobody answered.',
 model_unavailable:'The local AI model did not answer. Nothing was recorded as a reply.',
 already_processing:'This question is already being answered. Check Global chat.',
 retry_limit:'This question reached its reply limit. Ask again in a new message.',
};
/** Plain words for a respond result that is not an answer. */
export function respondStatusText(status){
 return RESPOND_STATUS[status]||'No reply was recorded ('+String(status||'unknown')+').';
}
