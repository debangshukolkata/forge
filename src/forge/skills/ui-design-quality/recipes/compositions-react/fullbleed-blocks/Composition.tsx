// Composition `fullbleed-blocks` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="band band--blue"><div className="band__no" aria-hidden="true">01</div><div className="band__body"><p className="band__label">Listen</p><h1>Listen first. Then draw.</h1><p>No questionnaires. We watch who comes in, what they ask for and what they walk past.</p><a className="arrow" href="#work">See what we found →</a></div></section>
      <section className="band band--hot band--flip"><div className="band__no" aria-hidden="true">02</div><div className="band__body"><p className="band__label">Make</p><h2>Then we draw the smallest thing that works.</h2><p>A sign, a menu, a one-page site. Built in days, tested on the street, thrown away if it fails.</p></div></section>
      <section className="band band--dark"><div className="band__no" aria-hidden="true">03</div><div className="band__body"><p className="band__label">Keep</p><h2>You keep the files, the fonts and the reasons.</h2><p>Everything we make comes with the why, so the next person can carry it on without us.</p><a className="arrow" href="#contact">Start a conversation →</a></div></section>
    </>
  );
}
