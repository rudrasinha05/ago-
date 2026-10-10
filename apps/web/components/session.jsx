"use client";
import {createContext,useContext,useRef,useState} from 'react';
import {SessionClient} from '@ago/sdk/session';
import {Button,Field,Notice} from '@ago/ui/components';
const SessionContext = createContext(null);
export function useSession() {return useContext(SessionContext);}
export function SessionProvider({children}) {
  const [me,setMe]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState(false);
  const epoch=useRef(0), api=useRef(null);
  const clear=()=>{epoch.current++;api.current?.clear();setMe(null);setBusy(false);setError('');};
  if (!api.current) api.current=new SessionClient({onExpire:()=>{clear();setError('Your session expired. Sign in again.');}});
  async function login(event) {
    event.preventDefault(); if(busy)return; const form=event.currentTarget; const fields=new FormData(form); const version=++epoch.current;
    setBusy(true);setError('');
    try {
      await api.current.login({tenant:String(fields.get('tenant')).trim(),email:String(fields.get('email')).trim(),password:String(fields.get('password'))});
      const profile=await api.current.request('/v1/console/me');
      if(version!==epoch.current)return;
      if(!profile || !Array.isArray(profile.permissions) || !profile.id || !profile.tenant_id)throw new Error('Invalid member response');
      form.reset();setMe(profile);
    } catch(e) {if(version===epoch.current){api.current.clear();setError(e.status===401?'Organization, email or password was not accepted.':e.message);form.elements.password.value='';form.elements.password.focus();}}
    finally {if(version===epoch.current)setBusy(false);}
  }
  async function logout() {
    epoch.current++;setMe(null);setError('');setBusy(true);
    try {await api.current.logout();} catch {setError('Signed out locally. Server revocation could not be confirmed.');}
    finally {setBusy(false);}
  }
  return <SessionContext.Provider value={{me,api:api.current,logout,epoch}}>
    <a className="skip-link" href="#screen">Skip to main content</a>
    {me?children:<main id="screen" className="signin" tabIndex={-1}><div className="login-box"><p className="eyebrow">AGO · Your organization</p><h1>Clarity starts here.</h1><p>Sign in to your organization's workspace.</p><form id="login-form" onSubmit={login}>
      <Field id="tenant" label="Organization ID" required autoComplete="off" spellCheck={false} />
      <Field id="email" label="Work email" type="email" autoComplete="username" required />
      <Field id="password" label="Password" type="password" autoComplete="current-password" required />
      {error&&<Notice error>{error}</Notice>}<Button kind="primary" type="submit" disabled={busy}>{busy?'Signing in…':'Sign in'}</Button>
    </form><p className="muted">Ask your administrator for your organization ID and account.</p><a href="/console/">Open existing Control Center</a></div></main>}
  </SessionContext.Provider>;
}
