// Composition `wellness-retreat` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <div className="bar"><span className="bar__brand">Still Water Studio</span><nav className="bar__nav"><span>Classes</span><span>The day</span><span>Teachers</span></nav></div>
          <div className="hero__text">
            <p className="hero__eyebrow">Yoga &amp; stillness · Hobart</p>
            <h1 className="hero__title">Slow down. Breathe out. Begin again.</h1>
            <p className="hero__lead">Small morning classes, warm rooms and teachers who never rush you. Your first week is on us.</p>
            <a className="btn" href="#book">Book a free first week</a>
          </div>
        </div>
        {/* Drawn sun over soft hills: not a placeholder. */}
        <svg className="hero__art" viewBox="0 0 1200 260" preserveAspectRatio="xMidYMax slice" role="img" aria-label="A low sun over layered green hills">
          <circle cx="600" cy="150" r="96" fill="#f2b98a" /><circle cx="600" cy="150" r="136" fill="#f2b98a" opacity=".25" />
          <path d="M0 190c140-60 280-70 420-30s260 30 400-20 260-30 380 20v100H0z" fill="#a9c2ac" />
          <path d="M0 220c180-50 300-40 460-10s300 20 460-20 200-10 280 10v60H0z" fill="#6f9a82" />
          <path d="M0 250c200-30 380-20 600 0s420 10 600-14v24H0z" fill="#3f6b57" />
        </svg>
      </section>
      
      <section className="steps" aria-labelledby="steps-title">
        <div className="wrap">
          <h2 className="sec-title" id="steps-title">How a day goes</h2>
          <p className="sec-lead">No timetable to decode. Come for one part or stay for all four.</p>
          <ol className="steps__list">
            <li className="step"><div className="step__no">1</div><div className="step__time">6:30 am</div><h3>Arrive</h3><p>Tea in the garden room while the floors warm. Leave your shoes and your inbox at the door.</p></li>
            <li className="step"><div className="step__no">2</div><div className="step__time">7:00 am</div><h3>Move</h3><p>An hour of slow flow, with options for every body and every kind of stiff Tuesday.</p></li>
            <li className="step"><div className="step__no">3</div><div className="step__time">8:15 am</div><h3>Rest</h3><p>Twenty minutes of guided stillness under blankets. Most people fall asleep. That is allowed.</p></li>
            <li className="step"><div className="step__no">4</div><div className="step__time">9:00 am</div><h3>Eat</h3><p>Porridge, stewed fruit and good coffee at the long table, then back out into the day.</p></li>
          </ol>
        </div>
      </section>
      
      <section className="team" aria-labelledby="team-title">
        <div className="wrap">
          <h2 className="sec-title" id="team-title">Your teachers</h2>
          <p className="sec-lead">Three people, one idea: you should feel better when you leave than when you came in.</p>
          <div className="team__grid">
            <article className="person">
              <svg className="person__avatar" viewBox="0 0 120 120" role="img" aria-label="Drawn portrait of Mara"><circle cx="60" cy="60" r="60" fill="#f2d8bd" /><path d="M22 104c4-26 20-34 38-34s34 8 38 34a60 60 0 0 1-76 0z" fill="#3f6b57" /><circle cx="60" cy="48" r="20" fill="#c98b62" /><path d="M38 46c0-22 16-28 28-24 12 2 18 12 16 26-6-12-14-14-22-14s-16 2-22 12z" fill="#2b3a33" /></svg>
              <h3>Mara Ellison</h3><div className="person__role">Founder · Vinyasa</div><p>Twenty years on the mat. Teaches the early class and bakes the bread.</p>
            </article>
            <article className="person">
              <svg className="person__avatar" viewBox="0 0 120 120" role="img" aria-label="Drawn portrait of Tomasz"><circle cx="60" cy="60" r="60" fill="#d7e3d6" /><path d="M22 104c4-26 20-34 38-34s34 8 38 34a60 60 0 0 1-76 0z" fill="#d98c5f" /><circle cx="60" cy="48" r="20" fill="#e6b896" /><path d="M40 40c4-14 14-18 22-18s18 4 20 18c-8-6-14-8-21-8s-14 2-21 8z" fill="#8a6a4a" /><path d="M44 62c4 10 12 14 16 14s12-4 16-14c-6 4-10 5-16 5s-10-1-16-5z" fill="#8a6a4a" /></svg>
              <h3>Tomasz Wren</h3><div className="person__role">Breath · Yin</div><p>A former physio who teaches the slow, long-held shapes that undo desk posture.</p>
            </article>
            <article className="person">
              <svg className="person__avatar" viewBox="0 0 120 120" role="img" aria-label="Drawn portrait of Priya"><circle cx="60" cy="60" r="60" fill="#f4e2c6" /><path d="M22 104c4-26 20-34 38-34s34 8 38 34a60 60 0 0 1-76 0z" fill="#8f6f9a" /><circle cx="60" cy="48" r="20" fill="#a8704c" /><path d="M36 52c-4-26 12-34 24-34s30 8 24 34c-2-12-8-20-24-20s-22 8-24 20z" fill="#1f2a25" /></svg>
              <h3>Priya Nair</h3><div className="person__role">Rest · Meditation</div><p>Leads the guided stillness. Her voice is the reason people fall asleep.</p>
            </article>
          </div>
        </div>
      </section>
      
      <section className="close" id="book">
        <div className="wrap">
          <h2 className="sec-title">Come as you are</h2>
          <p>Mats, blankets and tea are provided. Classes run Monday to Saturday.</p>
          <a className="btn" href="#book">Reserve a mat</a>
        </div>
      </section>
      <footer className="foot"><div className="wrap">Still Water Studio · 14 Salt Lane, Hobart · hello@stillwater.example</div></footer>
    </>
  );
}
