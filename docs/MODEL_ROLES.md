# Which model does which job (decision of 2026-10-15, D-411)

The user asked for a Claude Code-like Forge, left the roles to me, and asked for web research first. This is the evidence, what it supports, and the roles that follow. Everything marked
"vendor" or "aggregator" is a claim, not a measurement on our tasks; the A/B runs named at the end replace claims with numbers.

## What the research says

| Question | Finding | Strength of the evidence |
|---|---|---|
| gpt-5.4 against gpt-5.1 for coding agents | Aggregators list gpt-5.4 ahead on coding and agent benchmarks (Terminal-Bench Hard 57.6 against 45.5; a coding index of 57.2 against 44.7; ahead on 7 of 7 shared benchmarks); one site shows a much smaller gap. OpenAI's own guide: 5.4 takes the 5.3-Codex coding abilities, is the first mainline model trained for compaction (longer agent runs), has a 1.05M window, and defaults to reasoning effort `none` with `medium` for harder work. | Aggregator and vendor; the direction is consistent |
| gpt-5.2 against gpt-5.4 | Mixed: 5.2 ahead on SWE-bench Verified, 5.4 ahead on SWE-bench Pro and context | Aggregator, mixed |
| Gemini 3.1 Pro | Ahead of plain GPT-5 on SWE-bench Verified in one aggregator, behind GPT-5.5 on Terminal-Bench 2.0 and agentic averages; cheaper output tokens; 1M window | Aggregator |
| Gemini 4 Argon | Google: 77.9 percent on DeepSWE v1.1 with its own harness; first on the Vals index (68.9 percent, an independent result); behind GPT-6 Astra on FrontierSWE and behind Claude Opus 5.5 on Terminal-Bench 4.0 in one review; defaults to medium thinking; access staged; no independent tool-use benchmark | Mostly vendor; one independent index |
| Planner plus executor with two models | Cost savings are well supported; quality gains appear mainly when the executor is weak; a single strong model in a good harness often matches or beats a planner/executor pair (one arXiv study: planning helped a weaker model by 11.6 points and mainly cut cost for strong ones; practitioner reports of the split losing to one model) | Mixed, mostly blogs, one paper |
| Judge from the builder's own family | Self-preference bias is documented; a judge of another family is the minimum for independence; a panel of different families is better | Several sources; magnitudes unverified |
| Claude Code's own pattern | Main model for the work, a cheaper model for explore and other high-volume read-only subagents, the strongest model for planning (plan mode); subagents inherit the main model unless set | Community guides, not official documents |
| Rate limits | Gateways fall back reactively on 429 after the retries, honour `retry-after`, and chain across providers with request translation | Gateway documentation |

## The decision

| Role | Model | Why |
|---|---|---|
| coder (the main loop) | gpt-5.1 (changed by D-414: gpt-5.4 passed the same 13 of 14 tasks, 39 percent slower and 2.9 times the cost) | The research favoured 5.4 on public benchmarks; our own run did not. 5.4 stays selectable in the panel. |
| planner (plan mode and the `planner` subagent) | Gemini 4 Argon, else Gemini 3.1 Pro, else the coder | Used on demand for large, ambiguous or many-file work, like Claude Code's plan mode. No planning stage in front of small tasks: the evidence shows no quality gain for strong executors and a cost in time. |
| critic (design critic, candidate vote), judge, reviewer | Gemini 4 Argon, else Gemini 3.1 Pro, else gpt-5.2 (D-413), else gpt-4.1 | Another family than the builder. The independence the prompts claimed was not real while the critic ran on the coder's model (D-409). |
| knowledge builder, summariser, vision | gpt-5.1 | High-volume reading work where speed counts. A 5.4-mini would suit it if it is deployed (OpenAI positions it for high-volume agent work). |
| fallback | Gemini 3.1 Pro when Gemini answered, else gpt-5.4 or gpt-5.2 from the second Azure resource, else gpt-4o (the default config) | A rate limit or an outage usually hits one provider: the router prefers a model of another provider, and a Gemini model that fails falls back to the coder's Azure model. |

Gemini is used only after the user answers Yes to "Is Gemini enabled for you?" and the test passes (sending code to Google is the user's decision, per machine). Everyone else keeps Azure for every role.

## What is measured, and what is still a claim

- Measured here: coder gpt-5.1 on the coding benchmark (13 of 14 tasks), the approach challenges, the design benchmark (night-2). Coder gpt-5.4 on the coding benchmark: run `night-gpt54`, the same results as gpt-5.1, slower and dearer (docs/CODE_BENCHMARK.md, D-414).
- Still to measure, on the user's laptop (no Google credentials here): Argon as critic and judge against the Azure critic, with the same briefs and a blind comparison; Argon or Gemini 3.1 Pro as planner on the hard tasks and the design briefs. The A/B decides whether each stays.
- Sources: benchlm.ai, requesty.ai and llmreference.com comparisons; OpenAI's GPT-5.4 guide (developers.openai.com); Google's Gemini 4 Argon announcement and third-party reviews (Artificial Analysis, hackernoon, eesel); arXiv 2609.20804 (harness design for coding agents); blogs on planner and executor pairs (akitaonrails, morphllm, kilo); LLM-as-judge bias summaries (promptlayer, memx, tianpan); Portkey and LangSmith gateway fallback documentation; community Claude Code model guides (claudelog, dometrain).
