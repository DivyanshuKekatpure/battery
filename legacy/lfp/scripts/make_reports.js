// Builds the three course deliverables as .docx from the project outputs.
// Tables are read from outputs/tables/*.csv so no reported table value is retyped by hand.
// Usage: NODE_PATH=<dir with docx module> node scripts/make_reports.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType,
  ShadingType, AlignmentType, ImageRun, LevelFormat, BorderStyle, PageBreak,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "outputs");
const REPORTS = path.join(OUT, "reports");
fs.mkdirSync(REPORTS, { recursive: true });

// ------------------------------------------------------------------ helpers
function splitCsvLine(line) {
  // handles double-quoted fields containing commas (pandas quotes them)
  const out = [];
  let cur = "", q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { if (q && line[i + 1] === '"') { cur += '"'; i++; } else q = !q; }
    else if (ch === "," && !q) { out.push(cur); cur = ""; }
    else cur += ch;
  }
  out.push(cur);
  return out;
}
function csv(file) {
  const [head, ...lines] = fs.readFileSync(path.join(OUT, "tables", file), "utf8").trim().split("\n");
  const cols = splitCsvLine(head);
  return lines.map((l) => Object.fromEntries(splitCsvLine(l).map((v, i) => [cols[i], v])));
}
const num = (v, d = 3) => (v === "" || v === undefined ? "" : (Math.abs(Number(v)) < 0.5 * 10 ** -d ? 0 : Number(v)).toFixed(d));

function runs(text) {
  // **bold**, *italic*
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun(text.slice(last, m.index)));
    const t = m[0];
    out.push(t.startsWith("**") ? new TextRun({ text: t.slice(2, -2), bold: true })
                                : new TextRun({ text: t.slice(1, -1), italics: true }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun(text.slice(last)));
  return out;
}
const P = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 120 }, ...opts });
const H1 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_1, spacing: { before: 240, after: 120 } });
const H2 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 } });
const B = (t) => new Paragraph({ children: runs(t), numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 } });
const N = (t) => new Paragraph({ children: runs(t), numbering: { reference: "numbers", level: 0 }, spacing: { after: 60 } });
const Caption = (t) => new Paragraph({ children: runs(t), spacing: { after: 200 },
  run: { size: 18 }, alignment: AlignmentType.LEFT });
const Note = (t) => new Paragraph({ children: [new TextRun({ text: t, italics: true, size: 18, color: "555555" })],
  spacing: { after: 200 } });
const REF = (t) => new Paragraph({ children: runs(t), indent: { left: 720, hanging: 720 }, spacing: { after: 100 } });

const TABLE_W = 9360; // 6.5 in at US Letter with 1 in margins
function table(header, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const w = widths.map((x) => Math.round((x / total) * TABLE_W));
  w[w.length - 1] += TABLE_W - w.reduce((a, b) => a + b, 0);
  const cell = (t, i, isHead) => new TableCell({
    width: { size: w[i], type: WidthType.DXA },
    shading: isHead ? { type: ShadingType.CLEAR, fill: "E8EEF7", color: "auto" } : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: [new Paragraph({ children: [new TextRun({ text: String(t), bold: isHead, size: 18 })] })],
  });
  return new Table({
    width: { size: TABLE_W, type: WidthType.DXA }, columnWidths: w,
    rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true)) }),
           ...rows.map((r) => new TableRow({ children: r.map((c, i) => cell(c, i, false)) }))],
  });
}
function figure(file, caption) {
  const data = fs.readFileSync(path.join(OUT, "figures", file));
  return [new Paragraph({ children: [new ImageRun({ type: "png", data, transformation: { width: 576, height: 358 } })],
                          alignment: AlignmentType.CENTER, spacing: { before: 120 } }),
          Caption(caption)];
}
function doc(title, subtitle, children) {
  return new Document({
    creator: "Battery fast-charging project team",
    title,
    styles: {
      default: {
        document: { run: { font: "Calibri", size: 22 } },
        heading1: { run: { font: "Calibri", size: 30, bold: true, color: "1F3864" } },
        heading2: { run: { font: "Calibri", size: 25, bold: true, color: "2E5597" } },
      },
    },
    numbering: { config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
      { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    ] },
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      children: [
        new Paragraph({ children: [new TextRun({ text: title, bold: true, size: 36, color: "1F3864" })], spacing: { after: 80 } }),
        new Paragraph({ children: [new TextRun({ text: subtitle, size: 22, color: "555555" })], spacing: { after: 240 },
                        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F3864", space: 4 } } }),
        ...children,
      ],
    }],
  });
}
async function save(d, name) {
  const buf = await Packer.toBuffer(d);
  fs.writeFileSync(path.join(REPORTS, name), buf);
  console.log("wrote outputs/reports/" + name);
}

