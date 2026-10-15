# Skill A/B runs (C14, D-417)

### Skill `test-first`: with and without

| Condition | Tasks passed | Hidden tests | Model calls | Wall s | Cost |
|---|---|---|---|---|---|
| with the skill | 2/4 | 173/175 | 48 | 1140 | $1.57 |
| without the skill | 2/4 | 173/175 | 49 | 1305 | $1.83 |

| Task | with: tests / s / calls | without: tests / s / calls |
|---|---|---|
| t11_rate_limiter | 25/25 / 289 / 16 | 25/25 / 152 / 6 |
| t12_expr_calc | 68/69 / 241 / 6 | 68/69 / 292 / 14 |
| t13_todo_undo | 15/16 / 325 / 18 | 15/16 / 245 / 14 |
| t14_cron_next | 65/65 / 285 / 8 | 65/65 / 616 / 15 |

No difference in correctness. Calls -1, wall -165 s, cost -0.27 USD (with minus without).
