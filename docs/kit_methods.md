# Prespecified KIT methods

Research question: How do charging rate, a 90% charging cap, and operating temperature affect capacity degradation and equivalent-full-cycle life to 80% of initial capacity in NMC/graphite-SiO lithium-ion cells?

The independent unit is the physical cell. Primary 72-cell design and assumptions K001–K010 are defined in decision_log.md before any fit. Descriptive plots show measured reference capacities; lines only connect observations and are not imputed data. Cell-level first observed threshold crossings remain intervals. Uncrossed cells remain right-censored. Operating bath temperature is not phone ambient air.

MODEL ESTIMATES: AFT log scale = intercept + categorical rate + cap + temperature + all two-way interactions. Weibull shape is common. A lognormal fit uses the same design. Use stable interval probabilities and deterministic multiple starts, with convergence logs. Confidence intervals use 2000 stratified whole-cell bootstrap fits. Require >=95% successful fits. Primary three interaction tests are approximate likelihood-ratio tests, adjusted using Holm. Report modeled survival and life ratios separately from measured cell histories. Three-fold balanced held-out interval log likelihood measures predictive adequacy without inventing true failure dates.

Sensitivity models: rated capacity (3Ah); operating-only EFC; include flagged cold data; include final manual CU; include both; and pessimistic shutdown events for uncrossed fault-stopped cells. Final manual CU is identified by the README May29–Jun1 window. Changes in direction are disclosed. Equipment/safety shutdowns may violate independent censoring; sensitivity is not proof of its validity.

FINANCIAL MODEL ESTIMATES/ASSUMPTIONS: use 25C predicted lifetime distributions in a renewal process. All strategies supply 0.7*365*3=766.5 EFC (not number of partial sessions). Fresh iid replacements; prices fixed per scenario; smartphone lifetime transfer assumed. Numeric renewal expectations and bootstrap intervals are conditional, not observed savings. Price and usage/transfer sensitivity is distinct from sampling CI. Existing charger and zero implementation cost assumed; break-even implementation cost is expected replacement savings. No separate calendar model, no charging-time valuation, no battery-to-phone validation.

Validation: empirical extraction checks, explicit synthetic model-recovery tests, numeric renewal versus labeled simulation, report word counts and numeric provenance, repeatable run. No source or model is selected for favorable savings.

## Explicit distribution parameterization

The fitted Weibull has zero location (fixed), common shape k=exp(theta[-1]) and condition-specific scale eta(x)=1000*exp(X beta) EFC. Survival S(t|x)=exp(-(t/eta(x))^k), t>=0; the median is eta*(ln 2)^(1/k). Eta is the 63.2th percentile, not the mean or median. X uses intercept plus binary indicators for rate 1/3C or 5/3C (reference 1C), cap90 (reference 100), and temperatures 0/10/40C (reference25), and all cross-factor pairs; no three-way interaction.

Reporting original-scale k and eta with nominal percentile CIs transforms each successful bootstrap vector before taking quantiles. Median CIs use the same joint draw; do not combine separate marginal bounds. The lognormal sensitivity uses log(L/1000)=X beta_LN + sigma*Z, Z standard normal, sigma=exp(theta_LN[-1]); its scale 1000*exp(X beta_LN) is its median. Secondary parameters are point estimates only (no secondary bootstrap was performed). Monetary settings and biological threshold are kept distinct from estimated distribution parameters.