// ------------------------------------------------------------------ shared tables
const anova = csv("p4_2_anova.csv");
const RESP = { minutes_to_80pct: "Minutes to 80% charge", log_cycles_to_80pct: "log(cycles to 80% health)",
  health_at_500: "Health at 500 cycles", health_at_1000: "Health at 1000 cycles" };
function anovaTable() {
  const rows = [];
  for (const r of Object.keys(RESP)) {
    for (const term of ["rate", "method", "ambient", "limit", "rate:method"]) {
      const a = anova.find((x) => x.response === r && x.term === term);
      if (!a) continue;
      const p = Number(a.p);
      rows.push([RESP[r], term, a.df, Number(a.F).toFixed(1), p < 0.001 ? "< 0.001" : p.toFixed(3),
                 Number(a.partial_eta_sq).toFixed(3)]);
    }
  }
  return table(["Response", "Term", "df", "F", "p", "Partial η²"], rows, [3, 1.6, 0.6, 1.3, 1, 1.1]);
}
function regressionTable() {
  const reg = csv("p4_3_regression_log_life.csv");
  const main = reg.filter((r) => !r.term.includes(":"));
  const rows = main.map((r) => [r.term, num(r.estimate, 4), num(r.SE, 4), `[${num(r.ci_lo, 4)}, ${num(r.ci_hi, 4)}]`,
                                Number(r.p) < 0.001 ? "< 0.001" : Number(r.p).toFixed(3)]);
  const inter = reg.filter((r) => r.term.includes(":"));
  const maxAbs = Math.max(...inter.map((r) => Math.abs(Number(r.estimate))));
  rows.push([`${inter.length} two-way interactions`, `all |b| ≤ ${maxAbs.toExponential(1)}`, "0.010–0.015",
             "each CI contains 0", "all = 1.000"]);
  return table(["Term (baseline 1C, 25 °C, 100%, CC-CV)", "Estimate", "SE", "95% CI", "p"], rows, [3.2, 1.3, 1, 2, 1]);
}
function strategyTable() {
  const rel = csv("p4_5_reliability_by_strategy.csv");
  const cmp = csv("p4_4_strategy_comparison.csv");
  const t80 = (k) => cmp.find((c) => c.comparison.startsWith(k) && c.quantity.includes("minutes"));
  const rows = rel.map((r) => {
    const c = r.strategy === "normal_fast" ? null : t80(r.strategy);
    return [{ normal_fast: "Normal fast (3C, CC-CV, 100%)", limit_80pct: "80% limit (3C, CC-CV)", multistage: "Multistage (3C, 100%)" }[r.strategy],
      `${num(r.beta, 2)} [${num(r.beta_ci_lo, 2)}, ${num(r.beta_ci_hi, 2)}]`,
      `${num(r.eta, 0)} [${num(r.eta_ci_lo, 0)}, ${num(r.eta_ci_hi, 0)}]`,
      num(r.MTTF, 0), num(r.R500, 3), num(r.R1000, 3),
      c ? `${num(c.difference, 2)} [${num(c.ci_lo, 2)}, ${num(c.ci_hi, 2)}]` : "reference"];
  });
  return table(["Strategy (25 °C)", "Weibull β [95% CI]", "Weibull η, cycles [95% CI]", "MTTF", "R(500)", "R(1000)",
                "Δ median min to 80% vs normal [95% CI]"], rows, [2.4, 1.6, 1.8, 0.9, 0.9, 0.9, 2.2]);
}
function costInputTable() {
  return table(["Input", "Value", "Source (retrieved 28 Oct 2026)"], [
    ["Out-of-warranty battery replacement, iPhone 16", "$99 (sensitivity: $119, Pro models)", "Burkhardt (2024), citing Apple's iPhone Repair & Service page"],
    ["Service fee per replacement", "$0 (in-store)", "Apple Support: a shipping fee applies only when the phone is mailed in"],
    ["Charger (same for every strategy)", "$19", "Apple Store, 20W USB-C Power Adapter (MWVV3AM/A)"],
    ["Device (phone-replacement case)", "$799", "Apple Store, iPhone 16 128GB"],
    ["Equivalent full cycles per year", "255.5 (0.7 per day)", "Aussems (2025); review-site estimate, not peer reviewed"],
    ["Ownership period", "3 years", "Apple (2024), iPhone 16 Product Environmental Report, p. 9"],
  ], [3, 2.2, 4.2]);
}
function financialTable() {
  const s = csv("p5_cost_by_strategy.csv");
  const d = csv("p5_ownership_cost.csv");
  const lab = { normal_fast: "Fast 3C (CC-CV, 100%)", limit_80pct: "80% limit (3C)", multistage: "Multistage (3C)", slow_2C: "Slower 2C", slow_1C: "Slower 1C" };
  const saving = (k, c) => {
    const r = d.find((x) => x.after === k && x.case === c);
    return r ? `$${num(-r.difference, 2)} [${num(-r.ci_hi, 2)}, ${num(-r.ci_lo, 2)}]` : "reference";
  };
  return table(["Strategy", "Owners needing a replacement in 3 yr", "3-yr cost per owner, battery replaced [95% CI]",
                "Saving vs fast, battery replaced [95% CI]", "Saving vs fast, phone replaced [95% CI]"],
    s.map((r) => [lab[r.strategy], `${(100 * r.share_with_replacement).toFixed(1)}%`,
                  `$${num(r.cost_battery_case, 2)} [${num(r.cost_battery_ci_lo, 2)}, ${num(r.cost_battery_ci_hi, 2)}]`,
                  saving(r.strategy, "battery replacement"), saving(r.strategy, "phone replacement")]),
    [1.8, 1.5, 2.3, 2.1, 2.1]);
}

