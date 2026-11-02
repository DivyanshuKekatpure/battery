# Model specification: fast charging and smartphone battery degradation

**Phase 2 draft, for approval.** Parameter IDs refer to `outputs/parameters.csv`. Only rows with
`verified = yes` are used. P26–P29 were added in this phase, after Phase 1 was approved; they are
flagged below and need your approval too.

## 1. What is simulated

- **Unit:** one smartphone battery.
- **Inputs per battery:** a scenario, which is a charge rate, an ambient temperature, a charge limit
  and a charging method.
- **Outputs per battery:**
  - minutes to 80% charge
  - peak battery temperature (°C)
  - cycles to 80% health
  - health at 500 cycles
  - health at 1000 cycles
- **Randomness:** per-battery variation in life and charge time. One master seed (20261028) feeds
  a NumPy `default_rng`, and the seed is written to the run log.

## 2. Status of each model component

| Component | Proposed source | Status |
|---|---|---|
| Baseline life distribution | P26, P27 (Severson Weibull regression) | **Usable**, with extrapolation (LFP → LCO, 30 °C chamber) |
| Charge-rate effect on life | P28 (Weibull) or P06 (least squares) | **Usable**, with extrapolation: tested rates are 3.18–5.34 C, scenarios are 1–3 C |
| Ambient-temperature effect on life | Diao condition matrix (U01) | **Blocked**: Diao PDF not provided |
| Diao temperature × charge-extent interaction | U03 | **Blocked** |
| Charge-window effect (80% vs 100%) | Saxena 2016 / CALCE PL (U04) | **Blocked**: PDF missing, PL data unreadable |
| Multistage effect on life | Liu & Luo 2010 (U07) | **Blocked**; Tahir 2024 has no ageing test |
| Health vs cycles curve | P29 (Severson normalised fade curve) | **Usable** down to 80% health only |
| Charge time, CC-CV | P09 | **Usable**, with extrapolation |
| Charge time, multistage | P22 (25 °C), P23 (35 °C) | **Usable**, with extrapolation |
| Cell temperature vs C-rate | P10/P11 (Severson); Huang (U06) | **Blocked below about 2C**: P10/P11 predict a negative rise there; Huang not provided |
| Natural vs forced convection | Huang (U06) | **Blocked** |

## 3. Submodels

### 3.1 Life: cycles to 80% health

Life L (in equivalent full cycles) follows a Weibull distribution:

```
L ~ Weibull(shape = β, scale = η(scenario))
η(scenario) = η_ref · exp(b · (r − r_ref)) · F_T(T_amb) · F_W(limit) · F_M(method)
```

- **β = 2.595** (P26). 95% CI [2.285, 2.947].
- **η_ref = 820.2 cycles** at r_ref = 4.74C (P27). 95% CI [759.3, 886.1].
- **b = −0.5309** per 1C of average charge rate (P28). 95% CI [−0.7232, −0.3387].
- **r** is the average charge rate from 0 to 80%. For CC-CV, this is the CC rate (1, 2 or 3C).
  For multistage, Tahir's profile has the same 2.262C average as its CC-CV comparison, so r is
  taken as the nominal scenario rate. That's an assumption (A5).
- **F_T, F_W and F_M** are the temperature, window and method factors. **They have no verified
  source** (§2), so the model can't include them. See decision D1.

**Parameter uncertainty:** each simulated scenario draws its β, η_ref and b once, from a normal
approximation on the log scale of the MLE. That propagates fitting uncertainty, not just
battery-to-battery spread. The draws are reproducible from the seed.

### 3.2 Health against cycles

- **Up to end of life:** health(n) = c(n / L) for n ≤ L. Here c(f) is the median normalised fade
  curve (P29), interpolated linearly over f = 0, 0.05, …, 1. Health is Q / Q_nominal, where c(0) =
  0.972 and c(1) = 0.800.
- **After end of life (n > L):** health is **not modelled**. Severson cells stop cycling at end
  of life, so there's no data past it. The output is recorded as `"<0.80 (past EOL)"`, plus a
  flag, and isn't treated as a number.
- **Spread:** battery-to-battery variation in health comes only from L. The curve shape is held at
  its median; the 5–95% band in P29 is reported for context only.

### 3.3 Charge time: minutes to 80%

```
t80_CCCV = k · 0.8 · 60 / r        with k ~ Normal(1.061, 0.0879) per battery   (P09)
t80_MS   = t80_CCCV · ρ(T_amb)     ρ = 0.8976 at 25 °C (P22), 0.9258 at 35 °C (P23)
```

- **Charge limit:** it doesn't affect time to 80%, because charging to either 80% or 100% passes
  80% at the same point.
