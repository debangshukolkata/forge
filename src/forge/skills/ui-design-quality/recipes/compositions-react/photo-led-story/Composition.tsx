// Composition `photo-led-story` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <header className="top">
        <div className="wrap">
          <a className="brand" href="#top"><b>Fernhill Bakery</b><small>Slow-fermented sourdough</small></a>
          <nav aria-label="Main">
            <a href="#menu">Sourdough</a><a href="#menu">Pastries</a><a href="#craft">About</a><a href="#visit">Visit</a>
            <a className="btn" href="#visit">Order</a>
          </nav>
        </div>
      </header>
      
      <main id="top">
      {/* 1. DESIRE (rich): the product to the page edge, the promise on its fade */}
      <section className="hero">
        <div className="hero-copy"><div className="in">
          <p className="eyebrow">Neighbourhood bakery</p>
          <h1>Slow-fermented sourdough, baked fresh daily.</h1>
          <p className="lede">Crisp-crusted loaves and flaky pastries, made with organic flour, long patient fermentation and early-morning baking.</p>
          <a className="btn" href="#menu">View today's bakes <span aria-hidden="true">&rarr;</span></a>
          <ul className="trust">
            <li><svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 19c0-8 6-14 15-14 0 9-6 15-15 14ZM5 19l8-8" /></svg>Organic flour</li>
            <li><svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>Slow fermentation</li>
            <li><svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 21V8M12 12c-4 0-6-2-6-5 4 0 6 2 6 5ZM12 14c4 0 6-2 6-5-4 0-6 2-6 5Z" /></svg>Baked locally</li>
          </ul>
        </div></div>
        <div className="hero-photo" data-slot="Hero photograph: a scored sourdough loaf on a wooden board, warm side light, flour dust, shallow depth of field; landscape, the loaf on the right">
          <svg className="stand" viewBox="0 0 800 520" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Placeholder: a sourdough loaf on a board">
            <rect width="800" height="520" fill="#e8d3b4" /><rect y="360" width="800" height="160" fill="#6b4a2f" /><ellipse cx="470" cy="330" rx="230" ry="130" fill="#a86a32" />
            <ellipse cx="470" cy="300" rx="200" ry="95" fill="#c98b45" /><path d="M340 290c70-50 150-50 260 0" stroke="#f3dcb2" strokeWidth="10" fill="none" strokeLinecap="round" />
            <path d="M380 255c40-24 90-26 150-8" stroke="#f3dcb2" strokeWidth="6" fill="none" strokeLinecap="round" /><circle cx="640" cy="110" r="60" fill="#f1e2c8" /><circle cx="120" cy="420" r="26" fill="#d9c2a0" />
          </svg>
        </div>
      </section>
      
      {/* 2. TRUST (quiet): practical facts, a thin icon, a hairline between them */}
      <section className="facts" aria-label="Opening hours, address and delivery">
        <dl>
          <div className="fact"><svg width={30} height={30} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
            <div><dt>Opening hours</dt><dd>Tuesday to Friday, 7:30 to 3<br />Saturday, 8 to 2</dd></div></div>
          <div className="fact"><svg width={30} height={30} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11Z" /><circle cx="12" cy="10" r="2.5" /></svg>
            <div><dt>Find us</dt><dd>12 Fernhill Road, Oakwood<br /><a className="link" href="#visit">View on map &rarr;</a></dd></div></div>
          <div className="fact"><svg width={30} height={30} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 9h16l-1.500 10h-13L4 9ZM8 9l3-5M16 9l-3-5" /></svg>
            <div><dt>Delivery and pre-orders</dt><dd>Same-day local delivery on orders before 11 am. Pre-order loaves for weekend pick-up.</dd></div></div>
        </dl>
      </section>
      
      {/* 3. EXPLORATION (rich): what is sold, as photographs, not boxes */}
      <section className="menu" id="menu">
        <div className="wrap">
          <div>
            <p className="eyebrow">Our bakes</p>
            <h2>Sourdough and seasonal pastries</h2>
            <p className="intro">Naturally leavened loaves, buttery pastries and bakes that change with the seasons.</p>
            <a className="link" href="#visit">Browse all bakes &rarr;</a>
          </div>
          <ul className="items">
            <li><figure><div className="photo" data-slot="Photo: a sliced sourdough loaf, open crumb, on linen; square">
              <svg className="stand" viewBox="0 0 400 400" role="img" aria-label="Placeholder: a loaf"><rect width="400" height="400" fill="#efe3cf" /><ellipse cx="200" cy="230" rx="150" ry="95" fill="#a86a32" /><ellipse cx="200" cy="205" rx="130" ry="65" fill="#c98b45" /><path d="M110 200c60-30 120-30 180 0" stroke="#f3dcb2" strokeWidth="8" fill="none" strokeLinecap="round" /></svg></div>
              <figcaption><h3>Sourdough loaves</h3><p>Classic, wholegrain and seasonal varieties.</p><a className="link" href="#visit">View breads &rarr;</a></figcaption></figure></li>
            <li><figure><div className="photo" data-slot="Photo: croissants on a baking tray, golden, flaky; square">
              <svg className="stand" viewBox="0 0 400 400" role="img" aria-label="Placeholder: croissants"><rect width="400" height="400" fill="#eadcc6" /><path d="M70 250c30-90 230-90 260 0-60-30-200-30-260 0Z" fill="#c98b45" /><path d="M120 230c20-40 140-40 160 0" stroke="#f3dcb2" strokeWidth="8" fill="none" /><rect y="300" width="400" height="100" fill="#8d8a86" /></svg></div>
              <figcaption><h3>Pastries</h3><p>Croissants, pains au chocolat, cardamom buns and more.</p><a className="link" href="#visit">View pastries &rarr;</a></figcaption></figure></li>
            <li><figure><div className="photo" data-slot="Photo: a fruit danish or seasonal tart, berries, glaze; square">
              <svg className="stand" viewBox="0 0 400 400" role="img" aria-label="Placeholder: a seasonal tart"><rect width="400" height="400" fill="#e6d6bf" /><circle cx="200" cy="200" r="130" fill="#c98b45" /><circle cx="200" cy="200" r="95" fill="#f1e2c8" /><circle cx="165" cy="190" r="22" fill="#a23b3b" /><circle cx="215" cy="175" r="20" fill="#7a2f3f" /><circle cx="225" cy="225" r="22" fill="#a23b3b" /><circle cx="180" cy="230" r="18" fill="#7a2f3f" /></svg></div>
              <figcaption><h3>Seasonal specials</h3><p>Bakes that celebrate the best of the season.</p><a className="link" href="#visit">See what's baking &rarr;</a></figcaption></figure></li>
          </ul>
        </div>
      </section>
      
      {/* 4. CRAFT (dramatic, once): the deep colour changes the subject from what is sold to how it is made */}
      <section className="band" id="craft">
        <div className="words"><div>
          <p className="eyebrow">Our approach</p>
          <h2>Good bread takes time.</h2>
          <p>We use organic flour, long patient fermentation and traditional baking methods to create bread with depth of flavour, a crisp crust and a soft, open crumb.</p>
          <a className="btn light" href="#visit">Our story <span aria-hidden="true">&rarr;</span></a>
        </div></div>
        <div className="photo" data-slot="Photo: a baker's floured hands shaping dough on a wooden bench; landscape; fills the half to its edges">
          <svg className="stand" viewBox="0 0 700 520" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Placeholder: hands shaping dough">
            <rect width="700" height="520" fill="#b99a74" /><rect y="330" width="700" height="190" fill="#8a6a46" /><ellipse cx="360" cy="350" rx="190" ry="85" fill="#efe1c7" />
            <path d="M120 230c60-60 120-40 170 20l-40 40c-40-30-80-40-130-20Z" fill="#d7a87c" /><path d="M590 210c-50-50-110-30-170 30l40 40c40-30 80-40 130-20Z" fill="#c99a6f" />
            <circle cx="560" cy="440" r="14" fill="#f7efe0" /><circle cx="140" cy="450" r="10" fill="#f7efe0" />
          </svg>
        </div>
      </section>
      
      {/* 5. INVITATION (quiet): the shop, one clear action */}
      <section className="band light reverse" id="visit">
        <div className="words"><div>
          <p className="eyebrow">Visit us</p>
          <h2>A neighbourhood bakery.</h2>
          <p>Find us on Fernhill Road in Oakwood. Pop in for fresh bakes, a coffee and a warm welcome.</p>
          <a className="btn" href="#">Get directions <span aria-hidden="true">&rarr;</span></a>
        </div></div>
        <div className="photo" data-slot="Photo: the shop front with the name on the sign, warm lights in the window, plants by the door; landscape">
          <svg className="stand" viewBox="0 0 700 520" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Placeholder: the shop front">
            <rect width="700" height="520" fill="#cfd8c9" /><rect x="60" y="120" width="580" height="330" fill="#2f4a3a" /><rect x="100" y="190" width="220" height="200" fill="#f0d9a8" /><rect x="380" y="190" width="220" height="200" fill="#f0d9a8" />
            <rect x="130" y="140" width="440" height="36" fill="#223a2c" /><rect y="450" width="700" height="70" fill="#b7aa95" /><circle cx="60" cy="430" r="34" fill="#4f7a55" /><circle cx="650" cy="430" r="30" fill="#4f7a55" />
          </svg>
        </div>
      </section>
      </main>
      
      <footer>
        <div className="wrap">
          <div><b>Fernhill Bakery</b><br />Slow-fermented sourdough, pastries and seasonal bakes for the neighbourhood.</div>
          <div>12 Fernhill Road, Oakwood<br />Tuesday to Friday 7:30 to 3, Saturday 8 to 2</div>
        </div>
      </footer>
    </>
  );
}
