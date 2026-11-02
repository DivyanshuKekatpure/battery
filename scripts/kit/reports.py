"""Generate editable Markdown and DOCX from the same structured, sourced results."""
import json,re,math
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .common import OUT,save_json
from .figures import LABEL
from .parameters import summarize


def words(text):return len(re.findall(r"\S+",text))
def money(x):return f'${x:,.2f}'
def ci(row,field='median_EFC',digits=0):return f"{row[field]:,.{digits}f} [{row['ci_lo']:,.{digits}f}, {row['ci_hi']:,.{digits}f}]"
def text(s):return '\n\n'.join(' '.join(p.split()) for p in s.split('\n\n'))

KITREF='Luh, M., & Blank, T. (2024). Comprehensive battery aging dataset: capacity and impedance fade measurements of a lithium-ion NMC/C-SiO cell. Scientific Data, 11, 1004. https://doi.org/10.1038/s41597-024-03831-x. Version 2 result data: https://doi.org/10.35097/1969; supplied README, data dictionary and cell overview. CC BY 4.0; analysis adapted by this project.'
REFS=[KITREF,
'Burkhardt, M. (2024, September 15). iPhone 16 Pro battery replacements will cost even more than last year. 9to5Mac. https://9to5mac.com/2024/09/15/iphone-16-pro-battery-replacement/ (accessed November 1, 2026; dated price scenario).',
'Apple Inc. (2024). iPhone 16 and iPhone 16 Plus Product Environmental Report, p. 9. https://www.apple.com/environment/pdf/products/iphone/iPhone_16_and_iPhone_16_Plus_PER_Sept2024.pdf (accessed November 1, 2026).',
'Aussems, M. (2025, July 4). iPhone battery twice as bad as Samsung: which manufacturer performs best? ITdaily. https://itdaily.com/blogs/workplace/iphone-battery-twice-as-bad-as-samsung-which-manufacturer-performs-best/ (accessed November 1, 2026; weak usage source).',
'Apple Inc. (n.d.). Apple service and repair for iPhone battery. https://support.apple.com/iphone/repair/battery-replacement (accessed November 1, 2026; numeric pricing failed to load).']


