# Prespecified KIT methods

Research question: How do charging rate, a 90% charging cap, and operating temperature affect capacity degradation and equivalent-full-cycle life to 80% of initial capacity in NMC/graphite-SiO lithium-ion cells?

The independent unit is the physical cell. Primary 72-cell design and assumptions K001–K010 are defined in decision_log.md before any fit. Descriptive plots show measured reference capacities; lines only connect observations and are not imputed data. Cell-level first observed threshold crossings remain intervals. Uncrossed cells remain right-censored. Operating bath temperature is not phone ambient air.

MODEL ESTIMATES: AFT log scale = intercept + categorical rate + cap + temperature + all two-way interactions. Weibull shape is common. A lognormal fit uses the same design. Use stable interval probabilities and deterministic multiple starts, with convergence logs. Confidence intervals use 2000 stratified whole-cell bootstrap fits. Require >=95% successful fits. Primary three interaction tests are approximate likelihood-ratio tests, adjusted using Holm. Report modeled survival and life ratios separately from measured cell histories. Three-fold balanced held-out interval log likelihood measures predictive adequacy without inventing true failure dates.

Sensitivity models: rated capacity (3Ah); operating-only EFC; include flagged cold data; include final manual CU; include both; and pessimistic shutdown events for uncrossed fault-stopped cells. Final manual CU is identified by the README May29–Jun1 window. Changes in direction are disclosed. Equipment/safety shutdowns may violate independent censoring; sensitivity is not proof of its validity.

FINANCIAL MODEL ESTIMATES/ASSUMPTIONS: use 25C predicted lifetime distributions in a renewal process. All strategies supply 0.7*365*3=766.5 EFC (not number of partial sessions). Fresh iid replacements; prices fixed per scenario; smartphone lifetime transfer assumed. Numeric renewal expectations and bootstrap intervals are conditional, not observed savings. Price and usage/transfer sensitivity is distinct from sampling CI. Existing charger and zero implementation cost assumed; break-even implementation cost is expected replacement savings. No separate calendar model, no charging-time valuation, no battery-to-phone validation.

Validation: empirical extraction checks, explicit synthetic model-recovery tests, numeric renewal versus labeled simulation, report word counts and numeric provenance, repeatable run. No source or model is selected for favorable savings.
