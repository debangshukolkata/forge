// Composition `local-trades` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <div className="top"><div className="wrap"><span>Licensed &amp; insured · Same-day call-outs</span><span>Open <b>7 am to 9 pm</b>, every day</span></div></div>
      <header className="hero">
        <div className="wrap hero__grid">
          <div>
            <span className="hero__tag">Plumbing &amp; heating · Leeds</span>
            <h1 className="hero__title">Leak at 2 am? <span>We pick up.</span></h1>
            <p className="hero__lead">Fixed prices quoted before we start, tidy workers and a van that carries the part you need. Family-run since 2009.</p>
            <a className="hero__phone" href="tel:+441130000000">0113 000 0000</a>
            <p className="hero__note">Call now, or send a photo by text. We reply within ten minutes.</p>
          </div>
          {/* Drawn van with a wrench and pipe: not a placeholder. */}
          <svg className="hero__art" viewBox="0 0 520 330" role="img" aria-label="A work van with a ladder on the roof and a wrench and pipe beside it">
            <rect x="0" y="262" width="520" height="10" fill="#d5dbe0" />
            <rect x="40" y="86" width="340" height="12" rx="3" fill="#4d5b68" /><rect x="40" y="86" width="12" height="40" fill="#4d5b68" /><rect x="368" y="86" width="12" height="40" fill="#4d5b68" />
            <path d="M30 240V130c0-12 8-20 20-20h250c10 0 18 5 24 14l38 50h42c10 0 16 8 16 18v48z" fill="#0f2234" />
            <path d="M322 134l30 40h-62v-40z" fill="#9cc7e8" /><path d="M270 134v40h-70v-40z" fill="#9cc7e8" />
            <rect x="40" y="186" width="190" height="26" rx="3" fill="#e8590c" /><text x="52" y="205" fontFamily="Arial,sans-serif" fontWeight="700" fontSize="17" fill="#fff">PIPE &amp; SON · 24H</text>
            <rect x="430" y="214" width="22" height="12" rx="2" fill="#ffb27a" />
            <g fill="#14202b"><circle cx="110" cy="248" r="30" /><circle cx="360" cy="248" r="30" /></g><g fill="#d5dbe0"><circle cx="110" cy="248" r="13" /><circle cx="360" cy="248" r="13" /></g>
            <g transform="translate(445 60) rotate(30)"><rect x="-7" y="0" width="14" height="170" rx="6" fill="#e8590c" /><path d="M-22 0a22 22 0 1 1 44 0v-14h-14a8 8 0 0 0-16 0h-14z" fill="#e8590c" /></g>
          </svg>
        </div>
      </header>
      
      <section className="services" aria-labelledby="svc-title">
        <div className="wrap">
          <h2 className="sec-title" id="svc-title">What we fix</h2>
          <div className="services__grid">
            <article className="card">
              <svg className="card__icon" viewBox="0 0 48 48" role="img" aria-label="Drop"><path d="M24 4c10 12 14 19 14 26a14 14 0 0 1-28 0c0-7 4-14 14-26z" fill="#e8590c" /><path d="M17 31a7 7 0 0 0 7 7" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" /></svg>
              <h3>Leaks &amp; blockages</h3><p>Burst pipes, dripping taps, slow drains, a toilet that will not stop running. Found and fixed on the first visit.</p><div className="card__price">From £79 · no call-out fee</div>
            </article>
            <article className="card">
              <svg className="card__icon" viewBox="0 0 48 48" role="img" aria-label="Flame"><path d="M24 4c3 9 12 13 12 25a12 12 0 0 1-24 0c0-6 3-9 6-12 0 5 3 7 5 7-3-8-1-14 1-20z" fill="#e8590c" /><path d="M24 44a6 6 0 0 1-6-6c0-4 6-6 6-12 4 4 6 8 6 12a6 6 0 0 1-6 6z" fill="#ffb27a" /></svg>
              <h3>Boilers &amp; heating</h3><p>Annual services, repairs and new boilers fitted in a day. We leave the house warm and the floor clean.</p><div className="card__price">Service £85 · new boiler quotes free</div>
            </article>
            <article className="card">
              <svg className="card__icon" viewBox="0 0 48 48" role="img" aria-label="Bathroom tap"><path d="M8 18h20a8 8 0 0 1 8 8v4h-8v-4H8z" fill="#0f2234" /><rect x="4" y="14" width="16" height="6" rx="2" fill="#e8590c" /><path d="M33 36c2 3 3 5 3 7a3 3 0 0 1-6 0c0-2 1-4 3-7z" fill="#e8590c" /></svg>
              <h3>Bathrooms &amp; kitchens</h3><p>Taps, showers, baths and whole rooms. One tradesperson from stripping out to the last bead of sealant.</p><div className="card__price">Free survey · fixed written price</div>
            </article>
          </div>
        </div>
      </section>
      
      <section className="band" aria-labelledby="where-title">
        <div className="wrap">
          <h2 className="sec-title" id="where-title">Find us, or we find you</h2>
          <div className="band__grid">
            <div className="info"><h3>Workshop</h3><p>Unit 6, Canal Wharf Yard<br />Kirkstall Road<br />Leeds LS4 2AB</p></div>
            <div className="info"><h3>Hours</h3><ul className="hours"><li><span>Mon to Fri</span><span>7 am to 9 pm</span></li><li><span>Saturday</span><span>8 am to 6 pm</span></li><li><span>Sunday</span><span>Emergencies</span></li></ul></div>
            <div className="info info--areas"><h3>We cover</h3><ul className="areas"><li>Headingley</li><li>Kirkstall</li><li>Chapel Allerton</li><li>Roundhay</li><li>Armley</li><li>Horsforth</li><li>Pudsey</li><li>City centre</li></ul></div>
          </div>
        </div>
      </section>
      
      <div className="callbar"><div className="wrap"><span>Burst pipe or no heating? Talk to a person now.</span><a href="tel:+441130000000">Call 0113 000 0000</a></div></div>
    </>
  );
}
