// Composition `poster-hero` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="poster" aria-labelledby="poster-title">
        <div className="poster__bar"><b>Night Market</b><span>Fri 14 June · Harbour Yard</span></div>
        <div className="poster__main">
          <span className="sticker">Free entry</span>
          <h1 className="poster__title" id="poster-title"><span>Eat</span><span className="hot">loud</span><span>till late</span></h1>
          <div className="poster__row">
            <p className="poster__lede">Sixty street-food stalls, three stages and a firework finish. Doors at six, last bowl at midnight.</p>
            <a className="btn" href="#tickets">Get your wristband</a>
          </div>
          {/* Drawn art, not a placeholder: concentric sun with rays. Change the shapes to suit the product. */}
          <svg className="poster__art" viewBox="0 0 400 400" role="img" aria-label="A sun with rays over the harbour">
            <g fill="none" stroke="#fff" strokeWidth="3"><circle cx="200" cy="260" r="120" /><circle cx="200" cy="260" r="80" stroke="#e11d48" strokeWidth="10" /></g>
            <g stroke="#ffd400" strokeWidth="8" strokeLinecap="round"><path d="M200 70v40M80 120l28 28M320 120l-28 28M40 260h40M360 260h-40" /></g>
            <path d="M0 330h400v70H0z" fill="#e11d48" /><path d="M0 345c40-14 80-14 120 0s80 14 120 0 80-14 160 0" fill="none" stroke="#fff" strokeWidth="3" />
          </svg>
        </div>
        <div className="strip marquee" aria-hidden="true"><div>Ramen · Tacos · Dumplings · Churros · Skewers · Mochi · Jollof · Ramen · Tacos · Dumplings · Churros · Skewers · Mochi · Jollof</div></div>
      </section>
    </>
  );
}
