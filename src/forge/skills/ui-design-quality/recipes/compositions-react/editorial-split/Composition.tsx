// Composition `editorial-split` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="edit" aria-labelledby="edit-title">
        <div className="edit__top"><span>Harbour Library</span><span>Spring programme</span><span>Free for all ages</span></div>
        <div className="edit__grid">
          <div>
            <p className="edit__issue">No. 12 — Reading together</p>
            <h1 className="edit__title" id="edit-title">A quieter way to <em>learn out loud</em></h1>
            <p className="edit__lede">Saturday story circles, a homework room with real tea, and a shelf of picture books in eleven languages.</p>
            <div className="edit__cols"><p><b>Saturdays</b>10:00 to 12:30, ages 3 to 8, no booking.</p><p><b>Weeknights</b>Homework room, 16:00 to 19:00, ages 9 to 16.</p></div>
            <a className="link" href="#visit">Plan your first visit</a>
          </div>
          <div className="edit__arch">
            {/* Drawn art: sun, hills and a path. Recolour with the tokens. */}
            <svg viewBox="0 0 300 400" preserveAspectRatio="xMidYMid slice" role="img" aria-label="A sun above rolling hills with a winding path">
              <rect width="300" height="400" fill="#2f5d50" /><circle cx="210" cy="120" r="52" fill="#f2d9a6" />
              <path d="M0 270c60-50 120-60 190-20s80 20 110 0v150H0z" fill="#244a40" /><path d="M0 320c70-40 130-30 200 10s70 20 100 0v70H0z" fill="#1b3a32" />
              <path d="M150 400c-30-40 40-60 10-100s30-50 40-60" fill="none" stroke="#f7f2ea" strokeWidth="6" strokeLinecap="round" opacity=".85" />
            </svg>
          </div>
        </div>
      </section>
    </>
  );
}
