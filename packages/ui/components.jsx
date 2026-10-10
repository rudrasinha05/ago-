/** Shared semantic components; route/session ownership belongs to the app. */
export function Button({children,kind='soft',...props}) {return <button type="button" className={'btn btn-'+kind} {...props}>{children}</button>;}
export function Field({id,label,children,...props}) {return <><label className="field-label" htmlFor={id}>{label}</label>{children || <input id={id} name={id} {...props} />}</>;}
export function Notice({children,error=false}) {return <p role={error?'alert':'status'} className={error?'error-box':'notice-card'}>{children}</p>;}
export function Panel({title,children}) {return <section className="panel"><div className="panel-head"><h2>{title}</h2></div><div className="panel-body">{children}</div></section>;}
export function Metric({label,value,note}) {return <div className="metric"><div className="metric-label">{label}</div><div className="metric-value">{value ?? '—'}</div><p className="metric-foot">{note}</p></div>;}
export function Records({rows,label,empty='No records yet'}) {return rows===null ? <Notice>{label} unavailable to your role or temporarily unavailable.</Notice> : rows.length===0 ? <p>{empty}</p> : <ul className="record-list">{rows.map(x=><li key={x.id}><strong>{x.action || x.title || x.name || x.id}</strong><span>{String(x.status || x.kind || '').replaceAll('_',' ')}</span></li>)}</ul>;}
export function Loading({label='Loading authorized records…'}) {return <p role="status" className="notice-card">{label}</p>;}
