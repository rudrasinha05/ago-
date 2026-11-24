"use client";
import {useEffect,useRef,useState} from 'react';
import {boardMessage,replyText,respondStatusText} from './board-codenames';

const BASE='/v1/organization/company';
const LANGUAGES=[['en-IN','English (India)'],['hi-IN','Hindi']];
const speechApi=()=>typeof window==='undefined'?null:window.SpeechRecognition||window.webkitSpeechRecognition||null;

/** Talk to one Board member by voice or text. Every question and answer is a
 * normal recorded Global chat message; an answer is AI advice, never an
 * approval, a run or QA evidence. Voice uses the browser's own speech service. */
export function BoardRoom({api,me,members,seat,onSeat}){
 const [draft,setDraft]=useState(''),[log,setLog]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [listening,setListening]=useState(false),[lang,setLang]=useState('en-IN'),[speakReplies,setSpeakReplies]=useState(true);
 const [voice,setVoice]=useState({listen:false,speak:false});
 const recognition=useRef(null),alive=useRef(true),input=useRef(null),feed=useRef(null);
 const founder=Boolean(me?.roles?.includes('founder'));
 const member=members.find(m=>m.seat===seat)||members.find(m=>m.member)||null;
 useEffect(()=>{
  alive.current=true;
  setVoice({listen:Boolean(speechApi()),speak:typeof window!=='undefined'&&'speechSynthesis' in window});
  return()=>{alive.current=false;recognition.current?.abort?.();if(typeof window!=='undefined')window.speechSynthesis?.cancel?.();};
 },[]);
 useEffect(()=>{feed.current?.scrollTo?.({top:feed.current.scrollHeight});},[log]);
 function say(text){
  if(!speakReplies||!voice.speak||!text)return;
  try{
   window.speechSynthesis.cancel();
   const utterance=new SpeechSynthesisUtterance(text.slice(0,900));
   utterance.lang=lang;
   const match=window.speechSynthesis.getVoices().find(v=>v.lang===lang)||window.speechSynthesis.getVoices().find(v=>v.lang?.startsWith(lang.slice(0,2)));
   if(match)utterance.voice=match;
   window.speechSynthesis.speak(utterance);
  }catch{/* speaking is optional; the answer stays on screen */}
 }
 async function ask(text){
  const question=String(text||'').trim();
  if(!question||busy||!member?.member)return;
  setBusy(true);setError('');setDraft('');
  const at=new Date().toLocaleTimeString();
  setLog(old=>[...old,{id:'q'+Date.now(),who:'you',name:'You',text:question,at}]);
  try{
   const sent=await api.request(BASE+'/chat',{method:'POST',body:{channel:'global',body:boardMessage(member,question),
    mentions:[member.member.id],intent:'message',operation_key:crypto.randomUUID()}});
   if(!Number.isInteger(sent?.id))throw new Error('The question was not recorded. Try again.');
   if(!founder){setLog(old=>[...old,{id:'n'+sent.id,who:'note',text:'Saved in Global chat. Only the Founder can ask for an AI answer.'}]);return;}
   const result=await api.request(BASE+'/chat/orders/'+sent.id+'/respond',{method:'POST',body:{employee_id:member.member.id}});
   if(!alive.current)return;
   if(result?.status!=='responded'&&result?.status!=='already_replied'){
    setLog(old=>[...old,{id:'s'+sent.id,who:'note',text:respondStatusText(result?.status)}]);return;
   }
   const page=await api.request(BASE+'/chat?channel=global&limit=60');
   const reply=(Array.isArray(page?.items)?page.items:[]).find(m=>m.id===result.ack_message_id)
     ||(Array.isArray(page?.items)?page.items:[]).find(m=>m.reply_to===sent.id&&m.employee_id===member.member.id);
   const answer=reply?replyText(reply.body):'';
   if(!alive.current)return;
   setLog(old=>[...old,answer
    ?{id:'a'+(reply.id),who:'board',name:member.codename,color:member.color,text:answer,at:new Date().toLocaleTimeString()}
    :{id:'s'+sent.id,who:'note',text:'The answer was recorded in Global chat.'}]);
   say(answer);
  }catch(e){if(alive.current)setError(e?.message||'The Board member could not be reached.');}
  finally{if(alive.current){setBusy(false);requestAnimationFrame(()=>input.current?.focus());}}
 }
 function listen(){
  const Api=speechApi();
  if(!Api||busy)return;
  if(listening){recognition.current?.stop();return;}
  window.speechSynthesis?.cancel?.();
  const rec=new Api();recognition.current=rec;
  rec.lang=lang;rec.interimResults=true;rec.maxAlternatives=1;rec.continuous=false;
  let finalText='';
  rec.onresult=event=>{
   let heard='';
   for(let i=0;i<event.results.length;i++){heard+=event.results[i][0].transcript;if(event.results[i].isFinal)finalText=heard;}
   setDraft(heard);
  };
  rec.onerror=event=>{if(event.error==='not-allowed'||event.error==='service-not-allowed')setError('Microphone permission was refused. Allow the microphone for this page, or type instead.');
   else if(event.error!=='aborted'&&event.error!=='no-speech')setError('Voice input stopped ('+event.error+'). You can type instead.');};
  rec.onend=()=>{setListening(false);if(finalText.trim())ask(finalText);};
  setError('');setDraft('');setListening(true);
  try{rec.start();}catch{setListening(false);}
 }
 if(!members.some(m=>m.member))return <section className="board-room" aria-label="Board room">
  <h3>Board room</h3><p>No Board seat is appointed yet. Appoint AI officers in Board &amp; Roles to talk to them.</p></section>;
 return <section className="board-room" id="ago-board-room" aria-label="Board room">
  <header className="board-room-head">
   <div><h3>Board room</h3><p>Ask a Board member anything. Answers are AI advice, saved in Global chat; nothing is approved or run.</p></div>
   <div className="board-room-who" role="group" aria-label="Talk to">
    {members.map(m=><button key={m.seat} type="button" disabled={!m.member} aria-pressed={member?.seat===m.seat}
     style={{'--seat':m.color}} onClick={()=>onSeat(m.seat)}>{m.codename}</button>)}
   </div>
  </header>
  <ol className="board-room-feed" ref={feed} aria-label={'Conversation with '+(member?.codename||'the Board')} aria-live="polite">
   {!log.length&&<li className="board-room-empty">Try: “{member?.codename}, what is happening with our projects?”</li>}
   {log.map(entry=><li key={entry.id} className={'board-room-'+entry.who} style={entry.color?{'--seat':entry.color}:undefined}>
    {entry.who!=='note'&&<strong>{entry.name}</strong>}<span>{entry.text}</span>{entry.at&&<small>{entry.at}</small>}
   </li>)}
   {busy&&<li className="board-room-note" role="status">{member?.codename} is thinking…</li>}
  </ol>
  {error&&<p role="alert" className="board-room-error">{error}</p>}
  <form className="board-room-compose" onSubmit={e=>{e.preventDefault();ask(draft);}}>
   <label htmlFor="board-room-input" className="sr-only">Message {member?.codename}</label>
   <input id="board-room-input" ref={input} value={draft} maxLength={1500} disabled={busy}
    placeholder={listening?'Listening…':'Ask '+(member?.codename||'the Board')+'…'} onChange={e=>setDraft(e.target.value)}/>
   {voice.listen&&<button type="button" className={'board-room-mic'+(listening?' live':'')} aria-pressed={listening} disabled={busy}
    aria-label={listening?'Stop listening':'Speak to '+(member?.codename||'the Board')} onClick={listen}>
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>
   </button>}
   <button type="submit" disabled={busy||!draft.trim()}>{busy?'Asking…':'Ask'}</button>
  </form>
  <div className="board-room-options">
   {(voice.listen||voice.speak)&&<label>Voice language <select value={lang} onChange={e=>setLang(e.target.value)}>
    {LANGUAGES.map(([code,label])=><option key={code} value={code}>{label}</option>)}</select></label>}
   {voice.speak&&<label><input type="checkbox" checked={speakReplies} onChange={e=>{setSpeakReplies(e.target.checked);if(!e.target.checked)window.speechSynthesis?.cancel?.();}}/> Read answers aloud</label>}
   {!voice.listen&&<small>Voice input needs Chrome or Edge. You can type instead.</small>}
   {voice.listen&&<small>Voice is turned into text by your browser's speech service.</small>}
  </div>
 </section>;
}
