# Results summary: does fast charging make smartphone batteries degrade faster?

Six Sigma simulation study (course project, Cornell). Seed 20261028 for every phase. Parameter IDs
refer to `outputs/parameters.csv`; tables are in `outputs/tables/`, figures in `outputs/figures/`.
Decisions are logged in `docs/decision_log.md`.

## Answer

**In this model, yes: faster charging shortens battery life.** Going from 1C to 3C cuts the median
cycles to 80% health from 5,237 to 1,811, about 65% fewer. **Read this as a direction and a relative
size, not as phone lifetimes.** The life model is fitted to LFP cells charged at 3.2–5.3C, so 1–3C
for a phone's LCO cell is a double extrapolation. Its baseline also predicts lives 5 to 10 times
longer than Apple's ratings.

## Key numbers

### Life (36 scenarios × 1000 batteries)

| Quantity | Value |
|---|---|
| Median cycles to 80% health at 1C / 2C / 3C | 5,237 / 3,080 / 1,811 |
| 3C vs 1C effect on log life (regression) | −1.062, 95% CI [−1.088, −1.035] |
| 2C vs 1C effect on log life | −0.531, 95% CI [−0.558, −0.504] |
| Underlying rate slope (P28, fitted to 124 Severson cells) | −0.531 per C, 95% CI [−0.723, −0.339] |
| Median life at 1C with b at its CI bounds | 2,552 to 10,750 cycles |
| Median life at 3C with b at its CI bounds | 1,296 to 2,531 cycles |
| Share past end of life by 1000 cycles (1C / 2C / 3C) | 0.9% / 3.1% / 13.2% |
| Mean health at 500 cycles (1C / 2C / 3C) | 0.976 / 0.973 / 0.967 |

### ANOVA (type III; F, p, partial η²)

| Response | Rate | Method | Ambient | Limit |
|---|---|---|---|---|
| Minutes to 80% | F = 462,578, p < 1e-300, **0.963** | F = 10,240, p < 1e-300, **0.222** | F = 104.6, p = 5e-46, 0.006 | 0 |
| Cycles to 80% | F = 16,153, **0.473** | 0 | 0 | 0 |
| Log cycles to 80% | F = 15,250, **0.459** | 0 | 0 | 0 |
| Health at 500 | F = 2,037, **0.102** | 0 | 0 | 0 |
| Health at 1000 | F = 4,573, **0.212** | 0 | 0 | 0 |

A zero means the factor has **no verified life effect and isn't modelled**. It is not evidence of no
effect. The ambient effect on charge time exists only because 40 °C uses Tahir's 35 °C multistage
ratio.

### Other results

- **Regression** of log life on all factors with two-way interactions: R² = 0.459, adjusted
  R² = 0.459. Residuals are left-skewed (skew −0.97, excess kurtosis 1.66; Anderson-Darling 50.1
  against a 1% critical value of 1.04). That's expected, because life is Weibull, so the log
  residual is not normal.
- **Strategies at 3C and 25 °C**, each compared with normal fast charging (CC-CV, 100%), median and
  paired bootstrap 95% CI:
  - **Multistage** charges **1.75 min faster**, CI [1.74, 1.76] (17.0 → 15.3 min).
  - **80% limit** changes charge time by 0 and life by 0.
  - Neither changes life, because life effects for these aren't modelled.
- **Reliability at 3C** (identical for all three strategies): β = 2.63 [2.51, 2.76],
  η = 2,088 [2,037, 2,140] cycles, MTTF = 1,855 (SE 24), R(500) = 0.977, R(1000) = 0.866.
- **Control chart** (individuals chart, multistage, health at 500 cycles):
  - CL = 0.967, UCL = 0.996, LCL = 0.938.
  - 33 points fall beyond the limits and the longest one-sided run is 16, so it fails the stability
    rules.
  - Cpk = 5.84 and Ppk = 3.49 against an LSL of 0.80 at Apple's 500-cycle rating (P01). Cp and Pp
    are undefined because the spec is one-sided.
  - 1.8% of batteries are already past end of life at 500 cycles.
- **Ownership cost over 3 years** (766.5 cycles, a renewal process, paired bootstrap, B = 2000):

