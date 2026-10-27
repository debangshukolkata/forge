// Composition `school-courses` (React): the structure and class names of the HTML recipe with the same sample content. Replace the words and the drawn art with the product's own,
// replace tokens.css with the tokens exported from DESIGN.md, and split it into components if the page grows. The colours and fonts come from CSS variables.
import "./tokens.css";
import "./composition.css";

export default function Composition() {
  return (
    <>
      <div className="wrap">
        <header className="nav">
          <a className="nav__brand" href="#">Lantern Academy</a>
          <nav className="nav__links" aria-label="Main"><a href="#courses">Courses</a><a href="#enrol">Enrolment</a><a href="#teachers">Teachers</a><a href="#voices">Families</a></nav>
          <a className="btn btn--soft" href="#enrol">Enrol</a>
        </header>
      
        <section className="hero" aria-labelledby="hero-title">
          <div>
            <span className="hero__eyebrow">Autumn term opens 4 November</span>
            <h1 id="hero-title">Small classes where <em>curious</em> kids and adults light up</h1>
            <p>Evening and weekend courses in writing, coding, drawing and maths, taught live in groups of eight or fewer.</p>
            <div className="hero__cta"><a className="btn" href="#enrol">Enrol for autumn</a><a className="btn btn--soft" href="#courses">See the courses</a></div>
          </div>
          {/* Drawn open book with a lantern light: not a placeholder. */}
          <svg className="hero__art" viewBox="0 0 520 420" role="img" aria-label="An open book with a glowing lantern, stars and a pencil">
            <rect x="10" y="10" width="500" height="400" rx="48" fill="#dbe7ff" />
            <circle cx="400" cy="90" r="46" fill="#ffd25e" /><circle cx="400" cy="90" r="70" fill="#ffd25e" opacity=".3" />
            <g fill="#fff"><path d="M70 90l6 14 14 6-14 6-6 14-6-14-14-6 14-6z" /><path d="M180 60l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" /><path d="M110 170l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" /></g>
            <path d="M260 300c-40-34-110-40-190-24V150c80-16 150-10 190 24z" fill="#fff" stroke="#1f2a44" strokeWidth="6" strokeLinejoin="round" />
            <path d="M260 300c40-34 110-40 190-24V150c-80-16-150-10-190 24z" fill="#fffaf0" stroke="#1f2a44" strokeWidth="6" strokeLinejoin="round" />
            <path d="M260 174v126" stroke="#1f2a44" strokeWidth="6" />
            <g stroke="#3a5bd9" strokeWidth="6" strokeLinecap="round" fill="none"><path d="M100 188c40-8 78-4 128 16M100 218c40-8 78-4 128 16M100 248c34-6 60-2 100 12" /></g>
            <g stroke="#ff8a3d" strokeWidth="6" strokeLinecap="round" fill="none"><path d="M292 204c50-20 88-24 128-16M292 234c50-20 88-24 128-16" /></g>
            <path d="M70 316c60 18 130 20 190 6 60 14 130 12 190-6l-10 34c-58 14-120 14-180 0-60 14-122 14-180 0z" fill="#ff8a3d" />
            <g transform="rotate(-32 130 356)"><rect x="60" y="346" width="150" height="22" rx="6" fill="#3a5bd9" /><path d="M210 346l34 11-34 11z" fill="#ffd25e" /><rect x="60" y="346" width="26" height="22" rx="6" fill="#ff8a3d" /></g>
            <g transform="translate(260 96)"><path d="M-10 -34h20v12h-20z" fill="#1f2a44" /><rect x="-26" y="-22" width="52" height="54" rx="14" fill="#ffd25e" stroke="#1f2a44" strokeWidth="6" /><rect x="-14" y="-6" width="28" height="26" rx="8" fill="#fff6c9" /><path d="M-18 32h36" stroke="#1f2a44" strokeWidth="6" /></g>
          </svg>
        </section>
      </div>
      
      <section className="section" id="courses" aria-labelledby="courses-title">
        <div className="wrap">
          <h2 className="section__title" id="courses-title">This term's courses</h2>
          <p className="section__lead">Every course meets once a week. Materials are included, and the first session can be swapped for a refund.</p>
          <ul className="courses">
            <li className="course"><div className="course__name">Storycraft<small>Write a short story from first idea to last line. Ages 10 to 14.</small></div><div className="course__when"><span>Starts</span>Tue 5 Nov</div><div className="course__len"><span>Length</span>8 weeks</div><div className="course__price">$180</div><a className="course__go" href="#enrol">Enrol</a></li>
            <li className="course"><div className="course__name">First Code<small>Build a small game with blocks, then with real code. Ages 9 to 12.</small></div><div className="course__when"><span>Starts</span>Thu 7 Nov</div><div className="course__len"><span>Length</span>10 weeks</div><div className="course__price">$240</div><a className="course__go" href="#enrol">Enrol</a></li>
            <li className="course"><div className="course__name">Sketchbook Sundays<small>Observation drawing, shading and a finished portrait. All ages.</small></div><div className="course__when"><span>Starts</span>Sun 10 Nov</div><div className="course__len"><span>Length</span>6 weeks</div><div className="course__price">$130</div><a className="course__go" href="#enrol">Enrol</a></li>
            <li className="course"><div className="course__name">Maths Without Tears<small>Fractions, ratios and word problems explained slowly. Ages 11 to 15.</small></div><div className="course__when"><span>Starts</span>Mon 11 Nov</div><div className="course__len"><span>Length</span>12 weeks</div><div className="course__price">$260</div><a className="course__go" href="#enrol">Enrol</a></li>
          </ul>
        </div>
      </section>
      
      <section className="section steps-band" id="enrol" aria-labelledby="enrol-title">
        <div className="wrap">
          <h2 className="section__title" id="enrol-title">How enrolment works</h2>
          <p className="section__lead">Four short steps, and most families finish them in one evening.</p>
          <ol className="steps">
            <li className="step"><h3>Pick a course</h3><p>Choose a course and a start date from the list above.</p></li>
            <li className="step"><h3>Book a trial</h3><p>Join a free twenty-minute taster call with the teacher.</p></li>
            <li className="step"><h3>Confirm and pay</h3><p>Reserve the seat by card or in two instalments.</p></li>
            <li className="step"><h3>Get your welcome pack</h3><p>We send the class link, the materials list and a first task.</p></li>
          </ol>
        </div>
      </section>
      
      <section className="section" id="teachers" aria-labelledby="teachers-title">
        <div className="wrap">
          <h2 className="section__title" id="teachers-title">Meet the teachers</h2>
          <p className="section__lead">Working writers, engineers and artists who like explaining things.</p>
          <ul className="teachers">
            <li className="teacher"><span className="teacher__dot" style={{ "background": "#ffd25e" }}>M</span><div><div className="teacher__name">Maya Okafor</div><div className="teacher__role">Head of writing, former newspaper editor</div></div></li>
            <li className="teacher"><span className="teacher__dot" style={{ "background": "#bfeedd" }}>T</span><div><div className="teacher__name">Tomas Lindqvist</div><div className="teacher__role">Coding teacher and game developer</div></div></li>
            <li className="teacher"><span className="teacher__dot" style={{ "background": "#dbe7ff" }}>P</span><div><div className="teacher__name">Priya Raman</div><div className="teacher__role">Maths tutor, twelve years in classrooms</div></div></li>
            <li className="teacher"><span className="teacher__dot" style={{ "background": "#ffc9a8" }}>J</span><div><div className="teacher__name">Joao Alves</div><div className="teacher__role">Illustrator and drawing coach</div></div></li>
          </ul>
        </div>
      </section>
      
      <section className="section" id="voices" aria-labelledby="voices-title">
        <div className="wrap">
          <h2 className="section__title" id="voices-title">What families say</h2>
          <p className="section__lead">Notes we received after the summer term.</p>
          <div className="quotes">
            <blockquote className="quote"><p>My daughter finished her first story and read it aloud to the whole family. She has not stopped writing since.</p><cite>Helen D.<span>Parent of a Storycraft student</span></cite></blockquote>
            <blockquote className="quote"><p>Tomas never made coding feel like homework. Our son built a maze game and then asked for the next course.</p><cite>Arjun S.<span>Parent of a First Code student</span></cite></blockquote>
            <blockquote className="quote"><p>I came to Sunday drawing as a complete beginner. Six weeks later I framed my own portrait.</p><cite>Rosa B.<span>Adult learner, Sketchbook Sundays</span></cite></blockquote>
          </div>
        </div>
      </section>
      
      <div className="wrap">
        <footer className="foot"><span>Lantern Academy · 14 Marsh Lane · hello@lanternacademy.example</span><span>Open weekdays 10:00 to 19:00</span></footer>
      </div>
    </>
  );
}
