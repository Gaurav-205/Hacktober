# Start here (for Gaurav)

This is everything you need to build Munim at the Hack Day with Claude Code. No application code is included, on purpose.

## The rule that decides how you use it

MLH's Hack Day rules say the project must be built **at the event**. Libraries, models, fonts and public data are allowed, and so are AI coding tools if you disclose them. These files are planning documents and tool configuration, not application code. Even so, the build prompt makes Claude list them in the build log as "pre-event materials", so you can state exactly what existed before kickoff. Re-read the live event rules and the Track 2 challenge page yourself before you start; I could not re-fetch the Track 2 page.

## What you have

| File | Use it for |
| --- | --- |
| GitHub repo `Gaurav-205/Hacktober` | **The starting folder for Claude Code**, already pushed as one commit labelled as pre-event planning. Clone it at kickoff. |
| `munim-claude-code-kit.zip` | The same folder as a zip, in case you are offline. It holds all the specs, plus Claude Code setup: `CLAUDE.md`, project hooks, four reviewer agents, six skills, path rules, and the build prompt in `docs/planning/`. |
| `CLAUDE_CODE_PROMPT.md` | The build prompt itself, for reading. The same file is inside the kit. |
| `MUNIM_ONE_PROMPT.md` | A single-file version for any other coding agent (no Claude Code features). |
| `munim-pack.zip` | The specs and the sources everything above is built from. |

## Tonight, before the event

1. **Update Claude Code.** Run `claude update`, then check that `claude -v` and `claude doctor` look healthy.
2. **Install the tools.** Install Python 3.12, `uv`, Git, Node.js (npm fetches the fonts and htmx) and Ollama. Pull the model on good Wi-Fi with `ollama pull gemma4:e4b`, and check it answers with `ollama run gemma4:e4b`.
3. **Keep a fallback key.** Optionally, get a Gemini API key and keep it in your shell environment (`GEMINI_API_KEY`), never in a file you commit.
4. **Windows only.** The project hooks are bash commands, so run Claude Code inside WSL, or make sure Git Bash is installed.
5. **Get two human checks.** Ask a Hindi-speaking person who handles business papers to read the Hindi in `docs/CONTENT.md`. Ask an accountant to confirm the current RBI Bank Rate and its effective date. These are the two weakest points in the pack.
6. **GitHub is ready.** `Gaurav-205/Hacktober` holds the planning pack and the Claude Code setup as one commit, labelled as prepared before the event. It contains no application code; don't add any before kickoff.
7. **Stop the laptop sleeping.** Set it never to sleep while plugged in, because a sleeping laptop stops the build. Bring the charger.

## At kickoff (about 5 minutes)

1. Clone your repository into a new folder:
   ```
   git clone https://github.com/Gaurav-205/Hacktober munim
   cd munim
   ```
2. Offline instead? Unzip `munim-claude-code-kit.zip`, then run `cd munim && git init -b main`.
3. Optional: open `docs/planning/CLAUDE_CODE_PROMPT.md` and fill in the kickoff block (time, deadline, machine, whether the model is pulled). If you skip this, put the kickoff time in the goal line in step 6.
4. Start Claude Code in auto mode with a session name:
   ```
   claude --permission-mode auto -n munim-build
   ```
   If auto mode isn't available on your account, start with `claude -n munim-build` instead. The project allowlist covers the usual commands, and you approve the rest.
5. When Claude Code asks whether you trust this folder, say yes. The project hooks, its command allowlist and `/goal` only work in a trusted folder.
6. Replace `HH:MM` with the kickoff time and send this goal:
   ```
   /goal Kickoff was at HH:MM IST today and this folder was created at the event. Build Munim by following docs/planning/CLAUDE_CODE_PROMPT.md exactly; read it first. The goal is met only when this conversation shows, from commands Claude ran after its last code change: make ci exiting 0; the clock golden tests (2,283,919, 9,780,909 and 4,290,370 paise) passing; every E2E scenario in docs/TESTING.md passing in Chromium, and in Firefox or logged as pending with a reason; git status clean; and docs/PROGRESS.md ending with STATUS: DONE after the evidence block and final report. Also treat the goal as met when docs/PROGRESS.md ends with STATUS: BLOCKED and Claude has stated the reason and the exact human action needed. Never weaken a test or a check to pass, never commit real documents or secrets, never push. Stop after 300 turns.
   ```
   If you'd rather watch it start, paste the whole prompt file as your first message instead, then send the goal.
7. Push to GitHub yourself every hour or so with `git push`. Claude is set to ask before any push, so pushing is your job. (If you used the zip, first run `git remote add origin https://github.com/Gaurav-205/Hacktober.git` and push with `git push -u origin main`.)

## While it runs

- **Check progress.** `/build-log` gives a short status. `/goal` with nothing after it shows the goal's turns, time and spend.
- **Look at the app.** Once Gate 3 is closed, run `make run` in a second terminal and open http://127.0.0.1:8765.
- **If the terminal closes or the laptop restarts:** run `cd munim && claude --continue`, or `claude --resume munim-build`. The goal comes back with the session, and Claude reads its build log and carries on.
- **If you hit a usage limit:** the goal pauses. Send any message after the reset to continue.
- **To stop the goal:** `/goal clear`.

## What stays with you

- The Hindi review and the Bank Rate confirmation (in the app, on the Rules page).
- Pushing to GitHub, the demo video, and the submission form.
- A final read of the README numbers (they must come from the evaluation report).
- An honest note of what existed before kickoff, in `docs/AI_CONTRIBUTION.md`.

## Known weak points (be ready to say them out loud)

- **The Bank Rate.** The value in the pack (5.75%) is a placeholder from one reading of the RBI home page, and its effective date is unverified.
- **The law.** Whether registration must come before the supply is unsettled, and the product says so.
- **The Hindi.** It is machine-drafted until a person reviews it.
- **The model.** Neither Ollama's JSON output nor Gemma 4's vision has been tested. The build probes both at runtime and has fallbacks.
- **Real papers.** No real invoice has been tested. Don't claim real-world accuracy until you measure it.