| Change vs normal fast (3C) | Replacements per owner (before → after) | Difference, battery replaced | Difference, phone replaced |
|---|---|---|---|
| Slower charging, 2C | 0.062 → 0.016 | **−$4.55** [−5.84, −3.37] | **−$36.75** [−47.14, −27.17] |
| Slower charging, 1C | 0.062 → 0.003 | **−$5.84** [−7.33, −4.46] | **−$47.14** [−59.13, −35.96] |
| 80% limit | 0.062 → 0.062 | $0 (not modelled) | $0 |
| Multistage | 0.062 → 0.062 | $0 (not modelled) | $0 |

- **Cost sensitivity:** with the Pro-model battery price ($119 instead of $99), savings rise to
  −$5.47 (2C) and −$7.02 (1C). Battery price is the only input with a sourced range, so no other
  sensitivity could be run.

## Assumptions and extrapolations to disclose

1. LFP (Severson) life, rate law and fade shape are applied to LCO phone cells (A1).
2. The rate law is applied at 1–3C, below the tested 3.18–5.34C (A2).
3. Severson's 30 °C chamber data is used as the 25 °C baseline; no temperature correction (A3).
4. Apple's 1000-cycle rating is stated for "iPhone 15 models" only (A4).
5. Multistage average rate is set equal to the nominal rate (A5). Tahir's 25/35 °C time ratios are
   applied at 10/40 °C (A6), and full-charge ratios are applied to time to 80% (A7). Tahir's cell is
   LFP.
6. Health after end of life isn't modelled (A8).
7. Common random numbers are used, with parameters at point estimates (D011).
8. Peak temperature is reported only at 3C, from an LFP fit with R² = 0.07.
9. Cost assumptions:
   - The same $19 Apple 20W adapter is used for every strategy.
   - In-store service has no extra fee.
   - Battery price $99 comes from a 2024 news report citing Apple.
   - 255.5 cycles/year comes from a review site's estimate (0.7 cycles/day), not peer reviewed.
   - 3 years of ownership is Apple's first-owner assumption.
   - Charge time has no cost assigned: the slower charging that saves money takes 17 → 51 min to
     reach 80%.

## UNVERIFIED (not used)

These items are missing because the PDF wasn't provided, the data couldn't be read, or no primary
source was supplied:

| ID | Item |
|---|---|
| U01 | Cycles to 10% loss by ambient temperature |
| U02 | Fade acceleration after the knee, by temperature |
| U03 | Temperature × charge-extent interaction |
| U04 | Charge-window effect, 20–80% vs 0–100% |
| U05 | Keil & Jossen charge-rate effect on life |
| U06 | Huang temperature rise and convection |
| U07 | Multistage effect on life |
| U08 | Diao nominal capacity and end-of-life definition |
| U09 | Google Pixel rating |

Also not used:
- **All 57 Diao condition fits** (rows D100+), because the conditions can't be mapped to stresses.
- **Peer-reviewed charge-frequency figures** (Clemm et al. 2016; Cordella et al. 2021), which
  couldn't be opened.

## Surprises and doubts

- **The baseline fails validation by a wide margin.** It predicts 5,187 cycles at 1C against
  Apple's 500/1000. Absolute lives and costs are therefore not credible for phones; only the
  direction and relative size of the rate effect are supported, and only for LFP.
- **Savings are small in absolute terms (about $5 over 3 years).** Even at 3C, only 6% of owners
  need a replacement within 766 cycles under this (too optimistic) life model. With LCO-realistic
  lives near Apple's ratings, replacements and savings would be much larger. The Diao LCO data
  could test that once its conditions are mapped.
- **Three of the four factors can't be judged at all.** Temperature, charge limit and multistage
  have no verified life effect, and those are the very levers a phone user controls.
- **The SPC results look odd, but it's the method, not the process.** The control chart signals
  instability and the capability indices look excellent at the same time. Both come from health
  being bounded and skewed, and from excluding batteries already past end of life. An individuals
  chart with normal-theory limits isn't suited to this response.
- **Phone chargers may not be able to deliver these rates.** A 20W adapter probably can't charge a
  current iPhone at 3C, so the "3C" scenario may not exist in phones. This needs the iPhone battery's
  watt-hour rating to check, and that isn't sourced here.
