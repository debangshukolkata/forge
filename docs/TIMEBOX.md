# Starting a run at a time and working until a time (the time box)

`forge run` can wait for a start time, work until an end time, and wrap up. Added 2026-10-16 (D-460).

```
forge run --workspace C:\Work\ForgeRuns\myproject --auto-approve -p "Build the leave application ..." --start-at 14:00 --until 17:00
```

| Option | Meaning |
|---|---|
| `--start-at 14:00` | Wait until then before starting. `14:00` is the next 14:00 (tomorrow when it has passed); `2026-10-17 14:00` is exact. |
| `--until 17:00` | Work until then. An end time is counted from the start, so `--start-at 22:00 --until 06:00` ends the next morning. |
| `--wrap-up "text"` | What to do at the end. Default: update memory (`memory_write`), update the task list and the progress notes with what is done, in progress and next, and say what is left. |
| `--wrap-minutes 10` | The wrap-up starts this long before `--until`. |
| `--grace-minutes 10` | The run is stopped this long after `--until`, whatever it is doing. |

## What happens
1. Until the start time the command only waits (the window must stay open and the laptop awake).
2. At `--until` minus the wrap-up minutes the turn that is running is **interrupted** (a message sent into a running turn would only be read when the turn ends, perhaps an hour later) and the model is told: stop starting new work, finish only the step you are on, bring the project to a clean state (nothing half-edited, tests run, failing ones named and left alone), then do the wrap-up.
3. If the wrap-up has not finished by `--until` plus the grace minutes, the run is interrupted and ends.
4. **A deadline is soft and then hard:** a model call can take minutes, so "17:00" means wrapped up by about 17:00 and stopped by 17:10 at the latest.

## Result
Exit code `3` means the time box ended the run and the work is not finished (the status line says "wrapped up" or "stopped at the hard limit"). `0` still means the requirement was finished and exported before the end. To continue later: `forge run --workspace <same folder>` with no requirement picks up the saved task list and notes where they stopped.

## Checked live (2026-10-16)
A real 6-minute box on a habit-tracker brief (gpt-5.4): at the soft deadline the turn was interrupted, the model ran the tests, saved a `project-state` memory and wrote the hand-off into PROGRESS.md, stopped without starting the next task, and the run ended by itself about a minute before `--until`. The first try showed two faults, both fixed: the orchestrator started the next pending task after the wrap-up turn (so the run only ended at the hard limit), and a task stopped by the wrap-up was recorded as "blocked", which a resume skips; it is now put back to pending with "[paused by the time box]" and the model's note.

## Limits
- It does not survive the laptop sleeping, a closed window or a restart; use `Resume` afterwards. (Windows Task Scheduler could start the command, but on a managed laptop it may need rights you do not have.)
- A run that finishes the whole requirement before `--until` simply ends early.
- Everything the run does stays inside its own workspace, as for any `forge run`: it never pushes, deletes outside it or changes the original repository.