// ------------------------------------------------------------------ references
const REFS = {
  apple_batt: "Apple Inc. (n.d.-a). *Battery service and recycling*. Retrieved October 28, 2026, from https://www.apple.com/batteries/service-and-recycling/",
  apple_support: "Apple Inc. (n.d.-b). *iPhone battery replacement*. Apple Support. Retrieved October 28, 2026, from https://support.apple.com/iphone/repair/battery-replacement",
  apple_store: "Apple Inc. (n.d.-c). *Buy iPhone 16*. Apple Store. Retrieved October 28, 2026, from https://www.apple.com/shop/buy-iphone/iphone-16",
  apple_adapter: "Apple Inc. (n.d.-d). *20W USB-C Power Adapter* [Product listing, MWVV3AM/A]. Apple Store. Retrieved October 28, 2026, from https://www.apple.com/us/search/20W-USB-C-Power-Adapter",
  apple_per: "Apple Inc. (2024). *Product environmental report: iPhone 16 and iPhone 16 Plus*. https://www.apple.com/environment/pdf/products/iphone/iPhone_16_and_iPhone_16_Plus_PER_Sept2024.pdf",
  attia: "Attia, P. M., Grover, A., Jin, N., Severson, K. A., Markov, T. M., Liao, Y.-H., Chen, M. H., Cheong, B., Perkins, N., Yang, Z., Herring, P. K., Aykol, M., Harris, S. J., Braatz, R. D., Ermon, S., & Chueh, W. C. (2020). Closed-loop optimization of fast-charging protocols for batteries with machine learning. *Nature, 578*(7795), 397–402. https://doi.org/10.1038/s41586-020-1994-5",
  aussems: "Aussems, M. (2025, July 4). *iPhone battery twice as bad as Samsung: Which manufacturer performs best?* ITdaily. https://itdaily.com/blogs/workplace/iphone-battery-twice-as-bad-as-samsung-which-manufacturer-performs-best/",
  burkhardt: "Burkhardt, M. (2024, September 15). *iPhone 16 Pro battery replacement* [News article]. 9to5Mac. https://9to5mac.com/2024/09/15/iphone-16-pro-battery-replacement/",
  diao: "Diao, W., Saxena, S., & Pecht, M. (2019). Accelerated cycle life testing and capacity degradation modeling of LiCoO2-graphite cells. *Journal of Power Sources, 435*, 226830. https://doi.org/10.1016/j.jpowsour.2019.226830",
  fraser: "Fraser, T. (n.d.). *ZZ_financial_analysis* [Computer code]. sysen repository, GitHub. https://github.com/timothyfraser/sysen",
  huang: "Huang, S., Wu, X., Cavalheiro, G. M., Du, X., Liu, B., Du, Z., & Zhang, G. (2019). In situ measurement of lithium-ion cell internal temperatures during extreme fast charging. *Journal of The Electrochemical Society, 166*(14).",
  keil: "Keil, P., & Jossen, A. (2016). Charging protocols for lithium-ion batteries and their impact on cycle life—An experimental study with different 18650 high-power cells. *Journal of Energy Storage, 6*, 125–141. https://doi.org/10.1016/j.est.2016.02.005",
  saxena: "Saxena, S., Hendricks, C., & Pecht, M. (2016). Cycle life testing and modeling of graphite/LiCoO2 cells under different state of charge ranges. *Journal of Power Sources, 327*, 394–400.",
  severson: "Severson, K. A., Attia, P. M., Jin, N., Perkins, N., Jiang, B., Yang, Z., Chen, M. H., Aykol, M., Herring, P. K., Fraggedakis, D., Bazant, M. Z., Harris, S. J., Chueh, W. C., & Braatz, R. D. (2019). Data-driven prediction of battery cycle life before capacity degradation. *Nature Energy, 4*(5), 383–391. https://doi.org/10.1038/s41560-019-0356-8",
  tahir: "Tahir, M. U., Sangwongwanich, A., Stroe, D.-I., & Blaabjerg, F. (2024). Multi-objective optimization for multi-stage constant current charging for Li-ion batteries. *Journal of Energy Storage, 86*(Part A), 111313. https://doi.org/10.1016/j.est.2024.111313",
};
const refList = (keys) => keys.sort().map((k) => REF(REFS[k]));

