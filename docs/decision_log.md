# Decision log

Repo copy of the project decision log (the live version is the Claude Doc
<https://claude.ai/artifact/HKgDjtbqx6x4nZizR28zvX>). It is updated and pushed after every phase.

## Going back to a decision point

```bash
git fetch --tags
git tag -l 'decision-*' 'phase*'
git switch -c revisit-D009 decision-D008   # new branch at that point; nothing later is lost
```

`data/`, `papers/`, `outputs/*.h5` and `outputs/sim_results_sensitivity.csv` are not in git, so they stay as they are on disk.

## Decisions (newest first, all 2026-10-28)

| ID | Phase | Decision | Options considered | Return point |
|---|---|---|---|---|
| D014 | Process | Update the decision log (this file and the Claude Doc) and push to GitHub after every phase. | — | `phase5-prep` |
| D013 | 4 | Phase 4 results approved; D011 approved by "go ahead"; start Phase 5. | Approve / revise | `phase4-analysis` |
| D012 | Repo | Push Phases 1–4 and decision tags to GitHub. | — | `phase4-analysis` |
| D011 | 3 | Common random numbers across scenarios; parameters at point estimates; parameter uncertainty via a sensitivity run with the rate slope b at its 95% CI bounds (departs from the spec's per-scenario draws). | Per-scenario draws / common random numbers + sensitivity | `decision-D011` |
| D010 | 2 | Proceed with Phases 3–4 although the baseline fails validation (median 5,187 cycles at 1C vs Apple 500/1000); read results as relative effects only. | Proceed / wait for Diao LCO baseline | `decision-D008` |
| D009 | 2 | Run all 36 scenarios; ambient, limit and method have no life effect ("not modelled"); peak temperature only at 3C; approve P26–P29. | Wait for PDFs / assume no effect | `decision-D008` |
| D008 | 1 | Phase 1 parameter table approved. | Approve / revise | `decision-D008` |
| D007 | 0 | Download free CALCE PL zips and Tahir 2024; add Severson 2019 (authors' copy) and the Apple page; paywalled PDFs left to the user. | — | none |
| D006 | 0 | `data/DOE_Cap_v4.mat` confirmed as the Diao et al. (2019) dataset. | — | none |
| D005 | 0 | Phase 5 adapts the bootstrap structure of `timothyfraser/sysen` `ZZ_financial_analysis.py`. | — | none |
| D004 | Extraction | Add the authors' curation columns, dip-filtered `cycle_life_check`, README; push. | — | `decision-D004` |
| D003 | Repo | Invite DanielDistor, jonathanjma, dmb488-ops (write). | — | none |
| D002 | Repo | Make the repo public. | Private / public | none |
| D001 | Extraction | Download the Severson/Attia batch files and extract the per-cell summary. | — | `decision-D001` |

## Open items

- [ ] `data/cost_inputs.csv` with a value and citation for every row of `outputs/cost_inputs_TEMPLATE.csv` (low/high optional, used for sensitivity)
- [ ] Choose the "after" strategy for Phase 5 (80% limit, multistage, or a slower charge rate)
- [ ] Add Diao 2019, Saxena 2016, Huang 2019, Keil & Jossen 2016, Liu & Luo 2010 PDFs
- [ ] Choose how to read the CALCE PL data: MATLAB export, custom parser, or Saxena's printed numbers
