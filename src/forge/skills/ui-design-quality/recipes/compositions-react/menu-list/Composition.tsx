// Composition `menu-list` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="menu" aria-labelledby="menu-title">
        <div className="menu__head">
          <h1 className="menu__title" id="menu-title"><small>Kuro · the short menu</small>Four bowls,<br />no more</h1>
          {/* Drawn bowl with steam: not a placeholder. */}
          <svg className="menu__bowl" viewBox="0 0 160 140" role="img" aria-label="A steaming bowl of ramen">
            <g fill="none" stroke="#d9a441" strokeWidth="3" strokeLinecap="round"><path d="M50 30c-10-12 10-18 0-30M80 34c-10-12 10-18 0-30M110 30c-10-12 10-18 0-30" /></g>
            <path d="M12 62h136c0 44-30 70-68 70S12 106 12 62z" fill="#e0432f" /><path d="M12 62h136" stroke="#f2e8d8" strokeWidth="5" />
            <path d="M40 62c10-14 30-14 40 0M70 62c10-14 30-14 40 0" fill="none" stroke="#f2e8d8" strokeWidth="4" /><circle cx="118" cy="66" r="9" fill="#d9a441" />
          </svg>
        </div>
        <div className="menu__cols">
          <div>
            <h3>Bowls</h3>
            <div className="dish"><span className="dish__no">01</span><span className="dish__name">Shoyu</span><span className="dish__price">¥980</span><p>Clear soy broth, chicken oil, thin noodles, a soft egg.</p></div>
            <div className="dish"><span className="dish__no">02</span><span className="dish__name">Tonkotsu</span><span className="dish__price">¥1,100</span><p>Twelve-hour pork broth, black garlic, firm noodles.</p></div>
          </div>
          <div>
            <h3>Bowls, continued</h3>
            <div className="dish"><span className="dish__no">03</span><span className="dish__name">Spicy miso</span><span className="dish__price">¥1,150</span><p>Red miso, chilli oil, corn and butter for the long night.</p></div>
            <div className="dish"><span className="dish__no">04</span><span className="dish__name">Cold sesame</span><span className="dish__price">¥1,000</span><p>Chilled noodles, sesame tare, cucumber. Summer only.</p></div>
          </div>
        </div>
        <p className="menu__foot">Prices include tax. Extra egg ¥150, extra noodles ¥100. Cash and IC cards only.</p>
      </section>
    </>
  );
}
