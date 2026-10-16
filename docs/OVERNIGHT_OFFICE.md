# The overnight test run on the office laptop

What this is: one double-click that tests DebCraft for a whole night while you sleep. It runs every test once, one after another, gives DebCraft real tasks of different kinds (fixing code, building a tool, cutting a signature out of a photo, researching on the web, building a whole web application, designing pages with Gemini and with Azure, documents and presentations), and in the morning leaves **one report page** that says what passed, what failed and which screenshots to send back so that I can see why.

It is built so that it does not get stuck:

- Every job is a separate program with a time limit. If a job writes nothing (no output, no new files) for 25 minutes it is stopped, marked **STALLED**, and the night goes on with the next job.
- The whole night has a budget (11 hours by default). Nothing is started that cannot finish in what is left.
- A job that needs something the laptop does not have (Gemini not answering, no Node, no browser) is **SKIPPED** with the reason, not started.
- It never waits for a key press, and it asks Windows to stay awake.
- The report is rewritten after every job, so even if the laptop restarts at 3 am you have a report up to then, and you can continue the same night (see "If it stopped early").

## Before you leave (about 15 minutes, once)

1. **Plug the laptop in and stop it sleeping.** Settings, System, Power: set "Screen turn off" to anything, and **Sleep to Never** while plugged in. If you will close the lid, also set "Closing the lid" to **Do nothing** (Control Panel, Power Options, "Choose what closing the lid does"). Locking the screen (Windows key and L) is fine. Do not shut down, sign out or let it restart for updates.
2. **Get the newest code.** Download it (or pull it) into a folder, for example `C:\Work\LocalDevelopment\forge-main`, and double-click `Start-DebCraft.cmd` once. When DebCraft opens, close it. This makes the private Python environment (`.venv`) that the night uses.
3. **Test tools.** `Start-Overnight.cmd` adds them by itself the first time (needs the internet). To do it by hand, open PowerShell in that folder and run:

   ```
   .\.venv\Scripts\python -m pip install -e ".[dev,docs,webtext]"
   ```

4. **Check the `.env` file** (`%USERPROFILE%\.forge\.env`) has what you put there before: the Azure names, the second resource (`AZURE_FALLBACK_*`), `AZURE_STRONG_DEPLOYMENT=aicloud-gpt-5.4`, `AZURE_GPT52_DEPLOYMENT=aicloud-gpt-5.2`, and for Gemini `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION=global`. If Gemini asks you to sign in, run `gcloud auth application-default login` once.
5. **Look at the plan** (nothing runs):

   ```
   Start-Overnight.cmd --dry-run
   ```

   It prints every job, how long it should take and what it needs. The core night is about **ten hours**.

## Start the night

Double-click **`Start-Overnight.cmd`** (or run it in PowerShell). A window opens and prints one line when each job starts and ends. Leave it open. It first runs a **preflight** (about 10 minutes): it checks the tools, asks every model "say OK", tries to make a picture with Gemini, and runs `forge doctor`. You can open the report at any time to see how it is going:

`overnight-results\<date-time>\MORNING_REPORT.html` (it refreshes after every job).
`overnight-results\<date-time>\HEARTBEAT.txt` shows the time it last checked the running job: if that time is moving, it is alive.

Do not use the laptop for heavy work during the night: the speed numbers and the browser tests depend on it being quiet.

## In the morning

