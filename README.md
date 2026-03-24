# groupwatch

[Читать по-русски](./README.ru.md)

Watches a list of Facebook groups for new posts and appends them to a CSV file
or a Google Sheet. It is built for thousands of groups, where the hard part is
not parsing but keeping the accounts alive: every visit goes through a paced
queue and a small pool of logged-in browser sessions, and every failure lands in
an error journal instead of silently stopping the run.

![Demo run: 100 groups, 3 sessions, one of them hits a checkpoint](./docs/demo.png)

## How it works

```
groups.csv ──> queue ──> account pool ──> browser session ──> dedup by post id ──> CSV / Google Sheet
                 ^            │
                 └── retry ───┘──> error journal (group did not open, account paused)
```

- **Source list.** A table with `url,name,accounts`. The `accounts` column says
  which sessions are members of the group, so a closed group is only opened by
  an account that can see it.
- **Queue and workers.** One asyncio worker per session. Each account keeps its
  own gap between visits (40 s ± 30% by default) and an hourly cap (60).
- **Browser sessions.** Playwright with a persistent Chromium profile per
  account. You log in by hand once (`groupwatch login acc-1`), then the profile
  is reused, so Facebook sees the same device every time. No official API: it
  does not give access to group feeds.
- **Checkpoints.** When Facebook redirects a session to a checkpoint or login
  page, that account is paused and logged, and its group goes back to the queue
  for another session. The tool does not try to get around the check; a human
  confirms the account and it comes back.
- **Dedup.** Posts are keyed by the id from their permalink and kept in SQLite,
  so a group can be revisited as often as needed and only new posts are written.
- **Output.** `posts` sheet: collected at, group, author, text, link, post id.
  `errors` sheet: time, group, account, kind, detail.

## Try it

```bash
uv sync
uv run groupwatch demo            # 100 simulated groups, 3 sessions, 2 passes, offline
uv run pytest
```

The demo runs the whole pipeline (queue, pacing, checkpoint on one account,
dead groups, retries, dedup across passes, CSV output) against a simulated
source, so it needs no accounts. At the end it prints how long one pass takes at
live pacing.

## Live run

```bash
uv sync --extra live --extra sheets
uv run playwright install chromium
uv run groupwatch login acc-1     # log in, close the window
uv run groupwatch run --groups examples/groups.csv --accounts acc-1,acc-2 \
    --sheet <google-sheet-key> --credentials credentials.json --loop 600
```

Throughput is set by the pacing, not by the code: with a 40 s gap and about 15 s
per group, one account reads about 60 groups an hour. 3000 groups with 10
accounts is a pass every 5 hours. The live collector reads the group feed in
chronological order and picks posts by their permalink; its selectors are
checked in the pilot run on the real groups before scaling up.

## Layout

| File | What it does |
|---|---|
| `accounts.py` | Session pool: per-account gap, hourly cap, membership, pause on checkpoint |
| `runner.py` | Queue, workers, retries, error journal |
| `facebook.py`, `extract_posts.js` | Playwright collector and feed parser |
| `store.py` | SQLite: seen posts and errors |
| `sinks.py` | CSV and Google Sheets output |
| `simulated.py` | Offline source for the demo and tests |
| `dashboard.py`, `cli.py` | Live terminal view and commands |
