# gta6-trophy-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/fathirdwi757-maker/gta6-trophy-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/fathirdwi757-maker/gta6-trophy-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A refresh-aware forecast of GTA VI's PS5 trophy earn rates one week after launch. `main.py` (Python 3.13, standard library only) reads a case of Exophase page reads and writes five quantiles of every trophy's earn rate at the target: it compresses the history to the reads that actually changed, fits each trophy's logit rate against ln(1 + hours) with reads weighted by tracked-player count, shrinks every slope toward the cross-trophy median, damps the move back toward persistence, and bounds medians with published base rates for comparable games (RDR2's story funnel, Steam completion rates, week-one launch dynamics). The full reasoning and sources are in [MODEL.md](MODEL.md).

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

(with the kit's practice `input/` beside it; the grader runs `python3 -P -s /bot/main.py` on the final case the same way.)

---

<sub>Entered on [make.fun](https://make.fun/?ref=7k4mkbbj&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