def content():
    parameters,_=summarize()
    prep=json.loads((OUT/'preparation_summary.json').read_text());analysis=json.loads((OUT/'analysis_summary.json').read_text())
    life=pd.read_csv(OUT/'predicted_life.csv');caps=pd.read_csv(OUT/'cap_contrasts.csv');tests=pd.read_csv(OUT/'interaction_tests.csv').set_index('interaction')
    cv=pd.read_csv(OUT/'cross_validation.csv').groupby('family').held_out_log_likelihood.sum()
    f=pd.read_csv(OUT/'financial_strategies.csv');fs=json.loads((OUT/'financial_summary.json').read_text());sens=pd.read_csv(OUT/'financial_sensitivity.csv')
    get=lambda r,c:life[(life.temp==25)&(life.rate==r)&(life.cap==c)].iloc[0]
    cold=life[(life.temp==0)&(life.rate==5)&(life.cap==100)].iloc[0]
    warm=life[(life.temp==40)&(life.rate==5)&(life.cap==100)].iloc[0]
    a,b=get(5,100),get(5,90);contrast=caps[(caps.temp==25)&(caps.rate==5)].iloc[0]
    before=f[(f.rate==5)&(f.cap==100)].iloc[0];after=f[(f.rate==5)&(f.cap==90)].iloc[0]
    alt=sens[sens['case']=='primary_lognormal'].iloc[0]
    reg=pd.read_csv(OUT/'regression.csv');beta=reg[reg.term=='cap90'].iloc[0]
    values={'distribution_parameters':parameters,'preparation':prep,'analysis':analysis,'baseline_life_25C':a.to_dict(),'cap_life_25C':b.to_dict(),
            'primary_cap_ratio':contrast.to_dict(),'financial_baseline':before.to_dict(),'financial_intervention':after.to_dict(),
            'lognormal_financial':alt.to_dict(),'cross_validation_log_likelihood':cv.to_dict(),
            'provenance':{'life':'predicted_life.csv','ratio':'cap_contrasts.csv','finance':'financial_strategies.csv','model_sensitivity':'financial_sensitivity.csv','counts':'preparation_summary.json','parameters':'model_parameters.json and distribution_parameters.csv'}}
    save_json('report_values.json',values)
    measures=text('''We measure standardized discharge capacity in ampere-hours and capacity retention relative to each cell's first valid reference measurement. The primary endpoint is equivalent-full-cycle exposure until capacity first falls below 80% of that initial measurement. Because reference tests are intermittent, a crossing is an interval between observations; cells without a crossing are right-censored. Equivalent full cycles (EFC) equal average cumulative charging and discharging throughput divided by nominal 3 Ah capacity, with baseline exposure subtracted. Total exposure includes diagnostic operations; operating-only exposure is a sensitivity measure. Predictors are charging rate, regular-operation charging cap, and controlled bath temperature. Observed trajectories and endpoint coverage describe the experimental evidence. Life ratios, median lifetimes, survival probabilities, and their confidence intervals are explicitly model estimates, not additional measurements (Luh & Blank, 2024).''')
    assumptions=text('''The 72 selected cells represent this KIT experiment, not smartphone batteries generally. We assume a common Weibull shape and independent cell variation conditional on experimental conditions; shared baths limit independent temperature replication. Upper voltage represents an approximate 90% or 100% cap, not a continuously recalibrated SOC limit. Capping also changes cycle depth, so it does not isolate one degradation mechanism. Diagnostic tests periodically charge both groups fully. Missing capacities remain missing, and incomplete lifetimes remain censored. Three flagged cold measurements and the final manual check-up are excluded initially. Alternative models and inclusion rules assess sensitivity. Smartphone financial projections additionally assume transferable lifetime, constant usage, and fresh replacement batteries; these assumptions are not validated observations.''')
    approach=text(f'''We analyzed the downloaded KIT version 2 result data, not simulated cell observations (Luh & Blank, 2024). Selection fixed discharge at 1C and the lower voltage at 3.249 V, leaving three charging rates (1/3C, 1C, 5/3C), two upper limits (approximately 90%, 100%), four bath temperatures (0, 10, 25, 40°C), and three physical replicates in each of 24 combinations. We verified archive checksums, mapped termination reasons from the supplied workbook, and linked reference capacities to original CSV rows.

An accelerated-failure-time regression models log lifetime scale using categorical factors and all two-factor interactions; 1C, 100%, and 25°C define the reference. The survival equation is S(t|x)=exp[-(t/eta(x))^k], with scale eta(x)=1000 exp(X beta) EFC and location fixed at zero. The common shape k pools information across sparse groups. Interval likelihoods retain uncertain crossing times, while survival likelihoods retain cells that stopped before a crossing. No midpoint is substituted as an observed failure. We resampled whole cells within conditions {analysis['bootstrap_requested']:,} times, refitting each sample to obtain nominal percentile confidence intervals. Repeated check-ups are not independent replicates.

Approximate likelihood-ratio tests assess the three interactions with Holm correction. Balanced three-fold validation withholds one replicate per condition and scores its censored predictive likelihood. Prespecified sensitivities use a lognormal distribution, rated-capacity normalization, operating-only throughput, flagged/final measurements, and pessimistic shutdown events. These checks assess dependence on model and censoring choices; they cannot establish smartphone transfer. Tables distinguish observed or derived endpoints from model estimates.''')
    results=text(f'''The primary dataset contains {prep['selected_cells']} cells and {prep['primary_selected_measurements']} retained reference-capacity measurements. There are {prep['primary_crossings']} observed threshold-crossing intervals and {prep['primary_right_censored']} right-censored endpoints. Exclusions comprise {prep['manual_excluded_selected']} final-manual and three cold records within selected cells; no capacity readings were imputed. Individual trajectories show substantial variation despite identical nominal settings. Three cells per combination remain the experimental replication, regardless of bootstrap count.

At 25°C, the Weibull model estimates median life at 100% charging as {get(1,100).median_EFC:,.0f}, {get(3,100).median_EFC:,.0f}, and {a.median_EFC:,.0f} EFC for 1/3C, 1C, and 5/3C respectively. Corresponding 90%-cap medians are {get(1,90).median_EFC:,.0f}, {get(3,90).median_EFC:,.0f}, and {b.median_EFC:,.0f} EFC. For the prespecified 5/3C cap comparison, nominal 95% intervals are [{a.ci_lo:,.0f}, {a.ci_hi:,.0f}] EFC without the cap and [{b.ci_lo:,.0f}, {b.ci_hi:,.0f}] EFC with it. The estimated life ratio is {contrast.life_ratio:.2f} [95% CI {contrast.ci_lo:.2f}, {contrast.ci_hi:.2f}]. This is a model-based comparison, not an observed doubling for every cell.

At the reference 1C/25°C condition, the cap coefficient on log lifetime scale is {beta.estimate:.3f} [95% CI {beta.ci_lo:.3f}, {beta.ci_hi:.3f}]. The charging-rate-by-temperature interaction is supported by an approximate likelihood-ratio statistic of {tests.loc['rate:temp','LR']:.2f} on six degrees of freedom (Holm-adjusted p < 0.001). Rate-by-cap and cap-by-temperature tests have adjusted p-values {tests.loc['rate:cap','p_holm']:.3f} and {tests.loc['cap:temp','p_holm']:.3f}. These nonsignificant interactions do not establish equal cap benefits everywhere. Individual contrast intervals are nominal, without multiplicity adjustment.

At 5/3C without the cap, estimated median life is {cold.median_EFC:,.0f} EFC at 0°C and {warm.median_EFC:,.0f} EFC at 40°C, compared with {a.median_EFC:,.0f} EFC at 25°C. This variation makes a single temperature-independent charging-rate penalty inappropriate. In the measured 25°C baseline group, two cells cross within intervals ending near 408 and 416 EFC, while the third remains uncrossed at approximately 606 EFC. The capped group also varies substantially. These observations explain why a pooled fitted median cannot be described as the actual lifetime of any individual cell.

All {analysis['bootstrap_success']:,} bootstrap fits converged. However, held-out prediction exposes important model dependence: summed log likelihood is {cv['weibull']:.1f} for Weibull versus {cv['lognormal']:.1f} for lognormal; higher is better. We retain the prespecified Weibull results but do not interpret their intervals as covering distributional uncertainty. The lognormal sensitivity estimates 5/3C median life at {pd.read_csv(OUT/'sensitivity_predictions.csv').query("family == 'lognormal' and temp == 25 and rate == 5 and cap == 100").median_EFC.iloc[0]:,.0f} EFC for 100% charging and {pd.read_csv(OUT/'sensitivity_predictions.csv').query("family == 'lognormal' and temp == 25 and rate == 5 and cap == 90").median_EFC.iloc[0]:,.0f} EFC for the cap. Direction agrees, but magnitude changes.

At 1/3C/25°C, all three capped cells remain above the threshold; their estimated median therefore extends beyond observed follow-up. Fault-related shutdowns also challenge independent censoring. Temperature findings are conditional on one apparatus, and controlled liquid cooling differs from phone operation. The experiment supports a cap-and-rate comparison in these NMC/graphite-SiO cells. It does not establish absolute smartphone life or an independently replicated causal temperature effect. Smartphone validation is the appropriate next investment before operational rollout.''')
    financial=text(f'''A 90% cap at unchanged 5/3C charging is the prespecified intervention, compared with 100% charging at 25°C. Using KIT lifetime estimates, a conditional three-year phone scenario projects replacement spending of {money(before.spend_USD)} before versus {money(after.spend_USD)} after, saving {money(after.savings_USD)} per owner (nominal 95% cell-bootstrap interval {money(after.savings_ci_lo)}–{money(after.savings_ci_hi)}). These are model estimates, not observed smartphone savings (Luh & Blank, 2024).

The monetary input is a dated $99 iPhone 16 repair fee reported in September 2024, not a verified current quotation (Burkhardt, 2024). Apple's accessible service page did not load numeric pricing when checked on November 1, 2026. Taxes, shipping, and additional service charges are excluded by assumption (Apple, n.d.). We adopt Apple's three-year first-owner power-use horizon and the weak review-site estimate of 0.7 nominal EFC/day: {fs['horizon_EFC']:.1f} EFC per strategy (Apple, 2024; Aussems, 2025). Equal throughput prevents the cap from appearing beneficial simply because each partial cycle delivers less charge.

A renewal calculation replaces each battery at 80% initial capacity with a fresh lifetime from the same fitted strategy. Expected replacements decline from {before.expected_replacements:.3f} to {after.expected_replacements:.3f}; the probability of at least one replacement declines from {100*before.replacement_probability:.1f}% to {100*after.replacement_probability:.1f}%. Existing chargers and a free policy change are assumed. The estimated break-even implementation cost is therefore {money(after.savings_USD)} per owner under this scenario. Charging inconvenience and time are not monetized.

Uncertainty comes from {analysis['bootstrap_success']:,} whole-cell bootstrap refits, propagated through replacement calculations. Numerical renewal expectations agree with separately labeled simulation checks; halving the EFC grid changes expected spending by less than {money(math.ceil(fs['half_step_max_USD_change']*100)/100)}. Price, usage, and transfer sensitivities are scenarios rather than confidence intervals. The alternative lognormal model projects {money(alt.savings_USD)} saving; the $119 Pro-model repair fee is a dated alternative price, not uncertainty about today's base-model fee.

The 766.5-EFC horizon exceeds the baseline group's last valid measured follow-up, requiring extrapolation. Weibull predicts held-out observations worse than lognormal. Further, KIT uses cylindrical cells and liquid cooling; phone transfer, everyday usage, and repeated-replacement behavior remain unvalidated. No separate calendar-aging model is fitted. The results justify funding smartphone-cell validation and a charging-policy pilot, not booking fleet savings or promising a guaranteed benefit. A positive lower interval endpoint reflects the fitted model, not protection against these structural assumptions.''')
    preliminary=[('Measures',measures),('Assumptions',assumptions),('Model / approach',approach),('Results',results)]
    finance=[('Financial Impacts',financial)]
    counts={k:words(v) for k,v in preliminary};counts['Financial Impacts']=words(financial)
    assert 100<=counts['Measures']<=150,counts
    assert 90<=counts['Assumptions']<=120,counts
    assert 200<=counts['Model / approach']<=300,counts
    assert 400<=counts['Results']<=600,counts
    assert 300<=counts['Financial Impacts']<=500,counts
    save_json('report_word_counts.json',counts)
    return preliminary,finance


