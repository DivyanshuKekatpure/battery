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
    approach=text(f'''We selected 72 KIT cells: 1/3C, 1C, or 5/3C charging; approximately 90% or 100% caps; and 0, 10, 25, or 40°C baths, with three replicates per combination (Luh & Blank, 2024). Discharge was fixed at 1C, lower voltage at 3.249 V, and upper voltages at 4.092/4.200 V. Checksums and source-row links establish provenance.

The Weibull accelerated-failure-time model uses S(t|x)=exp[-(t/eta(x))^k] for t≥0, with zero location and common shape k. Scale eta(x)=1000 exp(X beta) EFC is the 63.2% failure quantile; median life is eta(x)(ln 2)^(1/k). X contains an intercept, binary rate_1third/rate_5third, cap90, temp0/temp10/temp40 indicators, and all cross-factor two-way products. Reference indicators are zero at 1C/100%/25°C; logarithms are natural. Tables report fitted parameters.

Interval likelihoods retain uncertain crossings; survival likelihoods retain right-censored cells. The likelihood uses measured brackets directly, rather than substituting midpoint failure times or dropping incomplete cases. Seed 20261101 fixes resampling. We refitted {analysis['bootstrap_requested']:,} whole-cell bootstrap samples within conditions. Parameter transformations preserve joint shape/scale dependence before calculating percentile intervals. Repeated measurements are not independent replicates.

Holm-adjusted likelihood-ratio tests assess interactions. Three-fold validation withholds one replicate per condition. Sensitivities change capacity normalization, throughput, flagged/final measurements, and shutdown assumptions. The lognormal alternative uses log(L/1000)=X beta_LN+sigma Z, Z standard normal, with sigma={parameters['lognormal_sensitivity']['sigma']:.6f}; its scale is its median (reference {parameters['lognormal_sensitivity']['reference_median_EFC']:,.3f} EFC). Secondary estimates have no bootstrap intervals.''')
    results=text(f'''The primary analysis retains {prep['primary_selected_measurements']} measurements from {prep['selected_cells']} cells: {prep['primary_crossings']} threshold-crossing intervals and {prep['primary_right_censored']} right-censored endpoints. Eleven final-manual and three cold measurements were excluded; none were imputed. Replication remains three physical cells per condition. Figure 1 shows individual histories; triangles in Figure 3 indicate censoring.

At 25°C, estimated uncapped median lives are {get(1,100).median_EFC:,.0f}, {get(3,100).median_EFC:,.0f}, and {a.median_EFC:,.0f} EFC for 1/3C, 1C, and 5/3C. Capped medians are {get(1,90).median_EFC:,.0f}, {get(3,90).median_EFC:,.0f}, and {b.median_EFC:,.0f}. The 5/3C cap life ratio is {contrast.life_ratio:.2f} (nominal 95% CI {contrast.ci_lo:.2f}–{contrast.ci_hi:.2f}). Estimated medians have intervals {a.ci_lo:,.0f}–{a.ci_hi:,.0f} EFC uncapped and {b.ci_lo:,.0f}–{b.ci_hi:,.0f} capped. These are distribution estimates, not observed lifetimes for individual cells.

The fitted common shape is {parameters['weibull_shape']['estimate']:.3f}; reference scale is {parameters['reference_scale_EFC']['estimate']:,.3f} EFC. Parameter intervals and regression coefficients appear below. At 1C/25°C, cap90 has coefficient {beta.estimate:.3f} (95% CI {beta.ci_lo:.3f}–{beta.ci_hi:.3f}). Rate-by-temperature interaction yields LR={tests.loc['rate:temp','LR']:.2f}, six degrees of freedom, Holm-adjusted p<0.001. Rate-by-cap and cap-by-temperature adjusted p-values are {tests.loc['rate:cap','p_holm']:.3f} and {tests.loc['cap:temp','p_holm']:.3f}; nonsignificance does not establish identical benefits. Contrast intervals are unadjusted.

At 5/3C without capping, estimated median life changes from {cold.median_EFC:,.0f} EFC at 0°C to {a.median_EFC:,.0f} at 25°C and {warm.median_EFC:,.0f} at 40°C (Figure 2). A temperature-independent rate penalty is therefore inappropriate within this model.

All {analysis['bootstrap_success']:,} bootstrap fits converged. However, held-out log likelihood totals {cv['weibull']:.1f} for Weibull versus {cv['lognormal']:.1f} for lognormal; higher is better. This substantial predictive weakness limits confidence in the prespecified Weibull family. Its intervals exclude distributional uncertainty.

All three 1/3C/25°C capped cells remain uncrossed, so their estimated median exceeds measured follow-up. Fault-related shutdowns challenge independent censoring; shared baths limit temperature replication. Diagnostic full charges and cylindrical, liquid-cooled construction further restrict transfer. The results support smartphone-cell validation, rather than a quantitative promise about phone lifetimes.

Nominal intervals condition on the distribution, common shape, and within-condition resampling. The stronger lognormal validation score shows that between-model uncertainty needs separate consideration. A positive fitted cap effect does not establish a precise population benefit or validate transfer to smartphones.''')
    financial=text(f'''At 25°C, capping 5/3C charging at approximately 90%, instead of 100%, is the prespecified intervention. The conditional three-year phone scenario estimates replacement spending of {money(before.spend_USD)} before versus {money(after.spend_USD)} after: saving {money(after.savings_USD)} per owner (nominal 95% cell-bootstrap interval {money(after.savings_ci_lo)}–{money(after.savings_ci_hi)}). These remain explicitly conditional projections from KIT cells, not observed phone savings (Luh & Blank, 2024).

The $99 fee is a dated September 2024 iPhone 16 estimate; $119 is a dated Pro-model sensitivity (Burkhardt, 2024). Apple's accessible page failed to load current numeric pricing. Additional fees, tax, shipping, and implementation costs are assumed zero (Apple, n.d.). We adopt Apple's three-year horizon and the weak review-site estimate of 0.7 nominal EFC/day: {fs['horizon_EFC']:.1f} EFC for every strategy (Apple, 2024; Aussems, 2025). Equal throughput avoids crediting the cap merely for delivering less charge per session.

A renewal calculation assumes independent fresh replacement lives at 80% initial capacity. Its distribution S(t)=exp[-(t/eta)^k] uses common shape k={parameters['weibull_shape']['estimate']:.3f} (95% CI {parameters['weibull_shape']['ci_lo']:.3f}–{parameters['weibull_shape']['ci_hi']:.3f}), zero location, and the strategy-specific scales tabulated below. Existing chargers, lifetime-transfer multiplier 1, no discounting, and no separate calendar-aging model are assumptions. Expected replacements fall from {before.expected_replacements:.3f} to {after.expected_replacements:.3f}; probability of any replacement falls from {100*before.replacement_probability:.1f}% to {100*after.replacement_probability:.1f}%. Break-even implementation spending is {money(after.savings_USD)} per owner; inconvenience is unpriced.

Intervals propagate {analysis['bootstrap_success']:,} whole-cell bootstrap refits. A {fs['grid_step_EFC']:.2f}-EFC renewal grid agrees with separately labeled simulation; halving its step changes spending by less than {money(math.ceil(fs['half_step_max_USD_change']*100)/100)}. Assumed usage 0.5–1.0 EFC/day and lifetime multipliers 0.5/1/2 are sensitivities, not confidence bounds. Lognormal sensitivity uses sigma={parameters['lognormal_sensitivity']['sigma']:.6f} and the listed medians, giving {money(alt.savings_USD)} saving; no secondary bootstrap was performed.

The horizon exceeds baseline measured follow-up and requires extrapolation. Weibull predicts held-out observations worse than lognormal. Phone transfer and everyday replacement behavior remain unvalidated. Positive conditional intervals do not cover these structural uncertainties. The evidence supports funding validation and a pilot, not booking fleet savings or guaranteeing benefits.''')
    preliminary=[('Measures',measures),('Assumptions',assumptions),('Model / approach',approach),('Results',results)]
    finance=[('Financial Impacts',financial)]
    counts={k:words(v) for k,v in preliminary};counts['Financial Impacts']=words(financial)
    assert 100<=counts['Measures']<=150,counts
    assert 90<=counts['Assumptions']<=120,counts
    assert 200<=counts['Model / approach']<=300,counts
    assert 300<=counts['Results']<=600,counts
    assert 300<=counts['Financial Impacts']<=500,counts
    save_json('report_narrative_word_counts.json',counts)
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


