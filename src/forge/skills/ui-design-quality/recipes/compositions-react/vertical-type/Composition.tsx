// Composition `vertical-type` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <section className="sign" aria-labelledby="sign-title">
        <p className="sign__word" lang="ja" aria-hidden="true">黒ラーメン</p>
        <div className="sign__body">
          <p className="sign__kicker">Namba, Osaka · 22:00 to 04:00</p>
          <h1 className="sign__title" id="sign-title">Ten seats, one broth, nothing before ten at night.</h1>
          <p className="sign__text">Behind the black curtain, past the paper lantern. We simmer the broth all day and open when the city quiets down.</p>
          <div className="sign__hours"><span><b>22:00</b>Doors</span><span><b>03:30</b>Last bowl</span><span><b>04:00</b>Close</span></div>
          <a className="btn" href="#find">How to find the door</a>
        </div>
        {/* Drawn lantern, not a placeholder. */}
        <svg className="sign__art" viewBox="0 0 200 320" role="img" aria-label="A paper lantern glowing red">
          <line x1="100" y1="0" x2="100" y2="40" stroke="#b9aa98" strokeWidth="3" />
          <rect x="70" y="36" width="60" height="14" rx="3" fill="#3a302a" />
          <ellipse cx="100" cy="150" rx="78" ry="100" fill="#d9382c" />
          <g fill="none" stroke="#8f2018" strokeWidth="3"><path d="M24 150h152M34 100h132M34 200h132M60 62h80M60 238h80" /></g>
          <ellipse cx="100" cy="150" rx="78" ry="100" fill="url(#glow)" />
          <defs><radialGradient id="glow" cx=".4" cy=".35" r=".7"><stop offset="0" stopColor="#ffd79a" stopOpacity=".55" /><stop offset="1" stopColor="#d9382c" stopOpacity="0" /></radialGradient></defs>
          <rect x="70" y="248" width="60" height="14" rx="3" fill="#3a302a" /><path d="M100 262v40M88 302h24" stroke="#b9aa98" strokeWidth="3" />
          <text x="100" y="165" textAnchor="middle" fontSize="64" fill="#f4ece1" fontFamily="serif" lang="ja">黒</text>
        </svg>
      </section>
    </>
  );
}
