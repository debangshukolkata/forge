// Composition `saas-product-tour` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <header className="wrap nav">
        <div className="nav__brand">
          <svg width={28} height={28} viewBox="0 0 28 28" aria-hidden="true"><rect width="28" height="28" rx="7" fill="#2253d4" /><path d="M14 5v12" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" /><circle cx="14" cy="21" r="3.2" fill="#fff" /></svg>
          Plumbline
        </div>
        <nav className="nav__links" aria-label="Main"><a href="#tour">Product</a><a href="#plans">Pricing</a><a href="#faq">Questions</a></nav>
        <a className="btn btn--small" href="#plans">Start free</a>
      </header>
      
      <main>
      <section className="wrap hero" aria-labelledby="hero-title">
        <span className="hero__tag">Build schedules that hold</span>
        <h1 id="hero-title">Plan the job. See it slip before it does.</h1>
        <p>Plumbline links every task, crew and delivery in one timeline, then tells you which late lorry will move your handover date.</p>
        <a className="btn" href="#plans">Try it with your next project</a>
        <span className="hero__note">Free for 14 days. No card needed.</span>
      
        <div className="shot">
          {/* Drawn app window: sidebar, a Gantt-style timeline and a warning card. */}
          <svg viewBox="0 0 960 520" role="img" aria-label="The Plumbline timeline showing tasks as bars with one flagged delay">
            <rect width="960" height="520" fill="#fff" />
            <rect width="960" height="42" fill="#eef2f8" />
            <circle cx="24" cy="21" r="6" fill="#ff6b5e" /><circle cx="46" cy="21" r="6" fill="#ffbd44" /><circle cx="68" cy="21" r="6" fill="#2fc15d" />
            <rect x="330" y="11" width="300" height="20" rx="10" fill="#fff" stroke="#d6dfeb" />
            <rect x="0" y="42" width="190" height="478" fill="#f5f8fc" />
            <rect x="20" y="66" width="110" height="12" rx="6" fill="#0e1a2e" />
            <rect x="20" y="104" width="150" height="34" rx="8" fill="#e4ecfd" /><rect x="34" y="117" width="80" height="8" rx="4" fill="#2253d4" />
            <rect x="34" y="162" width="100" height="8" rx="4" fill="#9fb0c8" /><rect x="34" y="194" width="120" height="8" rx="4" fill="#9fb0c8" /><rect x="34" y="226" width="86" height="8" rx="4" fill="#9fb0c8" />
            <g stroke="#e3e9f2"><path d="M330 90v410M470 90v410M610 90v410M750 90v410M890 90v410" /></g>
            <g fill="#51627a" fontFamily="Inter,system-ui,sans-serif" fontSize="12"><text x="330" y="80">Mon</text><text x="470" y="80">Tue</text><text x="610" y="80">Wed</text><text x="750" y="80">Thu</text><text x="890" y="80">Fri</text></g>
            <g fontFamily="Inter,system-ui,sans-serif" fontSize="14" fill="#0e1a2e"><text x="214" y="124">Groundworks</text><text x="214" y="176">Frame</text><text x="214" y="228">Roof trusses</text><text x="214" y="280">First fix</text><text x="214" y="332">Plaster</text><text x="214" y="384">Handover</text></g>
            <rect x="330" y="108" width="190" height="22" rx="6" fill="#2253d4" />
            <rect x="470" y="160" width="220" height="22" rx="6" fill="#2253d4" />
            <rect x="600" y="212" width="130" height="22" rx="6" fill="#e0614f" />
            <rect x="690" y="264" width="170" height="22" rx="6" fill="#7c9ae8" />
            <rect x="760" y="316" width="130" height="22" rx="6" fill="#7c9ae8" />
            <rect x="860" y="368" width="30" height="22" rx="6" fill="#0f9d8a" />
            <path d="M690 171v52M730 223v52" stroke="#9fb0c8" strokeWidth="2" fill="none" />
            <rect x="380" y="410" width="300" height="76" rx="12" fill="#fff" stroke="#e0614f" strokeWidth="2" />
            <circle cx="406" cy="436" r="10" fill="#e0614f" /><text x="406" y="441" fontFamily="Inter,system-ui,sans-serif" fontSize="14" fontWeight="700" fill="#fff" textAnchor="middle">!</text>
            <rect x="428" y="428" width="200" height="10" rx="5" fill="#0e1a2e" /><rect x="428" y="450" width="230" height="8" rx="4" fill="#9fb0c8" /><rect x="428" y="466" width="150" height="8" rx="4" fill="#9fb0c8" />
          </svg>
        </div>
      </section>
      
      <section className="logos" aria-label="Customers">
        <div className="wrap">
          <p className="logos__label">Scheduling work for 1,200 site teams</p>
          {/* Logo wall: invented marks drawn from simple shapes. */}
          <div className="logos__row" aria-hidden="true">
            <svg viewBox="0 0 120 32"><circle cx="14" cy="16" r="10" fill="#8a9ab2" /><rect x="32" y="10" width="76" height="12" rx="6" fill="#8a9ab2" /></svg>
            <svg viewBox="0 0 120 32"><path d="M4 28L16 4l12 24z" fill="#8a9ab2" /><rect x="36" y="10" width="70" height="12" rx="6" fill="#8a9ab2" /></svg>
            <svg viewBox="0 0 120 32"><rect x="4" y="6" width="20" height="20" rx="4" fill="#8a9ab2" /><rect x="32" y="10" width="60" height="12" rx="6" fill="#8a9ab2" /></svg>
            <svg viewBox="0 0 120 32"><path d="M14 2l12 8v12l-12 8L2 22V10z" fill="#8a9ab2" /><rect x="34" y="10" width="76" height="12" rx="6" fill="#8a9ab2" /></svg>
            <svg viewBox="0 0 120 32"><circle cx="10" cy="16" r="6" fill="#8a9ab2" /><circle cx="26" cy="16" r="6" fill="#8a9ab2" /><rect x="42" y="10" width="64" height="12" rx="6" fill="#8a9ab2" /></svg>
            <svg viewBox="0 0 120 32"><rect x="4" y="14" width="24" height="6" rx="3" fill="#8a9ab2" /><rect x="4" y="4" width="24" height="6" rx="3" fill="#8a9ab2" /><rect x="4" y="24" width="24" height="6" rx="3" fill="#8a9ab2" /><rect x="36" y="10" width="70" height="12" rx="6" fill="#8a9ab2" /></svg>
          </div>
        </div>
      </section>
      
      <section className="section wrap" id="tour" aria-labelledby="tour-title">
        <div className="section__head">
          <span className="eyebrow">The tour</span>
          <h2 id="tour-title">Three things your spreadsheet cannot do</h2>
        </div>
      
        <div className="row">
          <div>
            <span className="eyebrow">Dependencies</span>
            <h3>Move one task, watch the rest follow</h3>
            <p>Drag the frame start back a day and every task that waits on it shifts with it. Nothing is retyped, nothing is forgotten.</p>
            <ul><li>Finish-to-start and overlap links</li><li>Working days and bank holidays per site</li></ul>
          </div>
          <div className="row__visual">
            <svg viewBox="0 0 440 260" role="img" aria-label="Linked task bars cascading to the right">
              <rect width="440" height="260" fill="#f5f8fc" rx="8" />
              <rect x="24" y="30" width="150" height="26" rx="7" fill="#2253d4" /><rect x="150" y="82" width="170" height="26" rx="7" fill="#2253d4" /><rect x="250" y="134" width="120" height="26" rx="7" fill="#7c9ae8" /><rect x="330" y="186" width="86" height="26" rx="7" fill="#0f9d8a" />
              <path d="M174 56v13q0 13 13 13M320 108v13q0 13-13 13h-57M370 160v13q0 13 13 13" fill="none" stroke="#51627a" strokeWidth="2" />
            </svg>
          </div>
        </div>
      
        <div className="row row--flip">
          <div>
            <span className="eyebrow">Early warnings</span>
            <h3>Hear about the delay on Tuesday, not Friday</h3>
            <p>Plumbline reads supplier confirmations and weather feeds, then flags the tasks at risk with the number of days they could cost.</p>
            <ul><li>Alerts go to the person who can fix it</li><li>One tap to propose a new date</li></ul>
          </div>
          <div className="row__visual">
            <svg viewBox="0 0 440 260" role="img" aria-label="A risk card with a rising line and a warning marker">
              <rect width="440" height="260" fill="#f5f8fc" rx="8" />
              <rect x="24" y="24" width="392" height="212" rx="12" fill="#fff" stroke="#d6dfeb" />
              <path d="M50 190l60-30 60 14 70-64 70-20 60-40" fill="none" stroke="#2253d4" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="300" cy="100" r="9" fill="#e0614f" /><rect x="50" y="46" width="120" height="10" rx="5" fill="#0e1a2e" /><rect x="50" y="66" width="80" height="8" rx="4" fill="#9fb0c8" />
              <rect x="290" y="206" width="100" height="8" rx="4" fill="#9fb0c8" />
            </svg>
          </div>
        </div>
      
        <div className="row">
          <div>
            <span className="eyebrow">Handover pack</span>
            <h3>One link for the client, always current</h3>
            <p>Share a read-only view with the dates that matter and nothing else. When the plan changes, their page does too.</p>
            <ul><li>Branded with your logo</li><li>Comments land back on the task</li></ul>
          </div>
          <div className="row__visual">
            <svg viewBox="0 0 440 260" role="img" aria-label="A shared page with a milestone list and a progress ring">
              <rect width="440" height="260" fill="#f5f8fc" rx="8" />
              <circle cx="110" cy="130" r="58" fill="none" stroke="#d6dfeb" strokeWidth="16" /><path d="M110 72a58 58 0 1 1-41 99" fill="none" stroke="#0f9d8a" strokeWidth="16" strokeLinecap="round" />
              <text x="110" y="138" textAnchor="middle" fontFamily="Inter,system-ui,sans-serif" fontSize="24" fontWeight="700" fill="#0e1a2e">72%</text>
              <g><rect x="210" y="70" width="190" height="14" rx="7" fill="#0e1a2e" /><rect x="210" y="104" width="150" height="10" rx="5" fill="#9fb0c8" /><rect x="210" y="132" width="170" height="10" rx="5" fill="#9fb0c8" /><rect x="210" y="160" width="120" height="10" rx="5" fill="#9fb0c8" /></g>
            </svg>
          </div>
        </div>
      </section>
      
      <section className="plans section" id="plans" aria-labelledby="plans-title">
        <div className="wrap">
          <div className="section__head"><span className="eyebrow">Pricing</span><h2 id="plans-title">Pick a plan, change it any month</h2></div>
          <table className="compare">
            <caption style={{ "position": "absolute", "left": "-9999px" }}>Plan comparison</caption>
            <thead>
              <tr><td></td>
                <th scope="col"><span className="plan__name">Site</span><span className="plan__price">£19<small>/mo</small></span></th>
                <th scope="col" className="is-pick"><span className="plan__name">Team</span><span className="plan__price">£59<small>/mo</small></span></th>
                <th scope="col"><span className="plan__name">Firm</span><span className="plan__price">£189<small>/mo</small></span></th></tr>
            </thead>
            <tbody>
              <tr><th scope="row">Live projects</th><td>2</td><td className="is-pick">15</td><td>Unlimited</td></tr>
              <tr><th scope="row">Linked tasks</th><td><span className="yes">&#10003;</span></td><td className="is-pick"><span className="yes">&#10003;</span></td><td><span className="yes">&#10003;</span></td></tr>
              <tr><th scope="row">Delay alerts</th><td><span className="no">&ndash;</span></td><td className="is-pick"><span className="yes">&#10003;</span></td><td><span className="yes">&#10003;</span></td></tr>
              <tr><th scope="row">Client handover page</th><td><span className="no">&ndash;</span></td><td className="is-pick"><span className="yes">&#10003;</span></td><td><span className="yes">&#10003;</span></td></tr>
              <tr><th scope="row">Single sign-on</th><td><span className="no">&ndash;</span></td><td className="is-pick"><span className="no">&ndash;</span></td><td><span className="yes">&#10003;</span></td></tr>
            </tbody>
            <tfoot>
              <tr><td></td><td><a className="btn btn--small" href="#">Choose Site</a></td><td className="is-pick"><a className="btn btn--small" href="#">Choose Team</a></td><td><a className="btn btn--small" href="#">Choose Firm</a></td></tr>
            </tfoot>
          </table>
        </div>
      </section>
      
      <section className="section wrap" id="faq" aria-labelledby="faq-title">
        <div className="section__head"><span className="eyebrow">Questions</span><h2 id="faq-title">Before you ask</h2></div>
        <div className="faq">
          <div>
            <div className="faq__item"><h3>Can I import my current plan?</h3><p>Yes. Drop in a spreadsheet or a project file and we map the columns for you.</p></div>
            <div className="faq__item"><h3>Do my subcontractors need accounts?</h3><p>No. They get a link to their own tasks and can confirm dates from a phone.</p></div>
            <div className="faq__item"><h3>Where is my data kept?</h3><p>In the UK and EU, encrypted, with a daily backup you can download.</p></div>
          </div>
          <div>
            <div className="faq__item"><h3>What happens after the trial?</h3><p>You drop to a read-only view until you choose a plan. Nothing is deleted.</p></div>
            <div className="faq__item"><h3>Can I change plan mid-month?</h3><p>Any time. We credit the unused days against the next invoice.</p></div>
            <div className="faq__item"><h3>Is there help getting started?</h3><p>A real person walks your first project through with you, free on every plan.</p></div>
          </div>
        </div>
      </section>
      
      <section className="cta"><h2>Your next handover date, you can trust.</h2><a className="btn" href="#plans">Start the free trial</a></section>
      </main>
      <footer className="foot">&copy; 2026 Plumbline Software Ltd. Made in Leeds.</footer>
    </>
  );
}
