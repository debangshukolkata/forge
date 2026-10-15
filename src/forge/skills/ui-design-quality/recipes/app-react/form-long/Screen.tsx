// Screen recipe `form-long` (React): the structure and class names of the HTML recipe, with the same sample content. Split it into components, replace the sample
// data with your own and keep the class names or turn them into the project's utility classes. The colours come from CSS variables (see screen.css).
import "./screen.css";

export default function Screen() {
  return (
    <>
      <svg width={0} height={0} style={{ "position": "absolute" }} aria-hidden="true"><symbol id="i-users" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.2" /><path d="M3.5 19c.4-3 2.6-5 5.5-5s5.1 2 5.5 5" /><circle cx="17" cy="9" r="2.4" /><path d="M16 14.2c2.6-.2 4.3 1.5 4.6 4.3" /></symbol><symbol id="i-calendar" viewBox="0 0 24 24"><rect x="4" y="5.5" width="16" height="14.5" rx="2" /><path d="M4 10h16M9 3.5v4M15 3.5v4" /></symbol><symbol id="i-file" viewBox="0 0 24 24"><path d="M7 3.5h7l4 4V20.5H7z" /><path d="M14 3.5v4h4" /><path d="M9.5 13h5M9.5 16h5" /></symbol><symbol id="i-inbox" viewBox="0 0 24 24"><path d="M4 13.5 6.5 5h11L20 13.5V19H4z" /><path d="M4 13.5h5l1 2h4l1-2h5" /></symbol><symbol id="i-x" viewBox="0 0 24 24"><path d="m6 6 12 12M18 6 6 18" /></symbol></svg>
      
      <div className="app">
      <aside className="side" aria-label="Main"><div className="brand"><i>W</i>Ward &amp; Co</div><nav className="nav" aria-label="Primary"><a href="#" aria-current="page"><svg className="ico" aria-hidden="true"><use href="#i-users" /></svg>Patients</a><a href="#"><svg className="ico" aria-hidden="true"><use href="#i-calendar" /></svg>Appointments<span className="count">6</span></a><a href="#"><svg className="ico" aria-hidden="true"><use href="#i-file" /></svg>Referrals</a><a href="#"><svg className="ico" aria-hidden="true"><use href="#i-inbox" /></svg>Messages<span className="count">2</span></a></nav><div className="me"><span className="avatar">EN</span><div><b style={{ "fontSize": ".9rem" }}>Dr Elena Novak</b><div className="muted" style={{ "fontSize": ".8rem" }}>General practice</div></div></div></aside>
      <main className="main" style={{ "maxWidth": "980px" }}>
        <div className="top"><div><h1>New patient registration</h1><p className="sub">Fields marked * are needed to book a first appointment.</p></div></div>
        <div role="alert" className="card" style={{ "borderColor": "var(--color-danger)", "background": "color-mix(in srgb,var(--color-danger) 7%,var(--color-surface))", "display": "flex", "gap": "12px", "alignItems": "flex-start", "marginBottom": "18px" }}><span style={{ "color": "var(--color-danger)" }}><svg className="ico" aria-hidden="true"><use href="#i-x" /></svg></span><div><b>2 fields need your attention</b><p className="muted" style={{ "marginTop": "2px" }}><a href="#dob">Date of birth</a> is not a valid date, and <a href="#phone">phone</a> needs a number we can reach.</p></div></div>
        <form className="sections" aria-label="Registration">
          <section className="card fs" aria-labelledby="s1"><div><h2 id="s1">About the patient</h2><p>As it appears on their ID. We use it on every letter.</p></div>
            <div className="fields"><div className="row2"><div className="field"><label htmlFor="fn">First name *</label><input className="input" id="fn" defaultValue="Marcus" autoComplete="given-name" /></div><div className="field"><label htmlFor="ln">Last name *</label><input className="input" id="ln" defaultValue="Adeyemi" autoComplete="family-name" /></div></div>
            <div className="row2"><div className="field is-error"><label htmlFor="dob">Date of birth *</label><input className="input" id="dob" defaultValue="31/02/1988" aria-invalid="true" aria-describedby="dob-e" /><p className="error" id="dob-e"><svg className="ico" aria-hidden="true"><use href="#i-x" /></svg>There is no 31 February. Use day, month, year.</p></div><div className="field"><label htmlFor="sex">Sex recorded at birth</label><select className="select" id="sex"><option>Male</option><option>Female</option><option>Prefer not to say</option></select></div></div></div></section>
          <section className="card fs" aria-labelledby="s2"><div><h2 id="s2">Contact</h2><p>For appointment reminders only.</p></div>
            <div className="fields"><div className="row2"><div className="field is-error"><label htmlFor="phone">Phone *</label><input className="input" id="phone" defaultValue="0121 4" type="tel" aria-invalid="true" aria-describedby="phone-e" /><p className="error" id="phone-e"><svg className="ico" aria-hidden="true"><use href="#i-x" /></svg>That number is too short.</p></div><div className="field"><label htmlFor="em">Email</label><input className="input" id="em" type="email" placeholder="name@example.com" /></div></div>
            <div className="field"><label htmlFor="ad">Address</label><textarea className="textarea" id="ad" style={{ "minHeight": "80px" }} defaultValue="52 Larch Road, Birmingham B13 9QA" /></div></div></section>
          <section className="card fs" aria-labelledby="s3"><div><h2 id="s3">Preferences</h2><p>You can change these at any time.</p></div>
            <div className="fields"><label className="check"><input type="checkbox" defaultChecked /> Send reminders by text message</label><label className="check"><input type="checkbox" /> Send reminders by email</label><label className="check"><input type="checkbox" defaultChecked /> Share my record with my pharmacy</label></div></section>
        </form>
        <div className="stickybar">{/* for a form taller than the screen add position:sticky;bottom:0 here */}<span className="muted" style={{ "marginRight": "auto" }}>Unsaved changes</span><button className="btn">Cancel</button><button className="btn btn--primary">Register patient</button></div>
      </main></div>
    </>
  );
}