// ------------------------------------------------------------------ shared text
const MEASURES = [
  P("The unit of observation is one simulated smartphone battery, and we record five measures for each. **Cycles to 80% health** counts equivalent full charge cycles until capacity falls to 80% of nominal, the end-of-life definition used by Severson et al. (2019) and by Apple's ratings (Apple, n.d.-a). **Health at 500 and 1,000 cycles** is capacity as a fraction of nominal at Apple's two rated cycle counts; a battery already past end of life is flagged rather than given a number. **Minutes to 80% charge** is the convenience measure users notice. **Peak battery temperature** is ambient temperature plus the charge-phase rise. Together these put the trade-off in one place: speed and heat against lifespan. Life is also summarised as Weibull reliability (β, η, MTTF and R(t))."),
];
const ASSUMPTIONS = [
  P("Every model number comes from a published source, a manufacturer rating, or a fit to a published dataset; anything we could not verify was left out. That rule forced four simplifications. First, life is modelled on LFP cells (Severson et al., 2019), not the LCO cells in phones, because the LCO dataset (Diao et al., 2019) cannot yet be mapped to its test conditions. Second, the charge-rate law fitted at 3.2–5.3C is applied at 1–3C. Third, ambient temperature, the 80% limit and multistage charging get no life effect, because no verified source quantifies one. Fourth, capacity fades along the median Severson curve, so batteries differ only in when they reach end of life."),
];
const MODEL = [
  P("We built a full-factorial Monte Carlo simulation in Python (numpy, pandas and scipy only) with four factors: charge rate (1C, 2C, 3C), ambient temperature (10, 25, 40 °C), charge limit (80%, 100%) and charging method (standard constant-current/constant-voltage, CC-CV, versus multistage constant current). That gives 36 scenarios with 1,000 simulated batteries each, 36,000 in total. All runs use one random seed (20261028), and battery *i* uses the same random draws in every scenario (common random numbers), so differences between scenarios are not sampling noise."),
  P("**Life submodel.** Cycles to 80% health follow a Weibull distribution whose scale depends on charge rate: η(r) = 820.2 × exp(−0.531 × (r − 4.74)), with shape β = 2.595. We estimated β, η and the rate slope together by maximum likelihood on 124 cells from Severson et al. (2019), all of which reached end of life (no censoring). The slope's 95% CI is [−0.723, −0.339]. We re-ran the whole simulation with the slope at both CI bounds to carry parameter uncertainty into the results."),
  P("**Health submodel.** Health at *n* cycles is read off the median normalised fade curve from the same 124 cells: health starts at 0.972 of nominal, is 0.958 at half of life, and 0.800 at end of life."),
  P("**Charge-time submodel.** Time to 80% is t₈₀ = k × 0.8 × 60 / r minutes, where k ~ Normal(1.061, 0.088) was fitted to 21 Severson cells charged at a single rate to 80%. Multistage charging multiplies t₈₀ by 0.898 at 25 °C or 0.926 at 35 °C, the measured ratios in Tahir et al. (2024, Table 11)."),
  P("**Temperature submodel.** Peak temperature is ambient plus a charge-phase rise fitted to raw Severson temperature traces. That fit is weak (R² = 0.07) and predicts impossible negative rises below about 2C, so temperature is reported only at 3C."),
  P("**Analysis.** We used descriptive statistics, type III factorial ANOVA with partial η², and an ordinary-least-squares regression of log life on all factors with two-way interactions. Strategies were compared with paired bootstrap 95% confidence intervals (2,000 resamples). We fitted Weibull reliability per strategy, and applied an individuals control chart with capability indices to health at 500 cycles. This chain answers the research question directly: the ANOVA and regression isolate how much charge rate moves battery life, the bootstrap puts uncertainty on the difference between practical charging strategies, and the reliability and SPC steps translate it into the language of a warranty or a service plan."),
];
const RESULTS = [
  P("**Charge rate is the dominant driver of both lifespan and charging speed.** Median cycles to 80% health fall from 5,237 at 1C to 3,080 at 2C and 1,811 at 3C. In the regression of log life, the 3C coefficient is −1.062 (95% CI [−1.088, −1.035], p < 0.001) relative to 1C, which means about 65% shorter life; the 2C coefficient is −0.531 ([−0.558, −0.504], p < 0.001). The model explains R² = 0.459 of the variance in log life; the rest is battery-to-battery spread. Charge rate has a partial η² of 0.459 for log life, 0.102 for health at 500 cycles and 0.212 for health at 1,000 cycles (all p < 0.001). By 1,000 cycles, 0.9% of batteries charged at 1C are past end of life, against 3.1% at 2C and 13.2% at 3C. Mean health at 500 cycles is 0.976, 0.973 and 0.967 respectively."),
  P("**Fast charging buys time.** Mean minutes to 80% are 51.1 (1C), 25.6 (2C) and 17.0 (3C) with CC-CV. Rate explains almost all of the variance in charge time (partial η² = 0.963), and charging method explains a further 0.222 (both p < 0.001). Multistage charging saves 1.75 minutes per charge at 3C (paired bootstrap 95% CI [1.74, 1.76]). The ambient-temperature term is small (partial η² = 0.006) and exists only because the 40 °C scenarios borrow Tahir's 35 °C ratio."),
  P("**Charge limit, ambient temperature and method show zero effect on life — by construction, not as a finding.** Their F statistics for life are exactly 0 because no verified source quantified their life effects. Reliability at 3C is therefore identical for the three practical strategies: β = 2.63 [2.51, 2.76], η = 2,088 [2,037, 2,140] cycles, MTTF = 1,855 cycles, R(500) = 0.977 and R(1,000) = 0.866."),
  P("**Results are sensitive to the rate slope.** With the slope at its 95% CI bounds, median life at 1C ranges from 2,552 to 10,750 cycles and at 3C from 1,296 to 2,531. **The baseline fails validation:** at 1C and 25 °C the model predicts a median of 5,187 cycles, five to ten times Apple's ratings of 500 (iPhone 14 and earlier) and 1,000 cycles (iPhone 15 models) (Apple, n.d.-a). We did not tune the model to force a match. The most likely reason is chemistry: LFP cells last much longer than phone LCO cells. Absolute lifetimes are therefore not credible; the direction and relative size of the rate effect are the defensible results."),
  P("**Control chart and capability.** The individuals chart on health at 500 cycles for the multistage strategy has CL = 0.967, UCL = 0.996 and LCL = 0.938. It flags 33 points and a 16-point run, but the batteries are independent by design. The signals come from health being bounded and skewed (Shapiro–Wilk p < 0.001), not from instability. Against a lower specification of 0.80 at 500 cycles, Cpk = 5.84 and Ppk = 3.49, yet 1.8% of batteries are already past end of life at 500 cycles and cannot be charted. Capability indices overstate quality here, and the observed nonconforming fraction (1.8%) is the honest metric."),
];