def build(name,title,sections,tables,figures,refs):
    dest=OUT/'report_drafts';dest.mkdir(exist_ok=True)
    doc=Document();sec=doc.sections[0];sec.top_margin=sec.bottom_margin=Inches(.7)
    sec.left_margin=sec.right_margin=Inches(.75)
    sec.page_width=Inches(8.5);sec.page_height=Inches(11)
    normal=doc.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(10.5);normal.paragraph_format.space_after=Pt(7)
    doc.core_properties.title=title;doc.core_properties.author='Battery charging research project'
    doc.core_properties.created=doc.core_properties.modified=datetime(2026,11,1,tzinfo=timezone.utc)
    doc.add_heading(title,0)
    md=[f'# {title}',''];counts={}
    attach_to='Results' if name=='Preliminary_Methods_and_Results' else 'Financial Impacts'
    for heading,body in sections:
        doc.add_heading(heading,1);md.extend([f'## {heading}','',body,''])
        for paragraph in body.split('\n\n'):doc.add_paragraph(paragraph)
        count=words(body)
        if heading==attach_to:
            for caption,headers,rows in tables:
                doc.add_paragraph(caption,style='Caption');add_table(doc,headers,rows)
                md.extend([caption,'','| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |'])
                md.extend('| '+' | '.join(map(str,row))+' |' for row in rows);md.append('')
                count+=words(caption)+sum(map(words,headers))+sum(words(str(v)) for row in rows for v in row)
            for file,caption in figures:
                doc.add_paragraph().paragraph_format.keep_with_next=True
                doc.add_picture(str(OUT/'figures'/file),width=Inches(6.8))
                doc.add_paragraph(caption,style='Caption')
                md.extend([f'![{caption}](../figures/{file})',''])
                count+=words(caption)
        counts[heading]=count
    doc.add_heading('References',1);md+=['## References','']
    for ref in refs:doc.add_paragraph(ref);md.extend([ref,''])
    doc.save(dest/(name+'.docx'));(dest/(name+'.md')).write_text('\n'.join(md))
    return counts


