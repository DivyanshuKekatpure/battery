# Preliminary Methods and Results

## Measures

We measure standardized discharge capacity in ampere-hours, then divide by each cell's first valid reference capacity to calculate retention. Our main outcome is equivalent full cycles (EFC) until capacity first falls below 80% of that starting value. Tests are intermittent. We therefore bracket crossings between observations and right-censor cells that haven't crossed. EFC equals average cumulative charging and discharging throughput divided by nominal 3 Ah capacity, after subtracting baseline exposure. We include diagnostic operations and test operating-only exposure separately. We compare charging rate, regular-operation charging cap, and controlled bath temperature. Individual histories and threshold coverage show what we observed; life ratios, median lifetimes, survival probabilities and their confidence intervals come from the model (Luh & Blank, 2024).

## Assumptions

These 72 cells tell us about the KIT experiment. Generalizing to smartphones requires validation. We assume a common Weibull shape and independent cell variation within conditions, although shared baths limit independent temperature replication. Upper voltage gives approximate 90% or 100% caps without continuously recalibrating SOC. Capping changes cycle depth too, preventing isolation of one degradation mechanism. Diagnostics periodically charge both groups fully. We leave missing capacities missing and incomplete lifetimes censored, excluding three flagged cold measurements and the final manual check-up from primary analysis. Alternative models and inclusion rules test sensitivity. Phone projections assume transferable lifetime, constant usage and fresh replacement batteries. These assumptions remain unvalidated.

## Model / approach

We selected 72 KIT cells across 1/3C, 1C and 5/3C charging, approximately 90%/100% caps, and 0, 10, 25 and 40°C baths: three replicates per combination (Luh & Blank, 2024). We fixed discharge at 1C, lower voltage at 3.249 V and upper voltages at 4.092/4.200 V. Checksums verify files; source-row links trace measurements.

We fitted a Weibull accelerated-failure-time model: S(t|x)=exp[-(t/eta(x))^k], t≥0, location zero, common shape k. Scale eta(x)=1000 exp(X beta) EFC is the 63.2% failure quantile; median life equals eta(x)(ln 2)^(1/k). X includes an intercept, binary rate_1third/rate_5third, cap90, temp0/temp10/temp40 indicators and all cross-factor two-way products. Indicators equal zero at reference 1C/100%/25°C; logarithms are natural. Tables give fitted parameters.

Interval likelihoods use measured crossing brackets; survival likelihoods handle right-censored cells. We neither substitute midpoint failure times nor discard incomplete cases. Using seed 20261101, we refitted 2,000 whole-cell bootstrap samples within conditions, preserving joint shape/scale dependence when transforming parameters for percentile intervals. Repeated measurements aren't independent replicates.

We tested interactions with Holm-adjusted likelihood-ratio tests. Three-fold validation withholds one replicate per condition; sensitivity checks vary capacity normalization, throughput, flagged/final measurements and shutdown assumptions. The lognormal alternative uses log(L/1000)=X beta_LN+sigma Z, Z standard normal, sigma=0.181; its scale equals its median (reference 1,233 EFC). Secondary estimates have no bootstrap intervals.

## Results

We analyzed 859 measurements from 72 cells, giving 63 threshold-crossing intervals and 9 right-censored endpoints. We excluded eleven final-manual and three cold measurements without imputing any values. Figure 1 shows histories; Figure 3 marks censoring with triangles.

At 25°C, uncapped median-life estimates are 1,913, 1,244 and 563 EFC at 1/3C, 1C and 5/3C. With capping, they rise to 3,037, 2,226 and 1,127. At 5/3C, that's a life ratio of 2.00 (nominal 95% CI 1.31–2.92); median intervals are 371–790 EFC uncapped and 561–1,323 capped. These describe fitted distributions. They aren't observed individual lifetimes.

The common shape is 7.02; reference scale is 1,311 EFC. At 1C/25°C, cap90's coefficient is 0.58 (95% CI 0.42–0.78). Rate-by-temperature gives LR=75.53, six degrees of freedom, Holm-adjusted p<0.001. Rate-by-cap and cap-by-temperature adjusted p-values are both 0.372; neither establishes identical benefits. With three cells per condition, within-condition resampling likely understates uncertainty: several Table 3 interaction intervals exclude zero although Table 4 tests don't. We base interaction conclusions on Table 4.

Temperature matters here. At uncapped 5/3C, modeled median life is 48 EFC at 0°C, 563 at 25°C and 734 at 40°C (Figure 2), so this model doesn't support a temperature-independent rate penalty.

All 2,000 bootstrap fits converged. But Weibull predicted poorly: held-out log likelihood totals -463.6, versus -152.7 for lognormal (higher is better). Two cells that outlived predictions, P040_1 (10°C, 5/3C, 90%) and P060_3 (40°C, 5/3C, 100%), contribute -321.7; Weibull's steep shape makes such lives very unlikely. Without them, totals are -141.9 versus -130.1. We deliberately keep prespecified Weibull, with lognormal as the main robustness check.