// ------------------------------------------------------------------ 1. Preliminary methods and results
async function prelim() {
  const children = [
    H1("Measures"), ...MEASURES,
    H1("Assumptions"), ...ASSUMPTIONS,
    H1("Model / approach"), ...MODEL,
    H1("Results"), ...RESULTS,
    H2("Tables and figures"),
    P("**Table 1.** Factorial ANOVA (type III, effect coding, all interactions; n = 36,000 batteries, or fewer for health where batteries are past end of life). Terms not shown have partial η² < 0.002; the full table is in outputs/tables/p4_2_anova.csv."),
    anovaTable(), Note("A term with F = 0 has no verified effect in the model and was therefore not simulated; it is not evidence of no effect."),
    P("**Table 2.** Regression of log(cycles to 80% health) on all factors with two-way interactions (OLS, n = 36,000; R² = 0.459, adjusted R² = 0.459, residual SD = 0.471)."),
    regressionTable(), Note("Residuals are left-skewed (skew −0.97, excess kurtosis 1.66), as expected when life is Weibull-distributed; coefficient CIs use the normal-theory standard errors."),
    P("**Table 3.** Practical charging strategies at 3C and 25 °C: Weibull reliability of simulated life, and the change in median minutes to 80% from a paired bootstrap (2,000 resamples)."),
    strategyTable(),
    ...figure("p4_1_life_by_rate.png", "**Figure 1.** Cycles to 80% health by charge rate (boxes: interquartile range; whiskers: 5th–95th percentile). Dashed lines mark Apple's 500- and 1,000-cycle ratings; the simulated lives sit far above them (validation gap)."),
    ...figure("p4_sensitivity_median_life.png", "**Figure 2.** Median life by charge rate, with the rate slope at its point estimate (dot) and at its 95% CI bounds (bar)."),
    ...figure("p4_2_charge_time_interaction.png", "**Figure 3.** Mean minutes to 80% charge by rate and method."),
    ...figure("p4_6_individuals_chart_health500.png", "**Figure 4.** Individuals chart on health at 500 cycles, multistage strategy (3C, 25 °C). Red points fall beyond the 3σ limits; LSL = 0.80."),
    H1("References"), ...refList(["severson", "diao", "tahir", "apple_batt"]),
  ];
  await save(doc("Preliminary Methods and Results", "Does fast charging make smartphone batteries degrade faster? — Six Sigma simulation study", children), "Preliminary_Methods_and_Results.docx");
}

