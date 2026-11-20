"""gta6-trophy-rarity-forecast-01 entry: a refresh-aware, shrunk logit-trend forecaster.

What the grader does (kit RULES.txt): runs `python3 -P -s /bot/main.py` (Python 3.13, standard
library only, no network, 8 s per case) once per case. Each case file in the input directory is
JSON {"schema": "makefun/gta6-trophies-case/v1", "id", "at", "horizon_minutes", "target",
"levels", "game", "trophies", "history", "notes"}: `trophies` lists the game's trophies
{id, name, description, tier, points, secret} and `history` every read of Exophase's GTA VI PS5
trophy page before the checkpoint, oldest first, each {slot, at, players_tracked,
trophies_earned, rates} with `rates` in the order of `trophies`. The program writes <id>.out:
{"trophies": [{"id": 1, "q": [q05, q25, q50, q75, q95]}, ...]}, five quantiles of each trophy's
earn rate (percent) at the case's target, scored by mean pinball loss on the logit scale.

Why not the house baselines. The house baseline is persistence (last rate, random-walk spread,
sigma 0.5/sqrt-day); the house curve baseline fits logit(rate) against ln(1 + hours since
2026-11-19T00:00Z) over only the last 24 h of reads, per trophy, unshrunk. Two facts of this
page punish both:

  1. Exophase refreshes in steps. The page sat unchanged at 638 tracked players from
     2026-11-18T23:48Z through 2026-11-19T04:00Z, then refreshed to 3,868 tracked players by
     04:30Z and every rate but the 100% one fell, because a rate is earners / tracked players
     and the denominator jumped ~6x while earners barely moved. Reads before a refresh carry a
     different denominator and far coarser rounding (a 0.01-point step at 638 players is a
     sixteenth of a person; at 30,000 players it is 3 people), so this program weights each
     read by its tracked-player count and compresses the history to the reads that changed.
  2. Per-trophy slopes from rounded 2-decimal rates are noisy; an unshrunk line chases noise
     for 46 bronze trophies at once. This program shrinks every trophy's slope toward the
     cross-trophy median slope (a Bayesian-style precision-weighted average, prior sd 0.3),
     damps the extrapolated move 20% back toward persistence, and caps the median with
     base-rate sanity bounds (below).

Model, per trophy i:
  - distinct reads j (the (players_tracked, rates) pair changed), times t_j, counts N_j;
  - x_j = ln(1 + hours from the first read to t_j); y_j = logit(rate_ij), rate clamped to
    0.01..99.99 as the scorer clamps;
  - weighted least squares y = a + b*x with weights w_j = (N_j / N_last) * 0.5^(age_j / 72 h):
    proportion noise scales with 1/N, and a 72-hour recency half-life keeps launch-night's
    stale denominator from ruling the fit while still informing the slope;
  - slope b shrunk toward the cross-trophy median slope b_med by precision weighting
    (likelihood variance from the fit's residuals, prior variance 0.3^2);
  - median logit at the target = logit(last rate) + 0.8 * (fitted logit at x_target - fitted
    logit at x_last): the trend's move, damped a fifth of the way back to persistence;
  - sanity caps on the median percent, from published base rates for comparable games
    (see MODEL.md): platinum <= 1.5 (RDR2's platinum sits at 0.44% of tracked players after
    years; GTA VI's needs ~200 h, so a week-one rate above 1.5% is not credible), a
    "100% completion" trophy <= 2.5 (RDR2's 100% trophy: 1.7-5.5% long-run), gold <= 60,
    silver <= 75, bronze <= 97; and relative caps [0.2x, 30x + 5 points] around the last rate;
  - spread sigma (logit sd) = sqrt( (0.45*sqrt(d_days))^2 + residual variance inflated by the
    extrapolation leverage + flat-risk ), where flat-risk adds 0.85^2 when the history holds
    <= 2 distinct reads or a trophy's rate never moved: an unseen Exophase refresh is the
    dominant risk then, as the practice cases show (a ~6x denominator jump is a ~1.8 logit
    shift). Sigma is clamped to [0.30, 1.75];
  - q_tau = inv_logit(median_logit + z_tau * sigma), z = (-1.645, -0.674, 0, 0.674, 1.645),
    rounded to 4 decimals, half up, as the starter rounds.

Deterministic: pure functions of the case file, files processed in name order, no randomness,
no clock, no network. Outside the grader's container, MAKEFUN_INPUT_DIR and MAKEFUN_OUTPUT_DIR
stand in for /input and /output.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module shipped beside this
# file could be imported (this entry is a single file, but the line costs nothing).
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

RECENCY_HALF_LIFE_H = 72.0     # recency weight half-life for the trend fit
PRIOR_SLOPE_SD = 0.3           # prior sd of a trophy's logit slope (per ln-hour unit)
DAMPING = 0.8                  # keep 80% of the trend's move, 20% back to persistence
RW_SIGMA = 0.45                # random-walk spread per sqrt-day, logit units
FLAT_RISK_SD = 0.85            # extra spread when the history shows no movement to learn from
SIGMA_MIN, SIGMA_MAX = 0.30, 1.75


def clamp_rate(x: float) -> float:
    return min(99.99, max(0.01, x))


def logit(pct: float) -> float:
    p = clamp_rate(pct)
    return math.log(p / (100.0 - p))


def inv_logit(lg: float) -> float:
    if lg >= 0:
        return 100.0 / (1.0 + math.exp(-lg))
    e = math.exp(lg)
    return 100.0 * e / (1.0 + e)


def round4(x: float) -> float | int:
    """x rounded to 4 decimals, half up, as the starter rounds (whole numbers as ints)."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if float(value).is_integer() else value