1. Open `overnight-results\<date-time>\MORNING_REPORT.html` in your browser. The first line says whether the run **finished**. The table has one row per job: **PASS**, **PROBLEMS** (it ran but something it checked was wrong), **FAILED**, **TIMEOUT**, **STALLED** or **SKIPPED** (with the reason).
2. **If everything is PASS, send me a screenshot of the top table. That is all.**
3. **For each row that is not PASS**, the page has a section below the table with the failure details and the pictures. Take screenshots of those sections (scroll, one screenshot per section) and send them. The page also lists the exact files: `jobs\<job>\failure.md` and the pictures in `jobs\<job>\evidence\`. If a screenshot does not show enough, open the file named and screenshot that.
4. **The design taste test needs your eyes, before mine.** Open `runs\designbench\gallery-fernhill\gallery.html` and `runs\designbench\gallery-taste-mini\gallery.html`. They show the pages as Page 1, 2, 3 in a random order, without saying which model made which. For each brief write down which you like most and which least, **then** open `key.md` in the same folder (it says which model made which). Send me your choices and the key.
5. For the invoice application, the pictures of its pages are in `jobs\task_invoice_app\evidence\`. Look at them and tell me what you think of the look; the report says what it could and could not do.
6. If you would rather send one file: `results-bundle.zip` in the same folder holds the report and the small files of every job, with anything that looks like a key removed. Look inside before sending (the invoices and the prescription it uses are made up, no real data is involved).

## If it stopped early (power cut, restart, you pressed Ctrl+C)

Run the same command with the same folder and it continues with what is left, keeping what finished:

```
Start-Overnight.cmd --out overnight-results\<the same date-time folder>
```

Jobs that were running when it stopped are run again.

## Travelling: pause, switch the laptop off, continue later

The run can be stopped at any point and continued when the laptop is back. Three double-click files in the DebCraft folder:

- **`Pause-Overnight.cmd`** asks the run to stop **after the job that is running now has finished** (jobs take 3 minutes to 2 hours). The run window closes by itself when it has paused. Nothing is lost.
- **`Pause-Overnight-Now.cmd`** stops it **now** (wait about 30 seconds until the run window says it has paused). The job that was running starts again from its beginning when you continue. Use this when you have to shut the laptop in a few minutes.
- **`Resume-Overnight.cmd`** continues the newest run where it stopped: the jobs that finished are kept, the report keeps growing, and the job that was cut short starts again from its beginning. It also works after a power cut, a restart or Ctrl+C, without any earlier pause. Nothing else has to be done on the laptop: it starts a new preflight-free continuation with a fresh time budget (11 hours).

So: before you leave, double-click `Pause-Overnight-Now.cmd`, wait for the window to say paused, shut the laptop down. When you are back, switch it on, wait until it is on the network, double-click `Resume-Overnight.cmd`, and leave it. `MORNING_REPORT.html` shows "Not finished" and how many jobs are still to run while the run is paused.

Notes: a job that was stopped starts again from its beginning, so a long job (the coding benchmark takes about an hour) loses its progress; stop between jobs with `Pause-Overnight.cmd` when you can. If you connect through a VPN, connect it before you resume.

## The second night: run again only what did not pass

After a fix (new code, Gemini sign-in), do not start from nothing. **Double-click `Retry-Overnight.cmd`** (a double-click cannot add `--retry` to `Resume-Overnight.cmd`), or run the same folder with `--retry`. Jobs that PASSED are kept; failed, problem, timeout, stalled and skipped jobs run again (and the preflight is run again, so a Gemini that now answers is found):

```
Start-Overnight.cmd --out overnight-results\<the same date-time folder> --retry
```

To run only some of them add `--only fernhill_c,fernhill_b,fernhill_gallery` (the names are in the plan printed by `--dry-run`).

## If a dialog asks to install Python

Click Cancel and never type an administrator password. Nothing in the night may install anything; the runner and DebCraft now remove the Microsoft Store app-alias folder from the commands' PATH, so a command that says `python3` fails at once instead of opening the Store. If a dialog still appears, take a picture of it (its title and the program name matter) and send it with the report.

## What runs, in order (the core night)

| Job | What it tests | About |
|---|---|---|
| Preflight | tools, every model, picture generation, `forge doctor` | 10 min |
| Test suite, then browser tests, live model tests, network tests | the code itself on this laptop, and a real shadcn and Magic UI install | 55 min |
| Gemini and image smoke tests | the Gemini provider and `generate_image` | 8 min |
| Fernhill bakery page, three ways | A: the default model (gpt-5.4) designs and builds. C: Gemini 4 Argon designs and builds. B: gpt-5.4 builds from Argon's design. With a blind gallery. Real photographs come from `generate_image` here | 95 min |
| Small tasks | fix failing tests; a log-analyser tool; a signature cut out of a made-up prescription photo (three times: default model, Argon, gpt-5.4); a web research report with sources | 90 min |
| Two small design briefs, three ways, with a gallery | a quick second look at Argon's taste | 40 min |
| Gemini critic test | does Argon as the checking model make the pages better | 25 min |
| Invoice OCR web application | the large build: ingestion screen, invoice list, side-by-side review, reports; checked by running it and photographing every page | 90 min |
| Fourteen coding tasks, ten approach challenges | the coding benchmark and how it tackles traps | 105 min |
| Word, Excel and PDF documents; five presentations | documents and decks, judged on the pages as printed (needs Office on this laptop) | 70 min |

For a weekend, `Start-Overnight.cmd --profile extended --max-hours 22` adds the full four-brief taste test in three ways, the full Gemini critic test and the speed benchmark (about nine more hours).

## If something looks wrong

- **Preflight says Gemini does not answer.** All jobs that need Gemini are skipped; the rest run. Check `gcloud auth application-default login` and the two Google lines in `.env`, then run the skipped jobs later with `--only fernhill_c,fernhill_b,fernhill_gallery` and the same `--out`.
- **"pytest not found" or tests skipped.** Step 3 above was not done.
- **A job says STALLED.** It stopped producing anything for 25 minutes (a hung model call, a stuck browser). The report shows the last thing it was doing. This is a finding, not a problem with the night: send the section.
- **The laptop slept anyway.** Look at the clock in `HEARTBEAT.txt` against the time you woke up. Step 1 was not enough on a managed laptop; tell me and I will add a second way to stay awake.
- **The window shows an error at once.** Read its first line; it names the missing piece (for example "Double-click Start-DebCraft.cmd once first").

## Privacy

Nothing is uploaded anywhere. The only network traffic is the model calls (Azure, Gemini), the web searches of the research task and the packages the tasks install into their own folders. The prescription photo used by the signature tasks is generated by the program and shows no real person. The report and bundle are redacted for anything that looks like a key.
