// Screen recipe `form-quick-capture` (React): the structure and class names of the HTML recipe, with the same sample content. Split it into components, replace the sample
// data with your own and keep the class names or turn them into the project's utility classes. The colours come from CSS variables (see screen.css).
import "./screen.css";

export default function Screen() {
  return (
    <>
      <svg width={0} height={0} style={{ "position": "absolute" }} aria-hidden="true"><symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></symbol></svg>
      
      <header className="topbar"><div className="brand" style={{ "padding": "0" }}><i>D</i>Dayledger</div><nav aria-label="Primary"><a href="#" aria-current="page">Log</a><a href="#">Checklists</a><a href="#">Reports</a></nav><div className="grow"></div><span className="avatar">LM</span></header>
      <main className="main" style={{ "maxWidth": "1040px", "margin": "0 auto" }}>
        <div className="top"><div><h1>Shift log</h1><p className="sub">Riverside bakery · Tuesday morning shift</p></div></div>
        <div className="cap">
          <form className="card" aria-label="New entry" style={{ "padding": "24px", "display": "grid", "gap": "18px" }}>
            <div className="field"><label htmlFor="what">What happened?</label><textarea className="textarea" id="what" style={{ "minHeight": "120px" }} autoFocus defaultValue="Walk-in fridge reading 6.2 \u00b0C at 09:55, adjusted the thermostat." /><p className="hint">Plain words are fine. Add a photo if it helps.</p></div>
            <div className="field"><span className="label">Category</span><div className="chips" role="group" aria-label="Category"><button type="button" className="chip" aria-pressed="false">Bakery</button><button type="button" className="chip" aria-pressed="false">Supplier</button><button type="button" className="chip" aria-pressed="true">Equipment</button><button type="button" className="chip" aria-pressed="false">Compliance</button><button type="button" className="chip" aria-pressed="false">Other</button></div></div>
            <div className="grid cols-2" style={{ "gap": "16px" }}><div className="field"><label htmlFor="reading">Reading</label><input className="input mono" id="reading" defaultValue="6.2 \u00b0C" /></div><div className="field"><label htmlFor="who">Who is on it?</label><select className="select" id="who"><option>Me</option><option>Lucia Marin</option><option>Ops team</option></select></div></div>
            <div className="actions" style={{ "justifyContent": "space-between" }}><span className="muted" style={{ "fontSize": ".88rem" }}><span className="kbd">Ctrl</span> + <span className="kbd">Enter</span> to save</span><div className="actions"><button className="btn" type="button"><svg className="ico" aria-hidden="true"><use href="#i-plus" /></svg>Photo</button><button className="btn btn--primary" type="submit">Save entry</button></div></div>
          </form>
          <section className="card" aria-labelledby="rec"><div className="card-head"><h2 id="rec">Earlier today</h2><span className="pill pill--ok">4 logged</span></div><ul className="list"><li><div style={{ "flex": "1", "minWidth": "0" }}><div>Pot of the day: cardamom bun</div><div className="muted" style={{ "fontSize": ".85rem" }}>Bakery</div></div><span className="mono muted">09:41</span></li><li><div style={{ "flex": "1", "minWidth": "0" }}><div>Delivery short by 2 trays</div><div className="muted" style={{ "fontSize": ".85rem" }}>Supplier</div></div><span className="mono muted">09:12</span></li><li><div style={{ "flex": "1", "minWidth": "0" }}><div>Oven 2 ran hot, reset</div><div className="muted" style={{ "fontSize": ".85rem" }}>Equipment</div></div><span className="mono muted">08:50</span></li><li><div style={{ "flex": "1", "minWidth": "0" }}><div>Allergen sign replaced</div><div className="muted" style={{ "fontSize": ".85rem" }}>Compliance</div></div><span className="mono muted">08:15</span></li></ul></section>
        </div>
      </main>
    </>
  );
}