def parse_time(text: str) -> float:
    """ISO-8601 timestamp (the case's slots and targets) to epoch seconds."""
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def tier_cap(trophy: dict) -> float:
    """Base-rate sanity cap (percent) on a trophy's week-one median; see MODEL.md."""
    desc = (trophy.get("description") or "").lower()
    if trophy.get("tier") == "platinum":
        return 1.5
    if "100% completion" in desc or "100% complete" in desc:
        return 2.5
    return {"gold": 60.0, "silver": 75.0, "bronze": 97.0}.get(trophy.get("tier"), 97.0)


def distinct_reads(history: list[dict]) -> list[dict]:
    """Compress the history to the reads where the page actually changed.

    Exophase refreshes in steps, so long runs of reads are byte-identical; a run of identical
    reads is one observation, and keeping every copy would fake a sample size the fit does
    not have. A read is kept when its (players_tracked, rates) pair differs from the last
    kept read's.
    """
    kept: list[dict] = []
    last_key = None
    for read in history:
        key = (read.get("players_tracked"), tuple(read.get("rates") or ()))
        if key != last_key:
            kept.append(read)
            last_key = key
    return kept


def wls(xs: list[float], ys: list[float], ws: list[float]):
    """Weighted least squares y = a + b*x. Returns (a, b, resid_var, sxx, x_bar, w_sum)."""
    w_sum = sum(ws)
    x_bar = sum(w * x for x, w in zip(xs, ws)) / w_sum
    y_bar = sum(w * y for y, w in zip(ys, ws)) / w_sum
    sxx = sum(w * (x - x_bar) ** 2 for x, w in zip(xs, ws))
    if sxx <= 1e-12:
        return y_bar, 0.0, 0.0, sxx, x_bar, w_sum
    sxy = sum(w * (x - x_bar) * (y - y_bar) for x, y, w in zip(xs, ys, ws))
    b = sxy / sxx
    a = y_bar - b * x_bar
    dof = max(1.0, w_sum - 2.0)
    resid = sum(w * (y - (a + b * x)) ** 2 for x, y, w in zip(xs, ys, ws)) / dof
    return a, b, resid, sxx, x_bar, w_sum


