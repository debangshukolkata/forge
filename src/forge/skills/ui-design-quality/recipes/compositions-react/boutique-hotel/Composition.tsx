// Composition `boutique-hotel` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <header className="hero">
        {/* Drawn dusk scene: a whitewashed hotel on a headland above the sea. */}
        <svg className="hero__art" viewBox="0 0 1440 800" preserveAspectRatio="xMidYMid slice" role="img" aria-label="A white hotel with lit windows on a headland at dusk, the sea below">
          <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#0b2a2e" /><stop offset=".55" stopColor="#1f5a5c" /><stop offset=".85" stopColor="#e8b774" /></linearGradient><linearGradient id="sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2d6f6e" /><stop offset="1" stopColor="#0b2a2e" /></linearGradient></defs>
          <rect width="1440" height="800" fill="url(#sky)" />
          <circle cx="1080" cy="520" r="90" fill="#f5cf8f" opacity=".9" />
          <g fill="#f6efe3" opacity=".8"><circle cx="200" cy="90" r="2" /><circle cx="420" cy="160" r="2" /><circle cx="700" cy="70" r="2" /><circle cx="900" cy="150" r="2" /><circle cx="1260" cy="100" r="2" /><circle cx="560" cy="250" r="1.5" /></g>
          <rect y="560" width="1440" height="240" fill="url(#sea)" />
          <g stroke="#f5cf8f" strokeWidth="3" opacity=".5" strokeLinecap="round"><path d="M1010 590h140M1030 612h100M1050 634h60" /></g>
          <path d="M700 800V640c60-40 130-70 230-76 90-4 150 20 230 6 80-16 160-8 280 30V800z" fill="#07201f" />
          <g transform="translate(800 440)"><rect width="320" height="130" fill="#f1e8d6" /><rect x="40" y="-60" width="170" height="60" fill="#e6dac1" /><path d="M30 -60h190l-16 -22h-158z" fill="#b5532f" /><path d="M-10 0h340l-10 -18h-320z" fill="#b5532f" />
            <g fill="#f5cf8f"><rect x="24" y="30" width="26" height="40" /><rect x="76" y="30" width="26" height="40" /><rect x="128" y="30" width="26" height="40" /><rect x="180" y="30" width="26" height="40" /><rect x="232" y="30" width="26" height="40" /><rect x="284" y="30" width="22" height="40" /><rect x="70" y="-42" width="22" height="30" /><rect x="118" y="-42" width="22" height="30" /><rect x="166" y="-42" width="22" height="30" /></g>
            <rect x="132" y="86" width="40" height="44" fill="#0e5a58" /></g>
          <path d="M0 800V700c120-30 260-50 420-40v140z" fill="#07201f" />
        </svg>
        <div className="hero__nav"><a className="hero__brand" href="#">Hotel Marea</a><nav className="hero__links" aria-label="Main"><a href="#rooms">Rooms</a><a href="#stay">The stay</a><a href="#find">Find us</a></nav></div>
        <div className="hero__body"><small>Eleven rooms above the harbour</small><h1>Sleep to the sound of the tide</h1><p>A small whitewashed hotel on the headland at Porto Alvo. Breakfast on the terrace, supper from the sea.</p></div>
        <form className="book" action="#rooms" method="get" aria-label="Check availability">
          <label>Arrive<input type="date" name="arrive" defaultValue="2026-06-12" /></label>
          <label>Depart<input type="date" name="depart" defaultValue="2026-06-15" /></label>
          <label>Guests<select name="guests"><option>2 adults</option><option>1 adult</option><option>2 adults, 1 child</option></select></label>
          <button type="submit">Check rooms</button>
        </form>
      </header>
      
      <section className="section" id="rooms" aria-labelledby="rooms-title">
        <div className="wrap">
          <p className="kicker">Rooms</p>
          <h2 className="section__title" id="rooms-title">Three ways to wake up</h2>
          <article className="room">
            <svg className="room__art" viewBox="0 0 560 380" role="img" aria-label="A window onto the sea beside a bed"><rect width="560" height="380" fill="#e3d3b5" /><rect x="170" y="40" width="220" height="210" fill="#2d6f6e" /><rect x="170" y="150" width="220" height="100" fill="#0e5a58" /><circle cx="330" cy="100" r="26" fill="#f5cf8f" /><path d="M170 40h220v210H170zM280 40v210" fill="none" stroke="#f6efe3" strokeWidth="10" /><rect x="60" y="250" width="440" height="40" rx="6" fill="#f6efe3" /><rect x="60" y="290" width="440" height="50" fill="#12302f" /><rect x="80" y="226" width="110" height="34" rx="12" fill="#fff" /></svg>
            <div><h3>Harbour Room</h3><p>Our smallest room, with a tall window over the fishing boats and a bed made up in linen. Quiet after ten.</p><div className="room__meta"><span><strong>€210</strong> per night</span><span>22 m²</span><span>Double bed</span></div></div>
          </article>
          <article className="room">
            <svg className="room__art" viewBox="0 0 560 380" role="img" aria-label="A terrace with a table and two chairs facing the sea"><rect width="560" height="380" fill="#0b2a2e" /><rect y="200" width="560" height="180" fill="#2d6f6e" /><circle cx="420" cy="170" r="42" fill="#f5cf8f" /><rect y="250" width="560" height="130" fill="#e3d3b5" /><ellipse cx="220" cy="270" rx="70" ry="14" fill="#12302f" /><rect x="214" y="270" width="12" height="60" fill="#12302f" /><path d="M110 330v-70h24v70M306 330v-70h24v70" stroke="#b5532f" strokeWidth="10" /><path d="M0 250h560" stroke="#f6efe3" strokeWidth="8" /></svg>
            <div><h3>Terrace Suite</h3><p>A bedroom, a sitting room and a private terrace with a table for two. Breakfast is brought up on a tray.</p><div className="room__meta"><span><strong>€340</strong> per night</span><span>38 m²</span><span>King bed</span></div></div>
          </article>
          <article className="room">
            <svg className="room__art" viewBox="0 0 560 380" role="img" aria-label="A roof lantern and a freestanding bath under a sloping ceiling"><rect width="560" height="380" fill="#12302f" /><path d="M0 380V110l280-80 280 80v270z" fill="#1f5a5c" /><path d="M200 110l80-24 80 24" fill="none" stroke="#e8b774" strokeWidth="6" /><circle cx="280" cy="140" r="24" fill="#f5cf8f" /><rect x="160" y="250" width="240" height="64" rx="32" fill="#f6efe3" /><rect x="150" y="238" width="260" height="22" rx="11" fill="#fff" /><path d="M200 314l-14 30M360 314l14 30" stroke="#e8b774" strokeWidth="8" strokeLinecap="round" /></svg>
            <div><h3>The Lantern Loft</h3><p>Under the roof, with a sloping ceiling, a freestanding bath and the best view of the evening light.</p><div className="room__meta"><span><strong>€420</strong> per night</span><span>46 m²</span><span>King bed, bath</span></div></div>
          </article>
        </div>
      </section>
      
      <section className="section amen" id="stay" aria-labelledby="stay-title">
        <div className="wrap">
          <p className="kicker">The stay</p>
          <h2 className="section__title" id="stay-title">Small things done well</h2>
          <div className="amen__cols">
            <div><h3>Breakfast</h3><p>Warm bread, local honey and eggs from the farm up the hill, served from 8 to 11 on the terrace.</p></div>
            <div><h3>Supper</h3><p>One short menu each night, built around the morning's catch. Please reserve by noon.</p></div>
            <div><h3>The water</h3><p>Steps lead to a cove of smooth stones. Towels, masks and kayaks are kept by the gate.</p></div>
            <div><h3>The quiet</h3><p>No television in the rooms and no music by the pool. Books and board games fill the library.</p></div>
          </div>
        </div>
      </section>
      
      <section className="section guest" aria-label="Guest quote">
        <div className="wrap"><blockquote><p>We came for two nights and stayed for six. I have never slept so well, or eaten so slowly.</p><cite>Elena and Marc, guests in June</cite></blockquote></div>
      </section>
      
      <section className="section" id="find" aria-labelledby="find-title">
        <div className="wrap">
          <p className="kicker">Find us</p>
          <h2 className="section__title" id="find-title">Porto Alvo, above the harbour</h2>
          <div className="addr">
            <div className="addr__card"><h3>Address</h3><p>Rua do Farol 7<br />Porto Alvo 8600<br />Portugal</p></div>
            <div className="addr__card"><h3>Arriving</h3><p>Forty minutes from Faro airport by taxi. Check in from 15:00, check out by 11:00.</p></div>
            <div className="addr__card"><h3>Reservations</h3><p>reservas@hotelmarea.example<br />+351 282 555 014<br />Daily 8:00 to 20:00</p></div>
          </div>
          <footer className="foot"><span>Hotel Marea · Rua do Farol 7 · Porto Alvo</span><span>Open March to November</span></footer>
        </div>
      </section>
    </>
  );
}