None of the three capped 1/3C/25°C cells crossed the threshold, so their estimated median exceeds measured follow-up. Fault-related shutdowns challenge independent censoring. Shared baths limit temperature replication, while full diagnostic charges and cylindrical, liquid-cooled cells restrict smartphone transfer. We need smartphone-cell validation before promising quantitative phone lifetimes.

Nominal intervals assume the distribution and common shape. A positive fitted cap effect establishes neither a precise population benefit nor smartphone transfer.

Table 1. Derived endpoint coverage.

| Bath °C | Cells | Crossings | Right-censored |
| --- | --- | --- | --- |
| 0 | 18 | 16 | 2 |
| 10 | 18 | 17 | 1 |
| 25 | 18 | 14 | 4 |
| 40 | 18 | 16 | 2 |

Table 2. Estimated Weibull parameters: reference 1C/100%/25°C; location fixed.

| Parameter | Estimate | 95% CI |
| --- | --- | --- |
| Shape k | 7.02 | 6.32–12.94 |
| Scale eta (EFC) | 1,311 | 1,229–1,412 |
| Median (EFC) | 1,244 | 1,170–1,358 |
| Location (EFC) | 0 | Fixed |

Table 3. Fitted coefficients: bootstrap SE/CIs; intercept=log(reference eta/1000); log_shape=log(k).

| Term | Estimate | SE | 2.5% | 97.5% |
| --- | --- | --- | --- | --- |
| Intercept | 0.27 | 0.04 | 0.21 | 0.34 |
| rate_1third | 0.43 | 0.04 | 0.33 | 0.50 |
| rate_5third | -0.79 | 0.21 | -1.22 | -0.48 |
| cap90 | 0.58 | 0.09 | 0.42 | 0.78 |
| temp0 | -2.26 | 0.05 | -2.35 | -2.16 |
| temp10 | -1.25 | 0.05 | -1.34 | -1.14 |
| temp40 | -0.43 | 0.07 | -0.60 | -0.33 |
| rate_1third:cap90 | -0.12 | 0.04 | -0.20 | -0.04 |
| rate_5third:cap90 | 0.11 | 0.16 | -0.23 | 0.39 |
| rate_1third:temp0 | 0.68 | 0.04 | 0.60 | 0.77 |
| rate_1third:temp10 | 0.11 | 0.05 | 0.03 | 0.21 |
| rate_1third:temp40 | -0.33 | 0.07 | -0.43 | -0.16 |
| rate_5third:temp0 | -0.20 | 0.17 | -0.42 | 0.20 |
| rate_5third:temp10 | -0.24 | 0.24 | -0.70 | 0.23 |
| rate_5third:temp40 | 0.69 | 0.24 | 0.30 | 1.20 |
| cap90:temp0 | 0.26 | 0.10 | 0.04 | 0.42 |
| cap90:temp10 | 0.14 | 0.12 | -0.18 | 0.30 |
| cap90:temp40 | 0.28 | 0.12 | 0.06 | 0.53 |
| log_shape | 1.95 | 0.19 | 1.84 | 2.56 |

Table 4. Approximate interaction tests; Holm correction.

| Interaction | LR | df | Raw p | Holm p |
| --- | --- | --- | --- | --- |
| rate:cap | 3.13 | 2 | 0.209 | 0.372 |
| rate:temp | 75.53 | 6 | 2.98e-14 | 8.94e-14 |
| cap:temp | 4.81 | 3 | 0.186 | 0.372 |

Table 5. Estimated 25°C lifetimes/scales; *median beyond measured follow-up.

| Rate | Cap | eta/EFC | 95% CI | Median/EFC | 95% CI |
| --- | --- | --- | --- | --- | --- |
| 1/3C | 100% | 2,015 | 1,862–2,160 | 1,913 | 1,782–2,069 |
| 1/3C | 90% | 3,200 | 2,866–3,764 | 3,037* | 2,763–3,584 |
| 1C | 100% | 1,311 | 1,229–1,412 | 1,244 | 1,170–1,358 |
| 1C | 90% | 2,345 | 2,058–2,819 | 2,226 | 1,971–2,699 |
| 5/3C | 100% | 594 | 388–820 | 563 | 371–790 |
| 5/3C | 90% | 1,187 | 581–1,372 | 1,127 | 561–1,323 |

![Figure 1. Measured 25°C retention; lines connect observations.](../kit/figures/observed_25C.png)

![Figure 2. Estimated medians/95% intervals; panel scales differ.](../kit/figures/modeled_life_by_temperature.png)

![Figure 3. Derived 25°C intervals; triangles indicate censoring.](../kit/figures/observed_intervals_25C.png)

## References

Luh, M., & Blank, T. (2024). Comprehensive battery aging dataset: capacity and impedance fade measurements of a lithium-ion NMC/C-SiO cell. Scientific Data, 11, 1004. https://doi.org/10.1038/s41597-024-03831-x. Version 2 result data: https://doi.org/10.35097/1969; supplied README, data dictionary and cell overview. CC BY 4.0; analysis adapted by this project.