def forecast_case(case: dict, name: str) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    history = case["history"]
    if not history:
        raise ValueError(f"{name} has no history")
    trophies = case["trophies"]
    reads = distinct_reads(history)
    t0 = parse_time(reads[0].get("slot") or reads[0].get("at"))
    t_last = parse_time(reads[-1].get("slot") or reads[-1].get("at"))
    t_target = parse_time(case["target"])
    n_last = reads[-1].get("players_tracked") or 1
    d_days = max(0.0, (t_target - t_last) / 86400.0)

    def x_of(epoch: float) -> float:
        return math.log1p(max(0.0, (epoch - t0) / 3600.0))

    x_target = x_of(t_target)
    x_last = x_of(t_last)

    # Per-trophy weighted fits (first pass), so slopes can be shrunk toward their median.
    fits = []
    for i in range(len(trophies)):
        xs, ys, ws = [], [], []
        for read in reads:
            rates = read.get("rates") or []
            rate = rates[i] if i < len(rates) else None
            if rate is None:
                continue
            t_read = parse_time(read.get("slot") or read.get("at"))
            n_read = read.get("players_tracked") or n_last
            age_h = max(0.0, (t_last - t_read) / 3600.0)
            w = (n_read / n_last) * (0.5 ** (age_h / RECENCY_HALF_LIFE_H))
            xs.append(x_of(t_read))
            ys.append(logit(rate))
            ws.append(w)
        fits.append((xs, ys, ws, wls(xs, ys, ws) if len(xs) >= 2 else None))
    slopes = [f[3][1] for f in fits if f[3] is not None and f[3][3] > 1e-9]
    b_med = median(slopes) if slopes else 0.0

    rows = []
    for i, trophy in enumerate(trophies):
        xs, ys, ws, fit = fits[i]
        last_rates = reads[-1].get("rates") or []
        last_rate = last_rates[i] if i < len(last_rates) else None
        base_logit = logit(last_rate if last_rate is not None else 0.0)
        moved = len(set(ys)) > 1
        flat_risk = (FLAT_RISK_SD ** 2) if (len(reads) <= 2 or not moved) else 0.0
        resid_var = 0.0
        med_logit = base_logit
        if fit is not None and fit[3] > 1e-9:
            a, b, resid_var, sxx, x_bar, w_sum = fit
            # Shrink the slope toward the cross-trophy median by precision weighting.
            se_b2 = resid_var / sxx if sxx > 0 else 1.0
            prec_fit = 1.0 / (se_b2 + 0.04)
            prec_prior = 1.0 / (PRIOR_SLOPE_SD ** 2)
            b_shrunk = (b * prec_fit + b_med * prec_prior) / (prec_fit + prec_prior)
            pred_move = b_shrunk * (x_target - x_last)
            med_logit = base_logit + DAMPING * pred_move
            leverage = 1.0 + (x_target - x_bar) ** 2 / sxx
            resid_var = resid_var * leverage
        # Sanity caps on the median, in percent: tier base rates and a relative band.
        med_pct = inv_logit(med_logit)
        cap = tier_cap(trophy)
        lo = 0.01
        if last_rate is not None:
            cap = min(cap, max(last_rate * 30.0, last_rate + 5.0))
            # A cap bounds growth, never a level already observed (the 100% trophy).
            cap = max(cap, last_rate)
            lo = max(0.01, min(last_rate * 0.2, last_rate))
        med_pct = min(cap, max(lo, med_pct))
        med_logit = logit(med_pct)
        sigma = math.sqrt((RW_SIGMA * math.sqrt(d_days)) ** 2 + resid_var + flat_risk)
        sigma = min(SIGMA_MAX, max(SIGMA_MIN, sigma))
        q = sorted(round4(inv_logit(med_logit + z * sigma)) for z in Z)
        rows.append({"id": trophy["id"], "q": q})
    return {"trophies": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