// ------------------------------------------------------------------ 2. Financial impacts
const FIN_TEXT = [
  P("**Recommendation: default phone charging to a slower rate (2C) unless the user asks for a fast charge.** Over a three-year ownership period, this lowers expected battery-replacement spending by **$4.55 per owner (95% CI $3.37–$5.84)**, from $25.14 to $20.58. Slowing to 1C saves **$5.84 ($4.46–$7.33)**. For a fleet of 10,000 company phones, that is roughly $45,500 ($33,700–$58,400) over three years at 2C. The cost is time: reaching 80% charge takes 25.6 minutes at 2C and 51.1 at 1C, instead of 17.0 at 3C."),
  P("**How the costs were estimated.** We combined the simulated battery lifetimes with published prices, following the bootstrap approach in Fraser (n.d.):"),
  B("Each simulated owner uses the phone for 3 years, Apple's first-owner assumption (Apple, 2024, p. 9), at 0.7 equivalent full cycles per day (Aussems, 2025): 766.5 cycles in total."),
  B("Whenever a battery reaches 80% health, it is replaced and the new battery draws a fresh lifetime from the same strategy (a renewal process)."),
  B("Each replacement costs $99, Apple's out-of-warranty price for an iPhone 16 battery (Burkhardt, 2024), with no service fee for an in-store repair (Apple, n.d.-b). Every strategy uses the same $19 charger (Apple, n.d.-d), so charger cost cancels out."),
  P("**Uncertainty.** No closed-form standard error exists for this cost, so we bootstrapped it. We resampled the 1,000 simulated owners 2,000 times, with the same owners under both strategies, and took the 2.5th and 97.5th percentiles of the cost difference. Using the $119 Pro-model battery price instead raises the 2C saving to $5.47 ($4.05–$7.02)."),
  P("**When owners replace the whole phone at end of battery life** ($799; Apple, n.d.-c), the stakes are larger. Slower 2C charging saves $36.75 per owner ($27.17–$47.14), and 1C saves $47.14 ($35.96–$59.13)."),
  P("**What the money depends on.** Savings come from fewer owners hitting end of life within three years. At 3C, 6.2% of owners need a replacement (95% CI 4.8–7.6%); at 2C, 1.6% (0.9–2.4%); at 1C, 0.3% (0–0.7%). Most of that spending falls in year three (Figure 2)."),
  P("**What we cannot claim yet.** The 80% charge limit and multistage charging show $0 savings only because no verified source gives their effect on battery life. These are not evidence that they don't help."),
  P("**These figures are conservative for real phones.** Our lifetime model, fitted to LFP cells, predicts batteries lasting five to ten times longer than Apple's 500–1,000-cycle ratings. If real phone batteries fade as fast as Apple's ratings suggest, far more owners would hit end of life within three years, and the savings from slower charging would be larger. Two inputs also deserve caution. The usage rate comes from a review site's estimate rather than a peer-reviewed study, and the battery price comes from 2024 news coverage of Apple's price list. We would ask a CTO to fund obtaining the LCO test conditions (Diao et al., 2019) and a peer-reviewed usage estimate before scaling the recommendation."),
];
async function financial() {
  const children = [
    H1("Financial Impacts"), ...FIN_TEXT,
    P("**Table 1.** Cost inputs and sources."), costInputTable(),
    P("**Table 2.** Three-year cost per owner by charging strategy (1,000 simulated owners; bootstrap 95% CIs; 2,000 resamples)."),
    financialTable(), Note("80% limit and multistage: life effects not modelled, so their costs equal fast charging by construction."),
    ...figure("p5_2_savings_vs_fast.png", "**Figure 1.** Savings per owner over three years from slower charging, compared with fast 3C charging, if the owner replaces the battery (blue) or the whole phone (red). Bars are bootstrap 95% CIs."),
    ...figure("p5_4_cumulative_spend_by_year.png", "**Figure 2.** Cumulative battery-replacement spend per owner by year of ownership. Most of the difference appears in year three."),
    ...figure("p5_1_cost_per_owner.png", "**Figure 3.** Expected three-year cost per owner (charger plus battery replacements) by strategy."),
    ...figure("p5_3_share_needing_replacement.png", "**Figure 4.** Share of owners needing at least one battery replacement within three years."),
    H1("References"), ...refList(["apple_per", "apple_support", "apple_store", "apple_adapter", "aussems", "burkhardt", "diao", "fraser", "severson"]),
  ];
  await save(doc("Financial Impacts", "Discussion section — Six Sigma report: fast charging and smartphone battery degradation", children), "Financial_Impacts.docx");
}

