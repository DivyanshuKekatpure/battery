# Preliminary Methods and Results

## Measures

We measure standardized discharge capacity in ampere-hours and capacity retention relative to each cell's first valid reference measurement. The primary endpoint is equivalent-full-cycle exposure until capacity first falls below 80% of that initial measurement. Because reference tests are intermittent, a crossing is an interval between observations; cells without a crossing are right-censored. Equivalent full cycles (EFC) equal average cumulative charging and discharging throughput divided by nominal 3 Ah capacity, with baseline exposure subtracted. Total exposure includes diagnostic operations; operating-only exposure is a sensitivity measure. Predictors are charging rate, regular-operation charging cap, and controlled bath temperature. Observed trajectories and endpoint coverage describe the experimental evidence. Life ratios, median lifetimes, survival probabilities, and their confidence intervals are explicitly model estimates, not additional measurements (Luh & Blank, 2024).

## Assumptions

The 72 selected cells represent this KIT experiment, not smartphone batteries generally. We assume a common Weibull shape and independent cell variation conditional on experimental conditions; shared baths limit independent temperature replication. Upper voltage represents an approximate 90% or 100% cap, not a continuously recalibrated SOC limit. Capping also changes cycle depth, so it does not isolate one degradation mechanism. Diagnostic tests periodically charge both groups fully. Missing capacities remain missing, and incomplete lifetimes remain censored. Three flagged cold measurements and the final manual check-up are excluded initially. Alternative models and inclusion rules assess sensitivity. Smartphone financial projections additionally assume transferable lifetime, constant usage, and fresh replacement batteries; these assumptions are not validated observations.

## Model / approach

We analyzed the downloaded KIT version 2 result data, not simulated cell observations (Luh & Blank, 2024). Selection fixed discharge at 1C and the lower voltage at 3.249 V, leaving three charging rates (1/3C, 1C, 5/3C), two upper limits (approximately 90%, 100%), four bath temperatures (0, 10, 25, 40°C), and three physical replicates in each of 24 combinations. We verified archive checksums, mapped termination reasons from the supplied workbook, and linked reference capacities to original CSV rows.

An accelerated-failure-time regression models log lifetime scale using categorical factors and all two-factor interactions; 1C, 100%, and 25°C define the reference. A common Weibull shape pools information across sparse groups. Interval likelihoods retain uncertain crossing times, while survival likelihoods retain cells that stopped before a crossing. No midpoint is substituted as an observed failure. We resampled whole cells within conditions 2,000 times, refitting each sample to obtain nominal percentile confidence intervals. Repeated check-ups are not independent replicates.

Approximate likelihood-ratio tests assess the three interactions with Holm correction. Balanced three-fold validation withholds one replicate per condition and scores its censored predictive likelihood. Prespecified sensitivities use a lognormal distribution, rated-capacity normalization, operating-only throughput, flagged/final measurements, and pessimistic shutdown events. These checks assess dependence on model and censoring choices; they cannot establish smartphone transfer. Tables distinguish observed or derived endpoints from model estimates.

## Results

The primary dataset contains 72 cells and 859 retained reference-capacity measurements. There are 63 observed threshold-crossing intervals and 9 right-censored endpoints. Exclusions comprise 11 final-manual and three cold records within selected cells; no capacity readings were imputed. Individual trajectories show substantial variation despite identical nominal settings. Three cells per combination remain the experimental replication, regardless of bootstrap count.

At 25°C, the Weibull model estimates median life at 100% charging as 1,913, 1,244, and 563 EFC for 1/3C, 1C, and 5/3C respectively. Corresponding 90%-cap medians are 3,037, 2,226, and 1,127 EFC. For the prespecified 5/3C cap comparison, nominal 95% intervals are [371, 790] EFC without the cap and [561, 1,323] EFC with it. The estimated life ratio is 2.00 [95% CI 1.31, 2.92]. This is a model-based comparison, not an observed doubling for every cell.

At the reference 1C/25°C condition, the cap coefficient on log lifetime scale is 0.582 [95% CI 0.422, 0.779]. The charging-rate-by-temperature interaction is supported by an approximate likelihood-ratio statistic of 75.53 on six degrees of freedom (Holm-adjusted p < 0.001). Rate-by-cap and cap-by-temperature tests have adjusted p-values 0.372 and 0.372. These nonsignificant interactions do not establish equal cap benefits everywhere. Individual contrast intervals are nominal, without multiplicity adjustment.

At 5/3C without the cap, estimated median life is 48 EFC at 0°C and 734 EFC at 40°C, compared with 563 EFC at 25°C. This variation makes a single temperature-independent charging-rate penalty inappropriate. In the measured 25°C baseline group, two cells cross within intervals ending near 408 and 416 EFC, while the third remains uncrossed at approximately 606 EFC. The capped group also varies substantially. These observations explain why a pooled fitted median cannot be described as the actual lifetime of any individual cell.

