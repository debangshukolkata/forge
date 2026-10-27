// Composition `event-lineup` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <header className="hero">
        <div className="wrap">
          <div className="top"><b>Low Tide Live</b><nav aria-label="Sections"><a href="#schedule">Schedule</a><a href="#acts">Artists</a><a href="#tickets">Tickets</a><a href="#venue">Venue</a></nav></div>
          <div className="hero__in">
            <p className="hero__date">Sat 20 September · Gates 2 pm</p>
            <h1 className="hero__title"><span>Low tide</span><span className="hot">live</span></h1>
            <p className="hero__lede">One day, two stages and eleven acts on the old ferry pier. Come for the sunset set, stay for the last boat home.</p>
            <div className="hero__cta"><a className="btn" href="#tickets">Get tickets</a><a className="btn btn--line" href="#schedule">See the day</a></div>
          </div>
        </div>
        {/* Drawn scene: stage with truss and lights, crowd silhouettes. Redraw it for the event you are building. */}
        <svg className="hero__scene" viewBox="0 0 1200 300" preserveAspectRatio="xMidYMax slice" role="img" aria-label="A lit stage with a crowd in front">
          <defs><linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ff4d6d" stopOpacity=".55" /><stop offset="1" stopColor="#ff4d6d" stopOpacity="0" /></linearGradient></defs>
          <g fill="url(#beam)"><path d="M330 70 L210 260 L450 260z" /><path d="M600 70 L500 260 L700 260z" /><path d="M870 70 L750 260 L990 260z" /></g>
          <g fill="#241b38" stroke="#3a3150" strokeWidth="2"><rect x="250" y="60" width="700" height="14" /><rect x="262" y="60" width="10" height="200" /><rect x="928" y="60" width="10" height="200" /><rect x="250" y="200" width="700" height="60" /></g>
          <g fill="#ff4d6d"><circle cx="330" cy="82" r="9" /><circle cx="600" cy="82" r="9" /><circle cx="870" cy="82" r="9" /></g>
          <g fill="#0e0b16"><path d="M580 200v-36a20 20 0 0 1 40 0v36z" /><circle cx="600" cy="140" r="14" /></g>
          <g fill="#0e0b16">
            <circle cx="60" cy="236" r="14" /><path d="M36 300v-40a24 24 0 0 1 48 0v40z" />
            <circle cx="150" cy="226" r="15" /><path d="M124 300v-48a26 26 0 0 1 52 0v48z" />
            <circle cx="240" cy="244" r="13" /><path d="M218 300v-34a22 22 0 0 1 44 0v34z" />
            <circle cx="330" cy="232" r="14" /><path d="M306 300v-44a24 24 0 0 1 48 0v44z" />
            <circle cx="430" cy="246" r="13" /><path d="M408 300v-32a22 22 0 0 1 44 0v32z" />
            <circle cx="520" cy="228" r="15" /><path d="M494 300v-46a26 26 0 0 1 52 0v46z" />
            <circle cx="640" cy="240" r="14" /><path d="M616 300v-38a24 24 0 0 1 48 0v38z" />
            <circle cx="740" cy="226" r="15" /><path d="M714 300v-48a26 26 0 0 1 52 0v48z" />
            <circle cx="840" cy="244" r="13" /><path d="M818 300v-34a22 22 0 0 1 44 0v34z" />
            <circle cx="940" cy="230" r="14" /><path d="M916 300v-44a24 24 0 0 1 48 0v44z" />
            <circle cx="1040" cy="242" r="14" /><path d="M1016 300v-36a24 24 0 0 1 48 0v36z" />
            <circle cx="1140" cy="228" r="15" /><path d="M1114 300v-46a26 26 0 0 1 52 0v46z" />
          </g>
          <g stroke="#f6f3fb" strokeWidth="4" strokeLinecap="round"><path d="M150 205v-26M740 203v-30M1140 205v-24" /></g>
        </svg>
      </header>
      
      <main>
      <section className="sec" id="schedule">
        <div className="wrap">
          <p className="eyebrow">Saturday 20 September</p>
          <h2 className="h2">The day, hour by hour</h2>
          <ol className="sched">
            <li className="slot"><span className="slot__time">14:00</span><p className="slot__what">Gates open<span className="slot__who">Food yard and record fair start</span></p><span className="track">Pier</span></li>
            <li className="slot"><span className="slot__time">15:00</span><p className="slot__what">Mara Quill<span className="slot__who">Folk songs for slow water</span></p><span className="track">Boat stage</span></li>
            <li className="slot"><span className="slot__time">16:30</span><p className="slot__what">The Paper Kites Club<span className="slot__who">Jangle pop, nine players</span></p><span className="track track--main">Main stage</span></li>
            <li className="slot"><span className="slot__time">18:00</span><p className="slot__what">Dj Okoro<span className="slot__who">Afrobeat sunset set</span></p><span className="track track--main">Main stage</span></li>
            <li className="slot"><span className="slot__time">20:00</span><p className="slot__what">Static Harbour<span className="slot__who">Headline show, lights and all</span></p><span className="track track--main">Main stage</span></li>
            <li className="slot"><span className="slot__time">22:30</span><p className="slot__what">Last boat home<span className="slot__who">Free ferry to the north shore</span></p><span className="track">Pier</span></li>
          </ol>
        </div>
      </section>
      
      <section className="sec" id="acts">
        <div className="wrap">
          <p className="eyebrow">On the bill</p>
          <h2 className="h2">Meet the acts</h2>
          <div className="cards">
            <article className="act">
              <svg viewBox="0 0 300 180" role="img" aria-label="A singer with a guitar against a pink moon"><rect width="300" height="180" fill="#2a1c3f" /><circle cx="215" cy="70" r="44" fill="#ff4d6d" /><circle cx="130" cy="78" r="18" fill="#0e0b16" /><path d="M100 180v-52a30 30 0 0 1 60 0v52z" fill="#0e0b16" /><path d="M140 150l56-34" stroke="#f6f3fb" strokeWidth="5" strokeLinecap="round" /><ellipse cx="205" cy="124" rx="16" ry="11" fill="#f6f3fb" transform="rotate(-30 205 124)" /></svg>
              <h3>Mara Quill</h3><p>Folk songs for slow water. Three voices, one borrowed guitar.</p><p className="when">15:00 · Boat stage</p>
            </article>
            <article className="act">
              <svg viewBox="0 0 300 180" role="img" aria-label="A drummer behind a kit under a red light"><rect width="300" height="180" fill="#1d2a3f" /><path d="M150 0L60 180h180z" fill="#ff4d6d" opacity=".25" /><circle cx="150" cy="70" r="16" fill="#0e0b16" /><path d="M122 180v-58a28 28 0 0 1 56 0v58z" fill="#0e0b16" /><ellipse cx="80" cy="130" rx="34" ry="8" fill="none" stroke="#f6f3fb" strokeWidth="4" /><ellipse cx="225" cy="124" rx="34" ry="8" fill="none" stroke="#f6f3fb" strokeWidth="4" /><path d="M80 138v42M225 132v48" stroke="#f6f3fb" strokeWidth="3" /></svg>
              <h3>Paper Kites Club</h3><p>Jangle pop from nine players who rehearse in a bakery.</p><p className="when">16:30 · Main stage</p>
            </article>
            <article className="act">
              <svg viewBox="0 0 300 180" role="img" aria-label="A DJ at decks with sound waves"><rect width="300" height="180" fill="#2f1a2a" /><g fill="none" stroke="#ff4d6d" strokeWidth="4"><path d="M40 60q20-20 40 0t40 0 40 0 40 0 40 0" /><path d="M40 90q20-20 40 0t40 0 40 0 40 0 40 0" opacity=".6" /></g><circle cx="150" cy="104" r="14" fill="#0e0b16" /><path d="M126 150v-26a24 24 0 0 1 48 0v26z" fill="#0e0b16" /><rect x="60" y="148" width="180" height="32" fill="#0e0b16" /><circle cx="105" cy="164" r="11" fill="none" stroke="#f6f3fb" strokeWidth="3" /><circle cx="195" cy="164" r="11" fill="none" stroke="#f6f3fb" strokeWidth="3" /></svg>
              <h3>Dj Okoro</h3><p>Afrobeat and highlife, timed to the sun going down.</p><p className="when">18:00 · Main stage</p>
            </article>
            <article className="act">
              <svg viewBox="0 0 300 180" role="img" aria-label="A band silhouette in front of a wall of light"><rect width="300" height="180" fill="#ff4d6d" /><g fill="#0e0b16"><circle cx="90" cy="84" r="14" /><path d="M64 180v-50a26 26 0 0 1 52 0v50z" /><circle cx="150" cy="70" r="15" /><path d="M122 180v-62a28 28 0 0 1 56 0v62z" /><circle cx="212" cy="84" r="14" /><path d="M186 180v-50a26 26 0 0 1 52 0v50z" /></g><g stroke="#f6f3fb" strokeWidth="3" opacity=".7"><path d="M20 20v30M70 10v40M130 8v34M190 8v34M250 14v40" /></g></svg>
              <h3>Static Harbour</h3><p>The headline set: synths, a choir and a very large lamp.</p><p className="when">20:00 · Main stage</p>
            </article>
          </div>
        </div>
      </section>
      
      <section className="sec" id="tickets">
        <div className="wrap">
          <p className="eyebrow">Tickets</p>
          <h2 className="h2">Pick your spot</h2>
          <div className="tiers">
            <article className="tier"><h3 className="tier__name">General</h3><p className="tier__price">£45</p><ul><li>Entry from 2 pm</li><li>Both stages</li><li>Free ferry home</li></ul><a className="btn btn--line" href="#">Buy general</a></article>
            <article className="tier tier--hot"><h3 className="tier__name">Front of stage</h3><p className="tier__price">£80</p><ul><li>Everything in General</li><li>Barrier access, main stage</li><li>Fast lane at the gates</li><li>One free drink</li></ul><a className="btn" href="#">Buy front of stage</a></article>
            <article className="tier"><h3 className="tier__name">Pier pass</h3><p className="tier__price">£140</p><ul><li>Everything above</li><li>Seats on the upper deck</li><li>Dinner from the food yard</li></ul><a className="btn btn--line" href="#">Buy pier pass</a></article>
          </div>
        </div>
      </section>
      
      <section className="sec" id="venue">
        <div className="wrap venue">
          <div className="venue__card">
            <p className="eyebrow">Where</p>
            <address>Old Ferry Pier<br />14 Customs Quay<br />Harbourton HT1 4QA</address>
            <dl><dt>Train</dt><dd>Harbourton, 8 minutes' walk</dd><dt>Bus</dt><dd>Route 12 to Customs Quay</dd><dt>Bikes</dt><dd>Free valet at the north gate</dd></dl>
            <a className="btn" href="#">Open in maps</a>
          </div>
          <svg viewBox="0 0 480 320" role="img" aria-label="A simple map: the pier jutting into the water with the station inland">
            <rect width="480" height="320" fill="#181325" /><path d="M0 190q120-40 240-10t240-20v160H0z" fill="#1d2a3f" />
            <g stroke="#3a3150" strokeWidth="10" fill="none"><path d="M0 90h480M120 0v200M340 0v170" /></g>
            <path d="M232 168v90h28v-90z" fill="#ff4d6d" /><circle cx="246" cy="150" r="12" fill="#ff4d6d" /><circle cx="246" cy="150" r="5" fill="#0e0b16" />
            <rect x="104" y="66" width="32" height="48" fill="#f6f3fb" /><path d="M110 82h20" stroke="#0e0b16" strokeWidth="4" />
            <path d="M120 114L240 150" stroke="#f6f3fb" strokeWidth="3" strokeDasharray="6 6" fill="none" />
          </svg>
        </div>
      </section>
      </main>
      <footer className="wrap foot"><span>Low Tide Live · Harbourton Council licence 2291</span><span>hello@lowtide.example</span></footer>
    </>
  );
}
