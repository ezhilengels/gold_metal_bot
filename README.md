cd gold_bot
python3 run_bot.py --dry-run --force --open
```

- `--dry-run` → no Telegram, no history written
- `--force` → skips trading-day / time check (so it runs any time)
- `--open` → opens `dashboard.html` in your browser automatically

---

**What you should see in the terminal:**
```
  Gold Bot  ·  2026-04-04 09:15 IST
  ⏰  Next scheduled run: 2026-04-07 09:15 IST (in 71h 45m)

╔══════════ SIGNAL 08 — GOLD BOT FINAL VERDICT ══╗
║  S01 ✅ BUY (HIGH, score=3.2/4) — 10/15 pts     ║
║  S02 ✅ STRONG BUY (4/5 factors) — 25/25 pts    ║
  ...
║  FINAL SCORE  : 58.0 / 95.0                     ║
║  VERDICT      : BUY 🟢                          ║
╚═════════════════════════════════════════════════╝

  📊 Dashboard → ./dashboard.html

Then check history works:
python3 run_bot.py --force          # real run (no --dry-run)
python3 bot_status.py               # see the recorded run

Then start the live scheduler:
bashpython3 run_bot.py --schedule --open
Leave this running — it will fire automatically at 9:15 AM IST every Mon–Thu.