def main():
    prelim,fin=content()
    par,distributions=summarize()
    shape=par['weibull_shape'];scale=par['reference_scale_EFC'];med=par['reference_median_EFC']
    ln=par['lognormal_sensitivity']
    reg=pd.read_csv(OUT/'regression.csv');tests=pd.read_csv(OUT/'interaction_tests.csv')
    pred=pd.read_csv(OUT/'predicted_life.csv');pred=pred[pred.temp==25].merge(distributions,on=['temp','rate','cap'],validate='one_to_one',suffixes=('','_parameter'))
    desc=pd.read_csv(OUT/'descriptives.csv');aggregate=desc.groupby('temp')[['n','observed_crossings']].sum().reset_index()
    interval=lambda p: f"{p['ci_lo']:,.3f}–{p['ci_hi']:,.3f}"
    tables=[('Table 1. Derived endpoint coverage.',
             ['Bath °C','Cells','Crossings','Right-censored'],[[int(r.temp),int(r.n),int(r.observed_crossings),int(r.n-r.observed_crossings)] for r in aggregate.itertuples()]),
            ('Table 2. Estimated Weibull parameters: reference 1C/100%/25°C; location fixed.',
             ['Parameter','Estimate','95% CI'],
             [['Shape k',f"{shape['estimate']:.3f}",interval(shape)],
              ['Scale eta (EFC)',f"{scale['estimate']:,.3f}",interval(scale)],
              ['Median (EFC)',f"{med['estimate']:,.3f}",interval(med)],
              ['Location (EFC)',0,'Fixed']]),
            ('Table 3. Fitted coefficients: bootstrap SE/CIs; intercept=log(reference eta/1000); log_shape=log(k).',
             ['Term','Estimate','SE','95% CI'],[[r.term,f'{r.estimate:.5f}',f'{r.bootstrap_SE:.5f}',f'{r.ci_lo:.5f}–{r.ci_hi:.5f}'] for r in reg.itertuples()]),
            ('Table 4. Approximate interaction tests; Holm correction.',
             ['Interaction','LR','df','Raw p','Holm p'],[[r.interaction,f'{r.LR:.2f}',r.df,f'{r.p:.3g}',f'{r.p_holm:.3g}'] for r in tests.itertuples()]),
            ('Table 5. Estimated 25°C lifetimes/scales; *median beyond measured follow-up.',
             ['Rate','Cap','eta/EFC','95% CI','Median/EFC','95% CI'],
             [[LABEL[r.rate],f'{r.cap}%',f'{r.weibull_scale_EFC:,.1f}',f'{r.scale_ci_lo:,.1f}–{r.scale_ci_hi:,.1f}',f'{r.median_EFC:,.0f}'+('*' if r.median_beyond_max_followup else ''),f'{r.ci_lo:,.0f}–{r.ci_hi:,.0f}'] for r in pred.itertuples()])]
    counts=build('Preliminary_Methods_and_Results','Preliminary Methods and Results',prelim,tables,
          [('observed_25C.png','Figure 1. Measured 25°C retention; lines connect observations.'),
           ('modeled_life_by_temperature.png','Figure 2. Estimated medians/95% intervals; panel scales differ.'),
           ('observed_intervals_25C.png','Figure 3. Derived 25°C intervals; triangles indicate censoring.')],[KITREF])
    f=pd.read_csv(OUT/'financial_strategies.csv');inputs=pd.read_csv(OUT/'sources/cost_inputs.csv')
    fs=json.loads((OUT/'financial_summary.json').read_text())
    ft=[('Table 1. Sourced/assumed financial inputs.',
         ['Input','Value','Evidence status'],[[r.item,str(r.value)+' '+r.unit,r.quantity_class] for r in inputs.itertuples()]),
        ('Table 2. Estimated 25°C distribution inputs; lognormal values are point estimates.',
         ['Strategy','Weibull eta/EFC','95% CI','Lognormal median/EFC'],
         [[f'{LABEL[r.rate]} {r.cap}%',f'{r.weibull_scale_EFC:,.3f}',f'{r.scale_ci_lo:,.3f}–{r.scale_ci_hi:,.3f}',f'{r.lognormal_median_EFC:,.3f}'] for r in pred.itertuples()]),
        ('Table 3. Conditional spending/saving versus 5/3C/100%; 95% intervals.',
         ['Strategy','Replacements','Spending/USD','Saving/USD (95% CI)'],[[f'{LABEL[r.rate]} {r.cap}%',f'{r.expected_replacements:.3f}',money(r.spend_USD),f'{money(r.savings_USD)} ({money(r.savings_ci_lo)}–{money(r.savings_ci_hi)})'] for r in f.itertuples()])]
    counts.update(build('Financial_Impacts','Financial Impacts',fin,ft,
          [('conditional_costs.png','Figure 1. Conditional replacement spending; 95% intervals.'),
           ('conditional_annual_spend.png','Figure 2. Conditional cumulative replacement spending.')],REFS))
    save_json('report_word_counts.json',counts)
    assert 100<=counts['Measures']<=150 and 90<=counts['Assumptions']<=120,counts
    assert 100<=counts['Model / approach']<=300 and 300<=counts['Results']<=600,counts
    assert 300<=counts['Financial Impacts']<=500,counts
    print('Section words including tables/captions (excluding headings/references):',counts)

if __name__=='__main__':main()