- **Other temperatures:** ρ at 10 °C and 40 °C uses the nearest tested value (25 °C and 35 °C).
  That's an extrapolation (A6).
- **Caveat:** Tahir's ρ compares **full-charge** times, not time to 80% (A7).

### 3.4 Peak battery temperature

The proposed form was T_peak = T_amb + ΔT(r), with ΔT anchored to Huang 2019. **It's blocked:**
- Huang 2019 isn't available.
- The Severson fit (P10, P11: ΔT = −2.02 + 1.053·r) is negative below about 1.9C, and its R² is
  only 0.073.
- Tahir gives one rate only (7.8 °C max rise at 2.262C, P16), which isn't enough to set a C-rate
  dependence. See decision D2.

### 3.5 Diao temperature-by-charge-extent interaction

**Blocked** (U01, U03). Per-condition Weibull fits exist (`outputs/tables/diao_condition_fits.csv`,
rows D100+), but nothing maps condition IDs to temperatures.

## 4. Validation

**Baseline scenario:** 25 °C, 0–100%, 1C CC-CV. The life model gives:

| | η (cycles) | Median life | P(L < 500) | P(L < 1000) |
|---|---|---|---|---|
| Point estimate (b = −0.531) | 5,974 | **5,187** | 0.002 | 0.010 |
| b at its 95% CI upper bound (−0.339) | 2,911 | 2,528 | 0.010 | 0.061 |
| b at its 95% CI lower bound (−0.723) | 12,263 | 10,647 | <0.001 | 0.002 |

**Result: the baseline fails validation.** Apple rates 500 cycles (iPhone 14 and earlier, P01) and
1000 cycles (iPhone 15 models, P02) to 80% under ideal conditions. The model predicts a **median
of 5,187 cycles**, 5 to 10 times higher. Even the most pessimistic end of the slope's CI (2,528)
is 2.5 times Apple's 1000-cycle rating. **No parameters were tuned.**

Likely causes, in order of my confidence:
1. **Chemistry.** These are LFP cells, which are known for long cycle life; phones use
   LCO-family cells. This is exactly the mismatch the Diao (LCO) data was meant to fix.
2. **Extrapolation below the tested rates.** 1C is 2.2C below the slowest tested average (3.18C).
   The exponential rate law has no support there.
3. **Different definitions.** Apple's "ideal conditions" and "complete charge cycles" aren't
   specified, and Severson cells also had a 4C discharge every cycle.

**Implication:** absolute life numbers from this model aren't credible for phones. *Relative*
comparisons between scenarios depend only on b and β. With the life factors that can be modelled,
the model is internally consistent, but every relative effect is an LFP→LCO extrapolation.

## 5. Assumptions and extrapolations to disclose

| ID | Assumption or extrapolation |
|---|---|
| A1 | LFP (Severson) life, rate law and fade shape applied to LCO phone cells |
| A2 | Rate law applied at 1–3C, outside the tested 3.18–5.34C |
| A3 | Severson's 30 °C chamber life used as the 25 °C baseline (no temperature correction is available) |
| A4 | Apple's 1000-cycle rating stated for "iPhone 15 models" only |
| A5 | Multistage average rate treated as equal to the nominal scenario rate |
| A6 | Tahir's charge-time ratio at 25/35 °C applied at 10 and 40 °C |
| A7 | Tahir's full-charge time ratio applied to time to 80% |
| A8 | Health after end of life isn't modelled; it's reported as below 80% |
| A9 | Parameter uncertainty uses a normal approximation of the MLE on the log scale |

## 6. Decisions I need from you (CHECKPOINT)

- **D1. Factors with no verified life effect** (ambient temperature, charge limit, method). Options:
  - **(a) Recommended:** keep all 36 scenarios, but these three factors affect only the outputs
    they have sources for. Method affects charge time; temperature affects nothing yet. Their
    life effects are reported as "not modelled". Their ANOVA rows would show effects of exactly
    zero by construction, so I'd flag rather than interpret them.
  - **(b)** Wait for Diao, Saxena and Liu & Luo before running Phase 3.
  - **(c)** Set the factors to 1 and present that as "no effect". Not recommended: it would
    present an assumption as a finding.
- **D2. Peak temperature.** Either leave it out until Huang arrives, or use the Severson fit only
  at 3C, the one level near its range, and leave 1C and 2C blank.
- **D3. Validation failure.** Proceed knowing absolute lives aren't credible, using relative
  effects only? Or stop until the Diao mapping lets an LCO baseline replace Severson?
- **D4.** Approve the new parameters P26–P29.