def add_table(doc,headers,rows):
    table=doc.add_table(rows=1,cols=len(headers));table.style='Light Shading Accent 1'
    for cell,h in zip(table.rows[0].cells,headers):cell.text=str(h)
    trpr=table.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
    for row in rows:
        cells=table.add_row().cells
        for c,v in zip(cells,row):
            c.text=str(v)
            for p in c.paragraphs:
                for r in p.runs:r.font.size=Pt(8)
    return table


def build(name,title,sections,tables,figures,refs,notes=()):
    dest=OUT/'report_drafts';dest.mkdir(exist_ok=True)
    doc=Document();sec=doc.sections[0];sec.top_margin=sec.bottom_margin=Inches(.7)
    sec.left_margin=sec.right_margin=Inches(.75)
    sec.page_width=Inches(8.5);sec.page_height=Inches(11)
    normal=doc.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(10.5);normal.paragraph_format.space_after=Pt(7)
    doc.core_properties.title=title;doc.core_properties.author='Battery charging research project'
    doc.core_properties.created=doc.core_properties.modified=datetime(2026,11,1,tzinfo=timezone.utc)
    doc.add_heading(title,0);doc.add_paragraph('KIT version 2 • Experimental analysis with explicitly conditional financial scenarios')
    md=[f'# {title}','']
    for heading,body in sections:
        doc.add_heading(heading,1);md.extend([f'## {heading}','',body,''])
        # Sections are authored once; use paragraphs, not a duplicated Word narrative.
        for p in body.split('\n\n'):doc.add_paragraph(p)
    doc.add_heading('Supporting results',1);md+=['## Supporting results','']
    for note in notes:
        doc.add_paragraph(note);md.extend([note,''])
    for caption,headers,rows in tables:
        doc.add_paragraph(caption,style='Caption');add_table(doc,headers,rows)
        md.extend([caption,'','| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |'])
        md.extend('| '+' | '.join(map(str,r))+' |' for r in rows);md.append('')
    for file,caption in figures:
        # Keep figure + caption together on their own page for readability.
        doc.add_page_break();doc.add_picture(str(OUT/'figures'/file),width=Inches(6.8));doc.add_paragraph(caption,style='Caption')
        md.extend([f'![{caption}](../figures/{file})',''])
    doc.add_heading('References',1);md+=['## References','']
    for ref in refs:doc.add_paragraph(ref);md.extend([ref,''])
    doc.add_paragraph('Evidence and reproducibility: every measured capacity has source_file/source_row provenance in outputs/kit/observations.csv. Derived endpoints, model estimates, and financial assumptions are stored separately. Decisions: docs/decision_log.md. Numerical narrative bindings: outputs/kit/report_values.json.')
    doc.save(dest/(name+'.docx'));(dest/(name+'.md')).write_text('\n'.join(md))