All 2,000 bootstrap fits converged. However, held-out prediction exposes important model dependence: summed log likelihood is -463.6 for Weibull versus -152.7 for lognormal; higher is better. We retain the prespecified Weibull results but do not interpret their intervals as covering distributional uncertainty. The lognormal sensitivity estimates 5/3C median life at 473 EFC for 100% charging and 876 EFC for the cap. Direction agrees, but magnitude changes.

At 1/3C/25°C, all three capped cells remain above the threshold; their estimated median therefore extends beyond observed follow-up. Fault-related shutdowns also challenge independent censoring. Temperature findings are conditional on one apparatus, and controlled liquid cooling differs from phone operation. The experiment supports a cap-and-rate comparison in these NMC/graphite-SiO cells. It does not establish absolute smartphone life or an independently replicated causal temperature effect. Smartphone validation is the appropriate next investment before operational rollout.

## Supporting results

Table 1. Derived endpoint coverage after prespecified exclusions. Crossings are intervals, not exact failures.

| Bath °C | Cells | Crossings | Right-censored |
| --- | --- | --- | --- |
| 0 | 18 | 16 | 2 |
| 10 | 18 | 17 | 1 |
| 25 | 18 | 14 | 4 |
| 40 | 18 | 16 | 2 |

Table 2. Model-estimated Weibull AFT coefficients and nominal 95% bootstrap intervals. Log scale concerns life/1000 EFC; reference 1C, 100%, 25°C. No individual coefficient p-values are claimed.

| Term | Estimate | 95% CI |
| --- | --- | --- |
| Intercept | 0.271 | [0.206, 0.345] |
| rate_1third | 0.430 | [0.335, 0.501] |
| rate_5third | -0.792 | [-1.224, -0.478] |
| cap90 | 0.582 | [0.422, 0.779] |
| temp0 | -2.262 | [-2.349, -2.164] |
| temp10 | -1.254 | [-1.342, -1.144] |
| temp40 | -0.431 | [-0.599, -0.330] |
| rate_1third:cap90 | -0.119 | [-0.196, -0.041] |
| rate_5third:cap90 | 0.111 | [-0.234, 0.386] |
| rate_1third:temp0 | 0.677 | [0.596, 0.768] |
| rate_1third:temp10 | 0.110 | [0.032, 0.214] |
| rate_1third:temp40 | -0.332 | [-0.435, -0.164] |
| rate_5third:temp0 | -0.200 | [-0.421, 0.200] |
| rate_5third:temp10 | -0.239 | [-0.704, 0.233] |
| rate_5third:temp40 | 0.695 | [0.303, 1.202] |
| cap90:temp0 | 0.255 | [0.036, 0.424] |
| cap90:temp10 | 0.137 | [-0.178, 0.302] |
| cap90:temp40 | 0.284 | [0.060, 0.526] |
| log_shape | 1.949 | [1.844, 2.560] |

Table 3. Approximate interaction likelihood-ratio tests; three-test Holm correction.

| Interaction | LR | df | Raw p | Holm p |
| --- | --- | --- | --- | --- |
| rate:cap | 3.13 | 2 | 0.209 | 0.372 |
| rate:temp | 75.53 | 6 | 2.98e-14 | 8.94e-14 |
| cap:temp | 4.81 | 3 | 0.186 | 0.372 |

Table 4. Model-estimated median life at 25°C; nominal 95% intervals. *Median exceeds maximum follow-up in that condition.

| Rate | Cap | Median EFC | 95% CI |
| --- | --- | --- | --- |
| 1/3C | 100% | 1,913 | [1,782, 2,069] |
| 1/3C | 90% | 3,037* | [2,763, 3,584] |
| 1C | 100% | 1,244 | [1,170, 1,358] |
| 1C | 90% | 2,226 | [1,971, 2,699] |
| 5/3C | 100% | 563 | [371, 790] |
| 5/3C | 90% | 1,127 | [561, 1,323] |

![Figure 1. Measured reference capacities at 25°C. Connecting lines only link observations; they do not impute missing values.](../kit/figures/observed_25C.png)

![Figure 2. Model-estimated lifetime medians and nominal 95% bootstrap intervals. Panels use different vertical scales; temperature effects are conditional on shared bath apparatus.](../kit/figures/modeled_life_by_temperature.png)

![Figure 3. Derived lifetime intervals at 25°C. Right-pointing triangles denote right-censored cells.](../kit/figures/observed_intervals_25C.png)

## References

Luh, M., & Blank, T. (2024). Comprehensive battery aging dataset: capacity and impedance fade measurements of a lithium-ion NMC/C-SiO cell. Scientific Data, 11, 1004. https://doi.org/10.1038/s41597-024-03831-x. Version 2 result data: https://doi.org/10.35097/1969; supplied README, data dictionary and cell overview. CC BY 4.0; analysis adapted by this project.
