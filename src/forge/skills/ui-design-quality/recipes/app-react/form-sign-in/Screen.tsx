// Screen recipe `form-sign-in` (React): the structure and class names of the HTML recipe, with the same sample content. Split it into components, replace the sample
// data with your own and keep the class names or turn them into the project's utility classes. The colours come from CSS variables (see screen.css).
import "./screen.css";

export default function Screen() {
  return (
    <>
      <svg width={0} height={0} style={{ "position": "absolute" }} aria-hidden="true"><symbol id="i-shield" viewBox="0 0 24 24"><path d="M12 3.5 19 6v5.5c0 4.2-2.8 7.2-7 9-4.2-1.8-7-4.8-7-9V6z" /><path d="m9 12 2.2 2.2L15.2 10" /></symbol></svg>
      
      <div className="auth">
        <main className="auth-form"><div className="auth-card">
          <div className="brand" style={{ "padding": "0 0 6px" }}><i>H</i>Harbourside</div>
          <div><h1>Welcome back</h1><p className="muted" style={{ "marginTop": "6px" }}>Sign in to see this week's bookings.</p></div>
          <button className="btn" style={{ "width": "100%" }} type="button"><svg className="ico" aria-hidden="true"><use href="#i-shield" /></svg>Continue with company single sign-on</button>
          <div className="or">or use your email</div>
          <form style={{ "display": "grid", "gap": "16px" }} aria-label="Sign in">
            <div className="field"><label htmlFor="email">Email</label><input className="input" id="email" type="email" defaultValue="sam@harbourside.example" autoComplete="username" /></div>
            <div className="field"><div style={{ "display": "flex", "justifyContent": "space-between" }}><label htmlFor="pw">Password</label><a href="#" style={{ "fontSize": ".88rem" }}>Forgot it?</a></div><input className="input" id="pw" type="password" defaultValue="correcthorse" autoComplete="current-password" /></div>
            <label className="check"><input type="checkbox" defaultChecked /> Keep me signed in on this device</label>
            <button className="btn btn--primary" style={{ "width": "100%", "minHeight": "44px" }} type="submit">Sign in</button>
          </form>
          <p className="muted" style={{ "textAlign": "center" }}>New here? <a href="#">Create an account</a></p>
        </div></main>
        <aside className="auth-art"><div className="art-clip"><svg viewBox="0 0 400 400" aria-hidden="true"><circle cx="270" cy="270" r="190" fill="none" stroke="currentColor" strokeOpacity=".22" strokeWidth="2" /><circle cx="270" cy="270" r="140" fill="none" stroke="currentColor" strokeOpacity=".3" strokeWidth="2" /><circle cx="270" cy="270" r="90" fill="none" stroke="currentColor" strokeOpacity=".4" strokeWidth="2" /><path d="M80 330c60-70 110-20 170-90s70-110 130-150" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" /><circle cx="380" cy="90" r="12" fill="currentColor" /></svg></div><div className="brand" style={{ "padding": "0", "position": "relative" }}><i>H</i>Harbourside</div><blockquote>"We stopped chasing spreadsheets on Mondays. The week simply appears."<cite>Dana Whitlock, operations manager at Pier 9 Charters</cite></blockquote></aside>
      </div>
    </>
  );
}
