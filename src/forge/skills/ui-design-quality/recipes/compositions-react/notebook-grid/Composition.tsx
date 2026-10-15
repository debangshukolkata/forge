// Composition `notebook-grid` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="nb" aria-labelledby="nb-title">
        <h1 className="nb__title" id="nb-title">Try it, <mark>break</mark> it, ask why</h1>
        <p className="nb__lede">Three hands-on labs this month, built for kids aged 4 to 10 and the grown-ups who get dragged in.</p>
        <div className="nb__note">Bring wellies!
          <svg viewBox="0 0 90 70" aria-hidden="true"><path d="M6 8c30 0 60 10 70 48" fill="none" stroke="#c2410c" strokeWidth="3" strokeDasharray="6 6" strokeLinecap="round" /><path d="M62 50l14 10 4-16" fill="none" stroke="#c2410c" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </div>
        <div className="cards">
          <article className="card"><p className="card__tag">Lab 01 · Water</p><h3>Make a river</h3><p>Dig channels, build dams and watch where the water goes when you change your mind.</p><p className="card__meta">Sat 10:00 · ages 4 to 7</p></article>
          <article className="card"><p className="card__tag">Lab 02 · Air</p><h3>Fly a rocket</h3><p>Fold, tape, launch. Then fold it a different way and see whether it goes further.</p><p className="card__meta">Sat 13:00 · ages 6 to 10</p></article>
          <article className="card"><p className="card__tag">Lab 03 · Light</p><h3>Catch a rainbow</h3><p>Prisms, mirrors and one very dark tent. Bring a torch and a bad idea.</p><p className="card__meta">Sun 11:00 · ages 5 to 9</p></article>
        </div>
        <a className="btn" href="#labs">Save my place</a>
      </section>
    </>
  );
}
