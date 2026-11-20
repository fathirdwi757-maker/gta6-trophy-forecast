# Model notes — gta6-trophy-rarity-forecast-01

## What is being forecast, exactly (from the kit)

- One final case `f00`, cut at the deadline 2026-11-21T11:30:00Z: every valid read the house
  made of Exophase's GTA VI (PS5) trophy page before it, oldest first. Target
  2026-11-26T00:00:00Z (horizon 6,510 minutes ≈ 4.52 days).
- 55 trophies (1 platinum, 2 gold, 6 silver, 46 bronze; list and order are the case's own —
  this program invents no trophy list, it reads `trophies` from the case file).
- Per trophy: five quantiles (0.05, 0.25, 0.5, 0.75, 0.95) of its earn rate in percent.
  Score: mean pinball loss on the logit scale over all trophies × quantiles; lower is better;
  a prize needs a loss strictly below the best house entry (persistence baseline, a
  last-24 h logit-trend baseline, and an AI model forecast).
- The entry is a program (`main.py`, Python 3.13 stdlib, `python3 -P -s /bot/main.py`, 8 s,
  no network), not a static table: it computes the forecast from whatever history the final
  case carries.

## The two dynamics that decide this forecast

1. **A rate is earners ÷ tracked players, and the denominator moves in steps.** Exophase
   refreshes on its own schedule: the page read 638 tracked players, unchanged, from
   2026-11-18T23:48Z to 2026-11-19T04:00Z, then 3,868 players by 04:30Z, and every rate but
   the 100% one *fell* — earners had barely moved; the denominator had jumped ~6×. Any fit
   that treats each 10-minute read as an equal, independent observation of "the rate" is
   fitting refresh artefacts. So the program (a) compresses history to reads that changed,
   (b) weights reads by tracked-player count (a proportion's noise scales with 1/N, and at
   638 players a 0.01-point print step is a sixteenth of a person), and (c) adds explicit
   "flat-risk" spread when a history shows no movement — an unseen refresh is then the
   dominant risk, exactly what the practice cases demonstrate.
2. **Earn rates climb a story funnel, fast at first, then saturating.** Players pour through
   early story trophies in the first days and stall progressively deeper in the game; grind
   and collection trophies lag by weeks. A straight persistence forecast (the house baseline)
   therefore understates almost everything at a 4.5-day horizon, while an unshrunk per-trophy
   trend overfits rounding noise. The program fits logit(rate) against ln(1 + hours since the
   first read) per trophy, shrinks each slope toward the cross-trophy median slope, damps the
   extrapolated move 20% back toward persistence, and bounds the median with the base-rate
   caps below.

## Base rates used (published, long-run unless noted)

- **RDR2, tracked-player samples (PSN Trophy Leaders / PSN Leaderboard trophy pages):**
  story funnel — first mission 91.2%, Chapter 1 complete 84.1%, Chapter 2 63.1%, Chapter 3
  55.0%, Chapter 4 50.0%, Chapter 5 49.1%, story end 45.7%, epilogue 42.1%; "Attain 100%
  completion" 5.5% of that site's sample (Sony's own percent 0.5); platinum 3.9% site sample,
  0.44% on PSN Leaderboard's sample, Sony percent 0.1. These are *lifetime* rates after
  years — week-one values sit far below them, but the funnel's *shape* (each chapter keeps
  roughly 75-90% of the previous chapter's holders) is the prior for the trend's ceiling.
- **Steam global achievement rates, read 2026-11-01 (Perthro's open-world comparison):**
  finished the main story — RDR2 23.6%, GTA V 23.8%, Cyberpunk 2077 34.7%, Witcher 3 21.9%;
  100%/everything — GTA V 6.0%, RDR2 2.8%, Elden Ring 10.5%. Platform-wide samples include
  never-launched owners, so they bound tracked-sample rates from below.
- **Steam study of 100 story games (RageQuit.gg, October 2026):** median lifetime finish
  rate 33.3% (40.9% among players with ≥1 achievement).
- **Early-launch dynamics (Phantom Blade Zero tracker, Steam):** final-boss achievement
  21.9% at day 11 → 26.3% at day 14, late story steps still gaining ~1.5 points/day while
  the first steps had already settled (+0.2 in 3 days). Week one of GTA VI is the steep part
  of the curve for mid/late story trophies and the flat part for the first ones.
- **GTA VI's own scale (reported around launch):** story ≈ 45-55 focused hours (reviewer
  runs to credits: 42-115 h), Platinum ≈ 200 h. In the 168 h to the target, the Platinum is
  reachable only by a handful of no-sleep runs: its week-one rate belongs near zero.
- **Sample bias (Kwak, WebSci 2022):** profile-site samples (the Exophase kind) skew engaged
  versus platform-wide counts — Exophase rates run *higher* than PSN-wide rates for the same
  trophy, which is why the caps below sit nearer the tracked-sample figures than Sony's.

## Per-category reasoning for the 55 trophies

- **Story funnel (ids 2-13, secret bronzes + final-mission gold id 7):** "Complete Gone
  Fishing" and Chapter 1 (ids 2-3) are the widest part of the funnel — most tracked players
  clear them in days; Chapters 2-4 (ids 4-6) shed a growing share; the named story missions
  (ids 8-13) sit between chapters in the same cascade; the final mission (id 7, gold) is the
  funnel's end: with a ~50 h story and 168 h elapsed, a tracked-sample completion share in
  the tens of percent is credible, the platform-wide ~24% lifetime figure being the floor
  reference, not the week-one value.
- **Platinum (id 1) and 100% Completion (id 14, gold):** ~200 h of content against a 168 h
  week caps these at the bottom of the table — medians capped at 1.5% and 2.5% in the
  program, with the trend free to sit far below.
- **Grind / collection silvers (ids 15, 17, 25, 30, 31, 40):** 250 stunts, all shooting-range
  golds, 3 card sets, 100 WAiNK spots, 5 bank vaults — these trail the story by weeks;
  their week-one medians stay in the low-to-mid range of whatever the last reads show, and
  the slope shrinkage matters most here because their prints are noisy.
- **One-off and activity bronzes (the rest):** a long tail of "do X once" trophies whose
  rates track total hours played more than story progress; the cross-trophy median slope is
  mostly *their* slope, which is why it is the shrinkage target.

## Validation

- Kit practice cases p00/p01: output format-validated (ids, order, five non-decreasing
  quantiles in [0, 100], ≤ 65,536 bytes), byte-identical across two runs, ~0.05 s per run.
  (Their histories are the frozen pre-refresh page, so they exercise the flat-risk path.)
- Synthetic final-like cases (a *different* generating process than the model: per-trophy
  earner hazards against a step-refreshing, growing tracked-player denominator; history cut
  at 2026-11-21T11:30Z, truth at 2026-11-26T00:00Z): this program's pinball-logit loss
  0.227 / 0.236 on two variants vs the house persistence baseline's 0.608 / 0.631 on the
  same cases. Synthetic evidence only — the real check is the frozen final dataset — but it
  verifies the trend machinery end to end, including the refresh jump.
