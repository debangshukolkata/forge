// Composition `ticket-stub` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="tickets" aria-labelledby="tickets-title">
        <div className="tickets__head"><h1 className="tickets__title" id="tickets-title">Pick your<br />ticket</h1><p className="tickets__note">Under-twos are free. Every ticket includes the planetarium show and a go on the water wall.</p></div>
        <div className="row">
          <article className="ticket"><div className="ticket__main"><p className="ticket__kind">Child · 3 to 15</p><p className="ticket__price"><small>£</small>8</p><ul className="ticket__list"><li>All four galleries</li><li>One planetarium show</li></ul></div><div className="ticket__stub"><span>Admit one</span><span>No. 0001</span></div></article>
          <article className="ticket ticket--best"><div className="ticket__main"><p className="ticket__kind">Family · 2 adults + 3 kids</p><p className="ticket__price"><small>£</small>29</p><ul className="ticket__list"><li>Everything, all day</li><li>Free return visit in 30 days</li></ul></div><div className="ticket__stub"><span>Best value</span><span>No. 0002</span></div></article>
          <article className="ticket"><div className="ticket__main"><p className="ticket__kind">Adult · 16+</p><p className="ticket__price"><small>£</small>11</p><ul className="ticket__list"><li>All four galleries</li><li>Quiet hour on Sundays</li></ul></div><div className="ticket__stub"><span>Admit one</span><span>No. 0003</span></div></article>
        </div>
        <a className="btn" href="#book">Book a time slot</a>
      </section>
    </>
  );
}