// ------------------------------------------------------------------ 3. Rough draft
async function rough() {
  const placeholder = (t) => Note(`[${t} — insert the template completed in the earlier assignment; not in the word count.]`);
  const children = [
    H1("1. Introduction"),
    placeholder("Project Charter"),
    H2("Background and project motivation"),
    P("Smartphone owners now expect a phone to charge from empty to most of its capacity in well under half an hour, and manufacturers compete on charging wattage. Yet the battery is also the component that wears out first: Apple rates iPhone batteries to retain 80% of their capacity after 500 complete cycles for iPhone 14 and earlier and 1,000 cycles for iPhone 15 models (Apple, n.d.-a), and a battery below 80% is the most common reason owners pay for a replacement or buy a new phone. Laboratory studies show that high charging currents accelerate lithium-ion degradation (Keil & Jossen, 2016; Severson et al., 2019), but phone users and IT managers have no quantified guide to how much lifespan fast charging costs and what that is worth in dollars. That gap motivates this project."),
    H2("Project objectives and expected contributions"),
    P("Our research question is: does fast charging make smartphone batteries degrade faster, and by how much? The objectives are to (1) build a simulation model in which every parameter is traceable to a published dataset or paper; (2) quantify how charge rate, ambient temperature, charge limit and charging method affect cycles to 80% health, health at Apple's rated cycle counts, charging time and battery temperature; (3) compare practical strategies a user or fleet manager could adopt — normal fast charging, an 80% charge limit, multistage charging and slower charging — with confidence intervals; and (4) translate the results into ownership cost. The expected contribution is a transparent, reproducible decision aid that states clearly what is supported by evidence and what still is not."),
    H1("2. Literature review"),
    placeholder("SIPOC diagram"), placeholder("Process map"), placeholder("Voice of the Customer tree"),
    H2("Background literature"),
    P("Severson et al. (2019) cycled 124 commercial lithium iron phosphate (LFP) cells under 72 fast-charging protocols and found cycle lives from about 150 to 2,300 cycles. They released the full dataset, which we use to fit our life model. Attia et al. (2020) extended that work with a further 45-cell batch and machine-learning-guided optimisation of four-step charging protocols."),
    P("For the lithium cobalt oxide (LCO) chemistry used in phones, Diao et al. (2019) ran an accelerated full-factorial life test on 3.36 Ah pouch cells. It varied ambient temperature, discharge rate and charge cut-off, with eight replicate cells per condition, and the capacity data is public. Saxena et al. (2016) showed that the mean state of charge and the size of the charge swing both change the fade rate of LCO cells, which motivates our charge-limit factor."),
    P("Keil and Jossen (2016) tested charging protocols on three 18650 cell types. Charging current harmed cycle life more than discharge current, and the size of the effect differed widely between cell types. That warns against carrying one cell's numbers to another."),
    P("On heat, Huang et al. (2019) embedded thermocouples in a 2 Ah pouch cell. The core rose 22.5 °C within five minutes at 7C under forced air but less than 1.5 °C at 1C, and natural convection gave higher temperature rises than forced convection."),
    P("Multistage constant-current charging is reported to shorten charge time without extra heating. Tahir et al. (2024) measured 10.2% faster charging than CC-CV at 25 °C with a comparable maximum temperature rise, and Liu and Luo (2010) reported longer cycle life for an optimised multistage pattern. Together, this literature says fast charging should shorten life, but in amounts that depend on chemistry, temperature and protocol."),
    H1("3. Methodology"),
    placeholder("Research Design"),
    H2("Data"),
    P("We used five data sources. The Severson et al. (2019) and Attia et al. (2020) batch files (four MATLAB files, 10.9 GB) give per-cycle capacity, charge time, temperature and internal resistance for 185 LFP cells. We applied the authors' published curation to recover their 124-cell set and fitted life, fade, charge-time and temperature relationships to it. The Diao et al. (2019) file holds LCO capacity curves for 24 test conditions with 8 cells each, but which condition is which temperature is described only in the paper, which we have not yet obtained. The CALCE partial-cycling cells behind Saxena et al. (2016) are downloaded but stored in a MATLAB format our toolset cannot read. Tahir et al. (2024) supplies measured charge times and temperature rises for CC-CV versus multistage charging. Apple's published ratings and prices anchor validation and costs."),
    H2("Measures"), ...MEASURES,
    H2("Model / approach"),
    P("We built a full-factorial Monte Carlo simulation: charge rate (1C, 2C, 3C) × ambient temperature (10, 25, 40 °C) × charge limit (80%, 100%) × method (CC-CV, multistage). That is 36 scenarios with 1,000 batteries each, a fixed seed, and common random numbers, so each battery uses the same random draws in every scenario. Each battery's life is drawn from a Weibull distribution with shape β = 2.595 and a scale that falls with charge rate, η(r) = 820.2 × exp(−0.531 × (r − 4.74)). These were fitted together by maximum likelihood to the 124 Severson cells. Health at 500 and 1,000 cycles follows the median fade curve of those cells. Time to 80% charge is fitted to Severson charge times, with Tahir et al.'s measured multistage-to-CC-CV ratios. Temperature rise is fitted to raw Severson traces and reported only at 3C, where the fit is valid. We analysed the output with factorial ANOVA, a regression of log life with two-way interactions, paired bootstrap comparisons of strategies, Weibull reliability, and an individuals control chart with capability indices. Every parameter, its source and every extrapolation is listed in outputs/parameters.csv."),
    H2("Preliminary results"),
    ...RESULTS,
    regressionTable(),
    Caption("**Table 1.** Regression of log(cycles to 80% health) on all factors with two-way interactions (n = 36,000; R² = 0.459)."),
    ...figure("p4_1_life_by_rate.png", "**Figure 1.** Simulated cycles to 80% health by charge rate, against Apple's 500- and 1,000-cycle ratings."),
    H1("4. Discussion"),
    P("**What the results support.** Within the model, faster charging clearly shortens battery life: moving from 1C to 3C cuts median life by about 65% while cutting time to 80% charge from 51 to 17 minutes. Because the life model is exponential in charge rate, each extra 1C costs the same share of life, about 41%. The largest absolute changes, in both directions, are therefore between 1C and 2C. That step saves 25.6 minutes per charge and costs about 2,160 cycles of median life. Going from 2C to 3C saves 8.6 more minutes and costs about 1,270 more cycles. Multistage charging is a free improvement in charging speed (1.75 minutes faster at 3C) with no measured cost in heat in Tahir et al. (2024); whether it also protects lifespan, as Liu and Luo (2010) report, we cannot yet quantify."),
    P("**What the results do not support yet.** The model's lifetimes are five to ten times longer than Apple's ratings, so absolute numbers do not describe real phones. Three of the four factors (ambient temperature, the 80% limit and charging method) have no verified life effect in the model, so their zero effects are gaps in evidence, not findings. These are exactly the levers a phone owner controls, so closing them is the priority."),
    P("**Status, problems and strategies.** Completed: data extraction and curation; a 29-parameter verified parameter table; the model specification; the 36,000-battery simulation; the statistical analysis; and the financial module. Remaining problems and our plan:"),
    B("**LCO baseline.** Obtain the Diao et al. (2019) paper through Cornell Library, map its 24 conditions to temperatures, and replace the LFP baseline. This should bring lifetimes toward Apple's ratings and add a real temperature effect."),
    B("**Charge window and multistage life effects.** Obtain Saxena et al. (2016) and Liu and Luo (2010), and convert the CALCE files with a short MATLAB export."),
    B("**Temperature at 1–2C.** Obtain Huang et al. (2019) to replace the weak temperature fit."),
    B("**Statistical method.** Replace the individuals chart, which raises false alarms on bounded, skewed health data, with a chart on a transformed or attribute measure (share past end of life)."),
    P("**Timeline.** Literature PDFs and the LCO re-fit in week 1; re-run of Phases 3–5 in week 2; final report in week 3."),
    H2("Summary of findings"),
    P("Faster charging shortens simulated battery life: median cycles to 80% health fall from 5,237 at 1C to 1,811 at 3C, a coefficient of −1.062 on log life (95% CI [−1.088, −1.035]). Charging three times faster saves 34 minutes per charge to 80%, and multistage charging adds 1.75 minutes of saving at 3C. By 1,000 cycles, 13.2% of 3C batteries are past end of life against 0.9% at 1C. The effects of temperature, the 80% limit and multistage charging on lifespan remain unquantified, and absolute lifetimes overstate real phones because the model is fitted to LFP rather than LCO cells."),
    H2("Financial impacts"),
    P("**Proposed change:** default phones to 2C charging unless the user asks for a fast charge. Over three years this saves an expected $4.55 per owner in battery replacements (95% CI $3.37–$5.84), cutting the three-year cost from $25.14 to $20.58. Slowing to 1C saves $5.84 ($4.46–$7.33). Across a 10,000-phone corporate fleet, the 2C saving is about $45,500 ($33,700–$58,400). The inputs are: $99 per battery replacement (Burkhardt, 2024), no service fee in store (Apple, n.d.-b), three years of use (Apple, 2024) and 0.7 equivalent full cycles per day (Aussems, 2025). When owners replace the whole $799 phone at end of battery life (Apple, n.d.-c), the savings rise to $36.75 (2C) and $47.14 (1C) per owner. We built the intervals by bootstrapping 1,000 simulated owners 2,000 times, with the same owners under both strategies. The savings are small because the LFP-based model predicts long lives: only 6.2% of fast-charging owners need a replacement within three years. With phone-realistic lifetimes they would be larger, so we treat them as a lower bound. Charging time carries no cost here, and it is the main counterweight a CTO should weigh: 2C takes 25.6 minutes to reach 80% versus 17.0 at 3C."),
    ...figure("p5_2_savings_vs_fast.png", "**Figure 2.** Three-year savings per owner from slower charging versus fast 3C charging (bootstrap 95% CIs)."),
    H1("References"),
    ...refList(["apple_batt", "apple_per", "apple_store", "attia", "aussems", "burkhardt", "diao", "huang", "keil", "saxena", "severson", "tahir"]),
    REF("Liu, Y.-H., & Luo, Y.-F. (2010). Search for an optimal rapid-charging pattern for Li-ion batteries using the Taguchi approach. *IEEE Transactions on Industrial Electronics, 57*(12), 3963–3971."),
  ];
  await save(doc("Six Sigma Report — Rough Draft", "Does fast charging make smartphone batteries degrade faster?", children), "Rough_Draft.docx");
}

(async () => { await prelim(); await financial(); await rough(); })();
