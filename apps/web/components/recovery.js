// Plain-language recovery guidance for a failed AGO request (Issue #7 item 7).
// It explains what the recorded failure means and the safe next step. It never
// retries, never hides the server message, and never claims a write did or did
// not happen when the outcome is unknown.
const WRITE_UNCERTAIN='If you had just pressed an action button, check the record before trying again: the server may already have done it.';

export function recoveryHint(error){
  if(!error)return null;
  const status=Number.isInteger(error.status)?error.status:null;
  const message=String(error.message||'');
  if(status===401)return {what:'Your sign-in has expired.',
    next:'Sign in again. A request rejected as signed-out changes nothing on the server.'};
  if(status===403)return {what:'Your account is not allowed to do this step.',
    next:'Ask the Founder to assign the right role. AGO does not skip permission checks.'};
  if(status===404)return {what:'This record no longer exists, or you are not allowed to see it.',
    next:'Use Refresh and open it again from the current list.'};
  if(status===409)return {what:'The record changed after you opened it. Someone else may have acted, or the step moved on.',
    next:'Refresh and review the current state before deciding again. AGO does not repeat the action for you.'};
  if(status===400||status===422)return {what:'The server did not accept this input.',
    next:'Read the message above, correct the input, then try again.'};
  if(status===429)return {what:'Too many requests in a short time.',
    next:'Wait about a minute, then use Refresh.'};
  if(status!==null&&status>=500)return {what:'The AGO server hit a problem while handling this.',
    next:'Use Refresh in a moment. If it keeps failing, close AGO and run START_AGO.cmd again: its checks report database, Docker and Ollama problems. '+WRITE_UNCERTAIN};
  if(status===0||/timed out|failed to fetch|network|load failed/i.test(message))return {
    what:'AGO did not answer in time, or could not be reached.',
    next:'Check that the AGO window (START_AGO.cmd) is still running, then use Refresh. '+WRITE_UNCERTAIN};
  return null;
}