def main():
    prelim,fin=content()
    par,distributions=summarize()
    shape=par['weibull_shape'];scale=par['reference_scale_EFC'];med=par['reference_median_EFC']
    ln=par['lognormal_sensitivity']
    reg=pd.read_csv(OUT/'regression.csv');tests=pd.read_csv(OUT/'interaction_tests.csv')
    pred=pd.read_csv(OUT/'predicted_life.csv');pred=pred[pred.temp==25].merge(distributions,on=['temp','rate','cap'],validate='one_to_one',suffixes=('','_parameter'))
    desc=pd.read_csv(OUT/'descriptives.csv');aggregate=desc.groupby('temp')[['n','observed_crossings']].sum().reset_index()
    interval=lambda p: f"[{p['ci_lo']:,.3f}, {p['ci_hi']:,.3f}]"
    tables=[('Table 1. Derived endpoint coverage after prespecified exclusions. Crossings are intervals, not exact failures.',
             ['Bath °C','Cells','Crossings','Right-censored'],[[int(r.temp),int(r.n),int(r.observed_crossings),int(r.n-r.observed_crossings)] for r in aggregate.itertuples()]),
            ('Table 2. Weibull parameters transformed from existing fitted/bootstrap vectors. Reference condition: 1C, 100% cap, 25°C. All estimates and intervals are conditional on this model.',
             ['Parameter','Estimate','Nominal 95% CI','Units / status'],
             [['Common shape k',f"{shape['estimate']:.3f}",interval(shape),'Dimensionless; estimated'],
              ['Reference scale eta',f"{scale['estimate']:,.3f}",interval(scale),'EFC; estimated'],
              ['Reference median',f"{med['estimate']:,.3f}",interval(med),'EFC; model-derived'],
              ['Location',0,'Not estimated','EFC; fixed at zero']]),
            ('Table 3. Model-estimated Weibull AFT coefficients with bootstrap SE and nominal 95% intervals. Intercept is log(reference scale/1000 EFC); log_shape is log(k). Interaction terms multiply the indicated binary indicators. No individual coefficient p-values are claimed.',
             ['Term','Estimate','Bootstrap SE','95% CI'],[[r.term,f'{r.estimate:.5f}',f'{r.bootstrap_SE:.5f}',f'[{r.ci_lo:.5f}, {r.ci_hi:.5f}]'] for r in reg.itertuples()]),
            ('Table 4. Approximate interaction likelihood-ratio tests; three-test Holm correction.',
             ['Interaction','LR','df','Raw p','Holm p'],[[r.interaction,f'{r.LR:.2f}',r.df,f'{r.p:.3g}',f'{r.p_holm:.3g}'] for r in tests.itertuples()]),
            ('Table 5. Condition-specific Weibull scale and median life at 25°C, with nominal 95% intervals. Shape k is common. *Median exceeds maximum follow-up in that condition. Scales are estimated distribution parameters, not measured lifetimes.',
             ['Rate','Cap','Scale eta (EFC)','Scale 95% CI','Median EFC','Median 95% CI'],
             [[LABEL[r.rate],f'{r.cap}%',f'{r.weibull_scale_EFC:,.1f}',f'[{r.scale_ci_lo:,.1f}, {r.scale_ci_hi:,.1f}]',f'{r.median_EFC:,.0f}'+('*' if r.median_beyond_max_followup else ''),f'[{r.ci_lo:,.0f}, {r.ci_hi:,.0f}]'] for r in pred.itertuples()])]
    notes=[
        'Distribution definitions: t is baseline-subtracted EFC; k is Weibull shape and eta(x) is condition-specific scale. S(t|x)=exp[-(t/eta(x))^k] for t >= 0. Scale eta is the 63.2th failure percentile, not the median. Median life = eta(x)*(ln 2)^(1/k). Location is fixed at zero.',
        'Coding: log(eta(x)/1000 EFC)=X beta. X contains an intercept and binary indicators for rate_1third (1/3C), rate_5third (5/3C), cap90, and temp0/temp10/temp40, plus all cross-factor two-way products. Reference indicators are all zero at 1C/100%/25°C; no three-way term is fitted. All logarithms are natural.',
        'Bootstrap intervals transform each complete fitted parameter vector before taking percentiles; median intervals preserve the dependence between shape and scale. Coefficients are rounded for display; full precision and all 24 condition scales are in outputs/kit/distribution_parameters.csv and model.json.',
        f"Lognormal sensitivity: log(L/1000 EFC)=X beta_LN + sigma Z, where Z is standard normal, sigma={ln['sigma']:.6f}, and the reference median is {ln['reference_median_EFC']:,.3f} EFC. Its scale is a median, unlike Weibull eta. These are point estimates only; no secondary bootstrap intervals were calculated. All lognormal coefficients are in outputs/kit/lognormal_regression.csv.",
        'Fixed protocol and endpoint settings: discharge 1C; lower voltage 3.249 V; upper voltages 4.092 V (~90%) and 4.200 V (~100%); nominal capacity 3 Ah; endpoint 0.80 of each cell’s initial valid capacity. These are design/analysis settings rather than fitted degradation parameters. The seed is 20261101 and there are 2,000 successful cell-bootstrap fits.'
    ]
    build('Preliminary_Methods_and_Results','Preliminary Methods and Results',prelim,tables,
          [('observed_25C.png','Figure 1. Measured reference capacities at 25°C. Connecting lines only link observations; they do not impute missing values.'),
           ('modeled_life_by_temperature.png','Figure 2. Model-estimated lifetime medians and nominal 95% bootstrap intervals. Panels use different vertical scales; temperature effects are conditional on shared bath apparatus.'),
           ('observed_intervals_25C.png','Figure 3. Derived lifetime intervals at 25°C. Right-pointing triangles denote right-censored cells.')],[KITREF],notes)
    f=pd.read_csv(OUT/'financial_strategies.csv');inputs=pd.read_csv(OUT/'sources/cost_inputs.csv')
    fs=json.loads((OUT/'financial_summary.json').read_text())
    ft=[('Table 1. Financial inputs. All money is illustrative USD, using a dated repair estimate.',
         ['Input','Value','Evidence status'],[[r.item,str(r.value)+' '+r.unit,r.quantity_class] for r in inputs.itertuples()]),
        ('Table 2. Lifetime-distribution inputs to the 25°C financial scenarios. All rows share Weibull shape k; scales and lognormal medians are estimates. Lognormal sensitivity values are point estimates only.',
         ['Strategy','Weibull scale (EFC)','Scale 95% CI','Lognormal median (EFC)'],
         [[f'{LABEL[r.rate]} {r.cap}%',f'{r.weibull_scale_EFC:,.3f}',f'[{r.scale_ci_lo:,.3f}, {r.scale_ci_hi:,.3f}]',f'{r.lognormal_median_EFC:,.3f}'] for r in pred.itertuples()]),
        ('Table 3. Conditional three-year replacement spending and savings versus 5/3C/100% at 25°C. Intervals are nominal 95% cell-bootstrap intervals conditional on Weibull/phone-transfer assumptions.',
         ['Strategy','Expected replacements','Spending USD','Saving USD [95% CI]'],[[f'{LABEL[r.rate]} {r.cap}%',f'{r.expected_replacements:.3f}',money(r.spend_USD),f'{money(r.savings_USD)} [{money(r.savings_ci_lo)}, {money(r.savings_ci_hi)}]'] for r in f.itertuples()])]
    financial_notes=[
        f"Distribution inputs: S(t)=exp[-(t/eta)^k], location fixed at zero; k={shape['estimate']:.3f} (nominal 95% CI {shape['ci_lo']:.3f}–{shape['ci_hi']:.3f}). Table 2 lists each eta in EFC. The lognormal sensitivity has sigma={ln['sigma']:.6f} and each listed median, with log L normally distributed. These are fitted parameters, not additional cell measurements.",
        f"Scenario settings: 25°C; 0.80 initial-capacity replacement threshold; horizon {fs['horizon_EFC']:.1f} nominal EFC; lifetime-transfer multiplier 1 (assumed, unvalidated); independent fresh replacement lives; renewal grid {fs['grid_step_EFC']:.2f} EFC, checked at half that step. Zero location is fixed, not fitted. Uncertainty uses the same 2,000 joint cell-bootstrap fits, not independent draws from marginal parameter intervals.",
        'Sensitivity settings: assumed use 0.5/0.7/1.0 EFC/day; assumed lifetime multipliers 0.5/1/2; dated repair scenarios $99/$119. These values define scenarios, not observed phone usage distributions or confidence bounds. No discounting is applied. Common-shape assumptions and the weaker Weibull held-out performance remain limitations.'
    ]
    build('Financial_Impacts','Financial Impacts',fin,ft,
          [('conditional_costs.png','Figure 1. Conditional replacement spending. Excludes initial phone and charger purchases; interval uncertainty does not cover transfer to smartphones.'),
           ('conditional_annual_spend.png','Figure 2. Conditional annual cumulative replacement spending for the prespecified cap intervention.')],REFS,financial_notes)
    print('Report drafts generated:',(OUT/'report_word_counts.json').read_text())

if __name__=='__main__':main()
