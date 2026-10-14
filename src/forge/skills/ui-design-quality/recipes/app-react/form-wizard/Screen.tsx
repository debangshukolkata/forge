// Screen recipe `form-wizard` (React): the structure and class names of the HTML recipe, with the same sample content. Split it into components, replace the sample
// data with your own and keep the class names or turn them into the project's utility classes. The colours come from CSS variables (see screen.css).
import "./screen.css";

export default function Screen() {
  return (
    <>
      <svg width={0} height={0} style={{ "position": "absolute" }} aria-hidden="true"><symbol id="i-check" viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5" /></symbol><symbol id="i-chevron" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6" /></symbol><symbol id="i-x" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18" /></symbol></svg>
      
      <main className="main" style={{ "maxWidth": "1020px", "margin": "0 auto", "paddingTop": "34px" }}>
        <div className="brand" style={{ "padding": "0 0 22px" }}><i>K</i>Kiln</div>
        <div className="top" style={{ "marginBottom": "8px" }}><div><h1>Set up your workspace</h1><p className="sub">Step 3 of 4 · you can change all of this later</p></div><a className="btn btn--ghost" href="#">Save and exit</a></div>
        <ol className="steps" aria-label="Progress"><li className="step step--done"><span className="dot"><svg className="ico" aria-hidden="true"><use href="#i-check" /></svg></span><span>Company</span></li><li className="step step--done"><span className="dot"><svg className="ico" aria-hidden="true"><use href="#i-check" /></svg></span><span>Team</span></li><li className="step step--now" aria-current="step"><span className="dot">3</span><span>Billing</span></li><li className="step step--todo"><span className="dot">4</span><span>Review</span></li></ol>
        <div className="grid" style={{ "gridTemplateColumns": "minmax(0,3fr) minmax(0,2fr)", "alignItems": "start" }} id="split">
          <form className="card" aria-labelledby="bill" style={{ "padding": "26px" }}>
            <h2 id="bill" style={{ "fontSize": "1.25rem", "marginBottom": "4px" }}>Billing details</h2><p className="muted" style={{ "marginBottom": "22px" }}>We send invoices here. Nothing is charged until your trial ends.</p>
            <fieldset style={{ "border": "0", "padding": "0", "margin": "0 0 22px" }}><legend className="label" style={{ "marginBottom": "10px" }}>Plan</legend>
              <div className="grid cols-2" style={{ "gap": "12px" }}><label className="plan"><input type="radio" name="plan" /><b>Team</b> <span className="muted">· $12 per seat</span><p className="muted" style={{ "margin": "4px 0 0 24px", "fontSize": ".9rem" }}>Up to 25 people, shared projects</p></label>
              <label className="plan"><input type="radio" name="plan" defaultChecked /><b>Business</b> <span className="muted">· $24 per seat</span><p className="muted" style={{ "margin": "4px 0 0 24px", "fontSize": ".9rem" }}>Single sign-on, audit log, priority help</p></label></div></fieldset>
            <div className="form-grid">
              <div className="field"><label htmlFor="legal">Company legal name</label><input className="input" id="legal" defaultValue="Kiln Ceramics Ltd" autoComplete="organization" /></div>
              <div className="field is-error"><label htmlFor="mail">Billing email</label><input className="input" id="mail" type="email" defaultValue="accounts@kiln" autoComplete="email" aria-describedby="mail-e" aria-invalid="true" /><p className="error" id="mail-e"><svg className="ico" aria-hidden="true"><use href="#i-x" /></svg>Enter a full address, like accounts@kiln.example</p></div>
              <div className="field"><label htmlFor="vat">VAT number</label><input className="input mono" id="vat" placeholder="GB 123 4567 89" /><p className="hint">Optional. Needed to invoice without VAT in the EU.</p></div>
              <div className="field"><label htmlFor="country">Country</label><select className="select" id="country"><option>United Kingdom</option><option>Ireland</option><option>Germany</option></select></div>
              <div className="wide"><div className="field"><label htmlFor="addr">Billing address</label><textarea className="textarea" id="addr" style={{ "minHeight": "84px" }} defaultValue="14 Foundry Lane, Stoke-on-Trent ST1 4AB" /></div></div>
            </div>
            <div className="actions" style={{ "justifyContent": "space-between", "marginTop": "26px" }}><button className="btn" type="button"><svg className="ico" style={{ "transform": "scaleX(-1)" }} aria-hidden="true"><use href="#i-chevron" /></svg>Back</button><button className="btn btn--primary" type="submit">Continue to review</button></div>
          </form>
          <aside className="card" aria-labelledby="sum"><h2 id="sum" style={{ "marginBottom": "14px" }}>Your order</h2>
            <ul className="list"><li>Business plan<b className="num" style={{ "marginLeft": "auto" }}>$24 × 8</b></li><li>Extra storage, 200 GB<b className="num" style={{ "marginLeft": "auto" }}>$10</b></li><li className="muted">14-day trial<span style={{ "marginLeft": "auto" }}>−$202</span></li></ul>
            <hr className="divider" /><div style={{ "display": "flex", "justifyContent": "space-between", "alignItems": "baseline" }}><b>Due today</b><b className="num" style={{ "font": "600 1.7rem var(--font-display)" }}>$0.00</b></div><p className="muted" style={{ "fontSize": ".88rem", "marginTop": "8px" }}>Then $202 per month from 1 April. Cancel any time before then.</p>
          </aside>
        </div>
      </main>
    </>
  );
}
