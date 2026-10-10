export function WorkspaceShell({title, description, kind, capabilities}) {
  return <main className="workspace">
    <header><a className="brand" href="/">AGO<span>Artificial General Organization</span></a><span className="badge">{kind} workspace</span></header>
    <section className="hero"><p className="eyebrow">Clarity. Governance. Evidence.</p><h1>{title}</h1><p className="lead">{description}</p>
      <a className="primary" href="http://127.0.0.1:8000/console/">Open existing Control Center <span aria-hidden="true">↗</span></a>
      <p className="note">Run the local backend to use the Control Center. These application shells do not display private organizational data.</p>
    </section>
    <section className="cards" aria-label="Platform foundations">{capabilities.map(c=><article key={c.title}><span className="state">{c.state}</span><h2>{c.title}</h2><p>{c.description}</p></article>)}</section>
    <footer>Modular monolith foundation · reviewed architecture · independent human authority</footer>
  </main>;
}
