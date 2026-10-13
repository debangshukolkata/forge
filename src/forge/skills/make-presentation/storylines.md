# Storyline guides for common decks

Pick the guide that fits, then adapt it: the order is a default, the user's material and audience win. Counts are content slides (not
the title and closing slide) and assume the `minutes` of the talk; speaker notes are what the speaker says, in full sentences the speaker
could read aloud, never the slide text again. Every title is the point of the slide (a sentence with a verb), not a label.

## Board or executive update (10 to 20 minutes, 6 to 10 slides)
Audience wants: the answer, the risks, the decision needed. They read before they listen, so every slide must work alone.
1. **The answer first** (`stats` or `bullets`): where we stand in one sentence, the 3 numbers that prove it, the decision or ask.
2. Results against plan (`chart`, one chart, target line named in the title): "Revenue is 4% above plan".
3. What drove it (`cards`, 3 cards): cause, number, owner.
4. Risks and what we do about them (`table`: risk, impact, mitigation, owner; at most 5 rows).
5. Outlook (`chart` or `steps`): next two quarters, the assumptions that matter.
6. Decision slide (`bullets`, 1 to 3 asks, each with a date): what the board must decide today.
Appendix (hidden slides, `hide_slide`): detail tables the board may ask for. Notes: the number behind each claim and where it comes from.
Avoid: a history of the quarter before the answer; more than one message per slide; charts without the takeaway in the title.

## Investor or product pitch (10 minutes, 8 to 11 slides)
Audience wants: is the problem big, is this the answer, can this team win, what do you need. Order: problem (one human story or number),
why now, the solution (a picture, `image`), how it works (`steps`, 3 steps), traction (`stats` or `chart`), market (one number and its
source), business model (`cards` or `table`), competition (a 2x2 or `table`, honest), team (`cards`, why these people), the ask
(amount, use of funds in 3 lines, milestones it buys). Notes: the 30-second version of each slide and the one question to expect.
Avoid: a feature tour; a market number with no source; a competition table where we win every row.

## Quarterly business review, QBR (30 to 45 minutes, 12 to 18 slides)
Audience: a customer or an internal leadership group; they want value delivered and a plan. Order: executive summary (3 outcomes and 1
request), goals we agreed (`table`), results per goal (one slide each: chart, the number, what it means), usage or adoption trend
(`chart`), issues and how they were resolved (`table`), roadmap for next quarter (`steps`), asks and decisions (`bullets` with owners and
dates), appendix. Notes: the story behind each number and the sentence to say if a number is bad. Avoid: hiding a bad number in the
appendix; a results slide with eight metrics (pick the three that matter, put the rest in a `table` in the appendix).

## Design or technical review (30 to 60 minutes, 10 to 20 slides)
Audience: engineers who will challenge it. Order: goal and constraints (what must be true, what is out of scope), context diagram
(`freeform` or `image`: the system today), the proposal (one diagram, then the pieces), alternatives considered with why not (`table`:
option, pros, cons, verdict), risks and unknowns (`table`), the plan (`steps`: milestones, not tasks), what we need decided today.
Notes: the trade-off in each decision and the data you have for it. Avoid: showing code on slides longer than 8 lines; a diagram with more
than about 8 boxes (split it); hiding the alternatives you rejected.

## Training or workshop (45 to 90 minutes, 12 to 25 slides)
Audience: people who must be able to do something afterwards. Slides carry less than a talk: the activity carries the learning. Order:
what you will be able to do (3 outcomes), a short agenda with times, then repeat a block of: one concept (a picture and 3 lines), a worked
example, an exercise slide (task, time box, what good looks like), debrief. Close with a summary of the 3 outcomes, where to practise,
how to get help. Use `section` slides between blocks. Notes: timing for each block, the common mistakes to look for during the exercise,
answers to the exercises. Avoid: slides read aloud; more than 10 minutes without an activity or a question; an exercise with no answer key
in the notes.

## Project status update (5 to 15 minutes, 4 to 7 slides)
Audience: sponsors and stakeholders who want to know if they need to act. Order: one-line status with a colour word as well as a colour
(`on track`, `at risk`, `blocked`: never colour alone), what was done since last time (3 bullets with results), what is next (3 bullets
with dates), risks and issues that need a decision (`table`: item, impact, owner, needed by), milestones (`steps` or `table`: planned
against forecast). Notes: what changed since last time and anything the sponsor must not be surprised by. Avoid: a task list; reporting
activity instead of results; green status with unresolved decisions on the next slide.

## Proposal or sales deck (15 to 20 minutes, 8 to 12 slides)
Audience: a buyer comparing options. Order: their situation in their words, the cost of doing nothing (a number), our approach (3
points), how it works for them (a worked example with their data if you have it), proof (a customer result with a number and a name when
allowed), the plan and timeline (`steps`), investment (`table`, options if useful), next step (one action with a date). Avoid: starting
with the company history; features without the benefit; a price slide with no options or no next step.

## All-hands or change announcement (15 to 30 minutes, 6 to 12 slides)
Audience: everyone affected; they want to know what changes for them and when. Order: the news in one sentence, why (honest, short), what
changes for whom and from when (`table`: who, what changes, when), what stays the same, timeline (`steps`), how to get help and where to
ask questions, thanks (specific). Notes: the three hardest questions and the answer to each. Avoid: burying the news after a long
preamble; euphemism; a timeline with no dates.

## Checks before building any of these
- Can the deck be read as its titles alone and still tell the story? (`read_presentation` with `format: "markdown"` shows it.)
- Is there one message per slide, and does the title say it?
- Is the ask or decision visible in the last content slide and in the notes of the first?
- Do the minutes fit the slide count (`"minutes"` in the outline makes the build warn)?
- Is every number from the user's material, with its source in the notes?
