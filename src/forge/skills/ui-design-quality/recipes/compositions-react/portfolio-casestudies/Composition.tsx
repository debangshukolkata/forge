// Composition `portfolio-casestudies` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <div className="wrap">
        <div className="top"><b>Ines Varga</b><nav aria-label="Sections"><a href="#work">Work</a><a href="#cases">Cases</a><a href="#about">About</a><a href="#contact">Contact</a></nav></div>
        <header className="intro">
          <p className="intro__kicker">Brand and editorial designer · Lisbon</p>
          <h1 className="intro__title">Quiet design for <em>loud</em> small businesses.</h1>
          <p className="intro__lede">Twelve years of identities, packaging and print for bakeries, bookshops and the people who run them. Selected work, 2019 to now.</p>
        </header>
      </div>
      
      <main>
      <section className="sec" id="work">
        <div className="wrap">
          <h2 className="h2">Selected work</h2>
          <div className="work">
            <figure className="tile">
              <svg viewBox="0 0 400 520" role="img" aria-label="A poster with a large orange circle and a tall black bar"><rect width="400" height="520" fill="#ebe7df" /><circle cx="200" cy="190" r="120" fill="#d9480f" /><rect x="60" y="330" width="280" height="14" fill="#141414" /><rect x="60" y="360" width="190" height="14" fill="#141414" /><rect x="60" y="440" width="60" height="6" fill="#141414" /></svg>
              <figcaption>Forno Lume poster <span>Print</span></figcaption>
            </figure>
            <figure className="tile">
              <svg viewBox="0 0 400 280" role="img" aria-label="A wide logo lockup of stacked lines on black"><rect width="400" height="280" fill="#141414" /><g fill="none" stroke="#f4f2ee" strokeWidth="6"><path d="M80 90h240M80 130h240M80 170h140" /></g><circle cx="300" cy="190" r="22" fill="#d9480f" /></svg>
              <figcaption>Linha Books identity <span>Brand</span></figcaption>
            </figure>
            <figure className="tile">
              <svg viewBox="0 0 400 400" role="img" aria-label="Packaging: three boxes with a diagonal stripe"><rect width="400" height="400" fill="#d6d1c6" /><g stroke="#141414" strokeWidth="4"><path d="M70 150l70-40 70 40v110l-70 40-70-40z" fill="#f4f2ee" /><path d="M70 150l70 40 70-40M140 190v110" fill="none" /><path d="M210 190l60-34 60 34v94l-60 34-60-34z" fill="#d9480f" /><path d="M210 190l60 34 60-34M270 224v94" fill="none" /></g></svg>
              <figcaption>Casa Cacau packaging <span>Packaging</span></figcaption>
            </figure>
            <figure className="tile">
              <svg viewBox="0 0 400 600" role="img" aria-label="A tall book cover with a drawn horizon and sun"><rect width="400" height="600" fill="#f4f2ee" stroke="#141414" strokeWidth="4" /><rect x="30" y="30" width="340" height="540" fill="#141414" /><path d="M30 400h340v170H30z" fill="#2c2c2c" /><circle cx="200" cy="340" r="64" fill="#d9480f" /><path d="M30 400h340" stroke="#f4f2ee" strokeWidth="3" /><g fill="#f4f2ee"><rect x="70" y="80" width="200" height="12" /><rect x="70" y="106" width="130" height="12" /></g></svg>
              <figcaption>"Salt Road" book jacket <span>Editorial</span></figcaption>
            </figure>
            <figure className="tile">
              <svg viewBox="0 0 400 300" role="img" aria-label="A website layout with a header bar, a headline block and three small cards"><rect width="400" height="300" fill="#ebe7df" /><rect x="24" y="24" width="352" height="252" fill="#f4f2ee" stroke="#141414" strokeWidth="3" /><rect x="24" y="24" width="352" height="26" fill="#141414" /><rect x="48" y="76" width="200" height="22" fill="#141414" /><rect x="48" y="108" width="140" height="22" fill="#d9480f" /><g fill="none" stroke="#141414" strokeWidth="3"><rect x="48" y="170" width="96" height="80" /><rect x="152" y="170" width="96" height="80" /><rect x="256" y="170" width="96" height="80" /></g></svg>
              <figcaption>Mercado do Bairro site <span>Web</span></figcaption>
            </figure>
            <figure className="tile">
              <svg viewBox="0 0 400 460" role="img" aria-label="A grid of repeating pattern tiles in black, cream and orange"><rect width="400" height="460" fill="#f4f2ee" /><g fill="#141414"><circle cx="100" cy="100" r="60" /><rect x="220" y="40" width="120" height="120" /><path d="M40 260h120v120z" /></g><g fill="#d9480f"><circle cx="280" cy="320" r="60" /></g><path d="M200 400h160" stroke="#141414" strokeWidth="6" /></svg>
              <figcaption>Azulejo pattern set <span>Pattern</span></figcaption>
            </figure>
          </div>
        </div>
      </section>
      
      <section className="sec" id="cases">
        <div className="wrap">
          <h2 className="h2">Case studies</h2>
          <div className="cases">
            <article className="case"><span className="case__no">01</span><h3>Forno Lume: a bakery that sells out by nine</h3><p>New name, shop sign and bag, drawn to be seen from across a busy street.</p><div className="case__result"><b>+38%</b>morning walk-ins in the first quarter</div><a href="#">Read the case</a></article>
            <article className="case"><span className="case__no">02</span><h3>Linha Books: from one shelf to a reading club</h3><p>An identity that works as a stamp, a tote bag and a monthly zine cover.</p><div className="case__result"><b>420</b>club members signed up in six months</div><a href="#">Read the case</a></article>
            <article className="case"><span className="case__no">03</span><h3>Casa Cacau: packaging that ships flat</h3><p>One folded sheet replaced three boxes, with no glue and no plastic.</p><div className="case__result"><b>-22%</b>on postage and zero returns for damage</div><a href="#">Read the case</a></article>
          </div>
        </div>
      </section>
      
      <section className="sec" id="about">
        <div className="wrap about">
          <svg viewBox="0 0 200 240" role="img" aria-label="A drawn portrait: a head and shoulders in simple black and orange shapes"><rect width="200" height="240" fill="#ebe7df" /><circle cx="100" cy="92" r="44" fill="#141414" /><path d="M30 240v-30a70 56 0 0 1 140 0v30z" fill="#141414" /><path d="M64 78a40 40 0 0 1 72 0z" fill="#d9480f" /></svg>
          <div><p>I work alone, with a small circle of printers and developers I trust. One project at a time, so every client gets the whole of my attention.</p><small>Based in Lisbon · booking from January</small></div>
        </div>
      </section>
      
      <section className="contact" id="contact">
        <div className="wrap"><p>Start a project</p><a href="mailto:hello@inesvarga.example">hello@inesvarga.example</a><small>Replies within two working days · Studio visits by appointment</small></div>
      </section>
      </main>
    </>
  );
}
