// Composition `nonprofit-appeal` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="hero" aria-label="Donate">
        {/* Drawn scene: dusk sky, a sun, ploughed field rows and a long table of people sharing a meal. */}
        <svg className="hero__scene" viewBox="0 0 1280 680" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2b1d14" /><stop offset=".55" stopColor="#7a3a1e" /><stop offset="1" stopColor="#d98a3a" /></linearGradient></defs>
          <rect width="1280" height="680" fill="url(#sky)" />
          <circle cx="960" cy="400" r="120" fill="#f3c15c" opacity=".92" />
          <path d="M0 470q200-70 420-30t430-20 430 10v240H0z" fill="#4a3a22" />
          <path d="M0 520q260-60 520-20t760-10v190H0z" fill="#3d5a38" />
          <g fill="none" stroke="#2f4a2d" strokeWidth="5" strokeLinecap="round"><path d="M0 570q320-40 640-10t640-10M0 610q320-40 640-10t640-10M0 650q320-40 640-10t640-10" /></g>
          <g fill="#2b1d14"><rect x="860" y="548" width="300" height="12" rx="3" /><rect x="880" y="560" width="8" height="40" /><rect x="1130" y="560" width="8" height="40" />
            <circle cx="900" cy="520" r="11" /><path d="M886 548v-16q14-10 28 0v16z" /><circle cx="950" cy="518" r="11" /><path d="M936 548v-16q14-10 28 0v16z" /><circle cx="1010" cy="522" r="10" /><path d="M997 548v-14q13-9 26 0v14z" /><circle cx="1070" cy="518" r="11" /><path d="M1056 548v-16q14-10 28 0v16z" /><circle cx="1115" cy="524" r="9" /><path d="M1103 548v-12q12-8 24 0v12z" /></g>
          <g fill="#f3c15c"><circle cx="930" cy="544" r="5" /><circle cx="1040" cy="544" r="5" /></g>
        </svg>
        <div className="wrap hero__inner">
          <p className="hero__brand">Fieldfare Food Trust</p>
          <h1>No one in Calderdale should skip a meal.</h1>
          <p>Last winter our volunteers grew, cooked and delivered 61,000 meals. A gift today keeps the kitchen warm through the next one.</p>
          <form className="give" action="#" aria-label="Donate">
            <fieldset className="give__set">
              <legend className="give__legend">Choose a monthly gift</legend>
              <div className="give__chips">
                <label className="chip"><input type="radio" name="amount" defaultValue="8" /><span>£8</span></label>
                <label className="chip"><input type="radio" name="amount" defaultValue="15" defaultChecked /><span>£15</span></label>
                <label className="chip"><input type="radio" name="amount" defaultValue="30" /><span>£30</span></label>
              </div>
            </fieldset>
            <button className="btn" type="submit">Give £15 a month</button>
            <small>£15 feeds a family of four for a week. Cancel any time.</small>
          </form>
        </div>
      </section>
      
      <section className="impact" aria-label="Our impact last year">
        <div className="wrap impact__grid">
          <div><span className="impact__num">61,000</span><span className="impact__label">hot meals served</span></div>
          <div><span className="impact__num">2,400</span><span className="impact__label">families supported</span></div>
          <div><span className="impact__num">38</span><span className="impact__label">community gardens</span></div>
          <div><span className="impact__num">92p</span><span className="impact__label">of every pound goes to food</span></div>
        </div>
      </section>
      
      <section className="section wrap story" aria-labelledby="story-title">
        <div>
          <span className="eyebrow">Our story</span>
          <h2 id="story-title">It began with one borrowed oven</h2>
          <p>In 2014 Marian Holt cooked a Sunday dinner for six neighbours who had run out of money before the end of the month. Word travelled. Within a year there were forty at her table and a queue at her door.</p>
          <p>Today the Trust is two kitchens, thirty-eight allotments and three hundred volunteers. The table is still the point: nobody is handed a bag and sent away.</p>
        </div>
        <figure className="quote">
          <span className="quote__mark" aria-hidden="true">&ldquo;</span>
          <blockquote>I came for the food. I stayed because someone remembered how I take my tea.</blockquote>
          <figcaption>
            <svg width={44} height={44} viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="22" fill="#e9a93c" /><circle cx="22" cy="17" r="7" fill="#2b1d14" /><path d="M8 38q14-18 28 0z" fill="#2b1d14" /></svg>
            <span>Dev, volunteer and former guest</span>
          </figcaption>
        </figure>
      </section>
      
      <section className="programmes section" aria-labelledby="prog-title">
        <div className="wrap">
          <span className="eyebrow">Where your gift goes</span>
          <h2 id="prog-title">Three ways we feed people</h2>
          <div className="cards">
            <article className="card">
              <svg viewBox="0 0 360 180" role="img" aria-label="A pot on a hob with steam"><rect width="360" height="180" fill="#f1d9a8" /><path d="M110 70c-10-14 10-20 0-34M180 66c-10-14 10-20 0-34M250 70c-10-14 10-20 0-34" fill="none" stroke="#b3441c" strokeWidth="4" strokeLinecap="round" /><path d="M80 90h200v50q0 20-20 20H100q-20 0-20-20z" fill="#3d5a38" /><rect x="66" y="84" width="228" height="12" rx="6" fill="#2b1d14" /><rect x="40" y="160" width="280" height="8" rx="4" fill="#2b1d14" /></svg>
              <div className="card__body"><h3>Community kitchens</h3><p>Hot, cooked meals three evenings a week, eaten together at a long table.</p><a href="#">See the rota</a></div>
            </article>
            <article className="card">
              <svg viewBox="0 0 360 180" role="img" aria-label="Rows of seedlings in a raised bed"><rect width="360" height="180" fill="#cfdcb5" /><rect x="30" y="110" width="300" height="50" rx="8" fill="#7a4a2a" /><g fill="none" stroke="#3d5a38" strokeWidth="5" strokeLinecap="round"><path d="M70 110V76M130 110V64M190 110V80M250 110V60M300 110V78" /></g><g fill="#3d5a38"><ellipse cx="58" cy="74" rx="14" ry="7" /><ellipse cx="82" cy="78" rx="14" ry="7" /><ellipse cx="118" cy="62" rx="14" ry="7" /><ellipse cx="142" cy="66" rx="14" ry="7" /><ellipse cx="238" cy="58" rx="14" ry="7" /><ellipse cx="262" cy="62" rx="14" ry="7" /></g><circle cx="300" cy="40" r="20" fill="#e9a93c" /></svg>
              <div className="card__body"><h3>Grow Together</h3><p>Allotments lent free to families, with seeds, tools and a neighbour who knows how.</p><a href="#">Find a plot</a></div>
            </article>
            <article className="card">
              <svg viewBox="0 0 360 180" role="img" aria-label="A delivery bike with a crate"><rect width="360" height="180" fill="#f0c9b0" /><circle cx="110" cy="130" r="30" fill="none" stroke="#2b1d14" strokeWidth="6" /><circle cx="260" cy="130" r="30" fill="none" stroke="#2b1d14" strokeWidth="6" /><path d="M110 130l50-50h70l30 50M160 80l30 50h70" fill="none" stroke="#2b1d14" strokeWidth="6" strokeLinejoin="round" /><rect x="130" y="40" width="70" height="38" rx="5" fill="#b3441c" /><path d="M130 56h70" stroke="#fbf4e8" strokeWidth="4" /></svg>
              <div className="card__body"><h3>Doorstep deliveries</h3><p>Weekly boxes, brought by a friendly volunteer, to people who cannot get out.</p><a href="#">Ask for a box</a></div>
            </article>
          </div>
        </div>
      </section>
      
      <footer className="foot">
        <div className="wrap">
          <div className="foot__grid">
            <div><p className="foot__brand">Fieldfare Food Trust</p><p>Registered charity 1203345. Working from Hebden Bridge since 2014.</p></div>
            <div><h4>Get involved</h4><ul><li><a href="#">Volunteer</a></li><li><a href="#">Donate food</a></li><li><a href="#">Fundraise</a></li></ul></div>
            <div><h4>About us</h4><ul><li><a href="#">Our story</a></li><li><a href="#">Annual report</a></li><li><a href="#">Contact</a></li></ul></div>
            <div><h4>Kitchen notes, monthly</h4><form className="news" action="#"><input type="email" placeholder="you@example.org" aria-label="Email address" /><button className="btn" type="submit">Join</button></form></div>
          </div>
          <p className="foot__legal">&copy; 2026 Fieldfare Food Trust. Every gift is Gift Aid eligible.</p>
        </div>
      </footer>
    </>
  );
}
