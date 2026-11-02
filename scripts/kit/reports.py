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
'Rossignol, J. (2026, September 17). Apple increases battery replacement fee for iPhone 18 Pro and Pro Max. MacRumors. https://www.macrumors.com/2026/09/17/apple-higher-iphone-18-pro-battery-fee/ (accessed November 1, 2026; Pro-model fees only).']


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
    cells=pd.read_csv(OUT/'cross_validation_cells.csv');wcells=cells[cells.family=='weibull'].nsmallest(2,'held_out_log_likelihood')
    lcells=cells[(cells.family=='lognormal')&cells.cell.isin(wcells.cell)]
    assert (wcells.predicted_median_EFC<wcells.lower_EFC).all(),'worst cells should outlive predictions'
    worst=wcells.held_out_log_likelihood.sum();rest_w=cv['weibull']-worst;rest_ln=cv['lognormal']-lcells.held_out_log_likelihood.sum()
    describe=lambda r:f"{r.cell} ({r.temp}°C, {LABEL[r.rate]}, {r.cap}%)"
    grid_sens=sens[sens['case']=='assumed_usage_transfer_and_dated_price']
    usual=grid_sens[grid_sens.lifetime_multiplier<=1].savings_USD
    doubled=grid_sens[(grid_sens.lifetime_multiplier==2)&(grid_sens.usage_EFC_day==0.7)&(grid_sens.price_USD==99)].savings_USD.iloc[0]
    tied='both '+f"{tests.loc['rate:cap','p_holm']:.3f}" if round(tests.loc['rate:cap','p_holm'],3)==round(tests.loc['cap:temp','p_holm'],3) else f"{tests.loc['rate:cap','p_holm']:.3f} and {tests.loc['cap:temp','p_holm']:.3f}"
    values={'distribution_parameters':parameters,'preparation':prep,'analysis':analysis,'baseline_life_25C':a.to_dict(),'cap_life_25C':b.to_dict(),
            'primary_cap_ratio':contrast.to_dict(),'financial_baseline':before.to_dict(),'financial_intervention':after.to_dict(),
            'lognormal_financial':alt.to_dict(),'cross_validation_log_likelihood':cv.to_dict(),
            'cross_validation_worst_weibull_cells':[{k:(None if isinstance(v,float) and math.isinf(v) else v) for k,v in r.items()} for r in wcells.to_dict('records')],'cross_validation_without_worst':{'weibull':rest_w,'lognormal':rest_ln},
            'financial_sensitivity_range':{'multiplier_le_1_min':usual.min(),'multiplier_le_1_max':usual.max(),'multiplier_2_usage_0.7_price_99':doubled},
            'provenance':{'life':'predicted_life.csv','ratio':'cap_contrasts.csv','finance':'financial_strategies.csv','model_sensitivity':'financial_sensitivity.csv','cross_validation':'cross_validation_cells.csv','counts':'preparation_summary.json','parameters':'model_parameters.json and distribution_parameters.csv'}}
    save_json('report_values.json',values)
    measures=text('''We measure standardized discharge capacity in ampere-hours, then divide by each cell's first valid reference capacity to calculate retention. Our main outcome is equivalent full cycles (EFC) until capacity first falls below 80% of that starting value. Tests are intermittent. We therefore bracket crossings between observations and right-censor cells that haven't crossed. EFC equals average cumulative charging and discharging throughput divided by nominal 3 Ah capacity, after subtracting baseline exposure. We include diagnostic operations and test operating-only exposure separately. We compare charging rate, regular-operation charging cap, and controlled bath temperature. Individual histories and threshold coverage show what we observed; life ratios, median lifetimes, survival probabilities and their confidence intervals come from the model (Luh & Blank, 2024).''')
    assumptions=text('''These 72 cells tell us about the KIT experiment. Generalizing to smartphones requires validation. We assume a common Weibull shape and independent cell variation within conditions, although shared baths limit independent temperature replication. Upper voltage gives approximate 90% or 100% caps without continuously recalibrating SOC. Capping changes cycle depth too, preventing isolation of one degradation mechanism. Diagnostics periodically charge both groups fully. We leave missing capacities missing and incomplete lifetimes censored, excluding three flagged cold measurements and the final manual check-up from primary analysis. Alternative models and inclusion rules test sensitivity. Phone projections assume transferable lifetime, constant usage and fresh replacement batteries. These assumptions remain unvalidated.''')
    approach=text(f'''We selected 72 KIT cells across 1/3C, 1C and 5/3C charging, approximately 90%/100% caps, and 0, 10, 25 and 40°C baths: three replicates per combination (Luh & Blank, 2024). We fixed discharge at 1C, lower voltage at 3.249 V and upper voltages at 4.092/4.200 V. Checksums verify files; source-row links trace measurements.

We fitted a Weibull accelerated-failure-time model: S(t|x)=exp[-(t/eta(x))^k], t≥0, location zero, common shape k. Scale eta(x)=1000 exp(X beta) EFC is the 63.2% failure quantile; median life equals eta(x)(ln 2)^(1/k). X includes an intercept, binary rate_1third/rate_5third, cap90, temp0/temp10/temp40 indicators and all cross-factor two-way products. Indicators equal zero at reference 1C/100%/25°C; logarithms are natural. Tables give fitted parameters.

Interval likelihoods use measured crossing brackets; survival likelihoods handle right-censored cells. We neither substitute midpoint failure times nor discard incomplete cases. Using seed 20261101, we refitted {analysis['bootstrap_requested']:,} whole-cell bootstrap samples within conditions, preserving joint shape/scale dependence when transforming parameters for percentile intervals. Repeated measurements aren't independent replicates.

We tested interactions with Holm-adjusted likelihood-ratio tests. Three-fold validation withholds one replicate per condition; sensitivity checks vary capacity normalization, throughput, flagged/final measurements and shutdown assumptions. The lognormal alternative uses log(L/1000)=X beta_LN+sigma Z, Z standard normal, sigma={parameters['lognormal_sensitivity']['sigma']:.3f}; its scale equals its median (reference {parameters['lognormal_sensitivity']['reference_median_EFC']:,.0f} EFC). Secondary estimates have no bootstrap intervals.''')
    results=text(f'''We analyzed {prep['primary_selected_measurements']} measurements from {prep['selected_cells']} cells, giving {prep['primary_crossings']} threshold-crossing intervals and {prep['primary_right_censored']} right-censored endpoints. We excluded eleven final-manual and three cold measurements without imputing any values. Figure 1 shows histories; Figure 3 marks censoring with triangles.

At 25°C, uncapped median-life estimates are {get(1,100).median_EFC:,.0f}, {get(3,100).median_EFC:,.0f} and {a.median_EFC:,.0f} EFC at 1/3C, 1C and 5/3C. With capping, they rise to {get(1,90).median_EFC:,.0f}, {get(3,90).median_EFC:,.0f} and {b.median_EFC:,.0f}. At 5/3C, that's a life ratio of {contrast.life_ratio:.2f} (nominal 95% CI {contrast.ci_lo:.2f}–{contrast.ci_hi:.2f}); median intervals are {a.ci_lo:,.0f}–{a.ci_hi:,.0f} EFC uncapped and {b.ci_lo:,.0f}–{b.ci_hi:,.0f} capped. These describe fitted distributions. They aren't observed individual lifetimes.

The common shape is {parameters['weibull_shape']['estimate']:.2f}; reference scale is {parameters['reference_scale_EFC']['estimate']:,.0f} EFC. At 1C/25°C, cap90's coefficient is {beta.estimate:.2f} (95% CI {beta.ci_lo:.2f}–{beta.ci_hi:.2f}). Rate-by-temperature gives LR={tests.loc['rate:temp','LR']:.2f}, six degrees of freedom, Holm-adjusted p<0.001. Rate-by-cap and cap-by-temperature adjusted p-values are {tied}; neither establishes identical benefits. With three cells per condition, within-condition resampling likely understates uncertainty: several Table 3 interaction intervals exclude zero although Table 4 tests don't. We base interaction conclusions on Table 4.

Temperature matters here. At uncapped 5/3C, modeled median life is {cold.median_EFC:,.0f} EFC at 0°C, {a.median_EFC:,.0f} at 25°C and {warm.median_EFC:,.0f} at 40°C (Figure 2), so this model doesn't support a temperature-independent rate penalty.

All {analysis['bootstrap_success']:,} bootstrap fits converged. But Weibull predicted poorly: held-out log likelihood totals {cv['weibull']:.1f}, versus {cv['lognormal']:.1f} for lognormal (higher is better). Two cells that outlived predictions, {describe(wcells.iloc[0])} and {describe(wcells.iloc[1])}, contribute {worst:.1f}; Weibull's steep shape makes such lives very unlikely. Without them, totals are {rest_w:.1f} versus {rest_ln:.1f}. We deliberately keep prespecified Weibull, with lognormal as the main robustness check.

None of the three capped 1/3C/25°C cells crossed the threshold, so their estimated median exceeds measured follow-up. Fault-related shutdowns challenge independent censoring. Shared baths limit temperature replication, while full diagnostic charges and cylindrical, liquid-cooled cells restrict smartphone transfer. We need smartphone-cell validation before promising quantitative phone lifetimes.

Nominal intervals assume the distribution and common shape. A positive fitted cap effect establishes neither a precise population benefit nor smartphone transfer.''')
    financial=text(f'''We propose capping 5/3C charging at approximately 90% instead of 100%, at 25°C, as prespecified. In our three-year phone scenario, estimated replacement spending falls from {money(before.spend_USD)} to {money(after.spend_USD)}: {money(after.savings_USD)} saved per owner (nominal 95% cell-bootstrap interval {money(after.savings_ci_lo)}–{money(after.savings_ci_hi)}). The baseline, uncapped 5/3C, wears fastest, so this is essentially one avoided replacement: expected replacements fall from {before.expected_replacements:.3f} to {after.expected_replacements:.3f}. The upper bound exceeds one fee because some refits predict over one baseline replacement. These projections depend on KIT cells; we haven't observed phone savings (Luh & Blank, 2024).

We use a September 2024 iPhone 16 fee estimate of $99, with $119 for Pro-model sensitivity (Burkhardt, 2024). A September 2026 report confirms the $119 Pro fee and lists $129 for iPhone 18 Pro (Rossignol, 2026); we couldn't verify the current base fee. Savings scale proportionally with price. We assume zero additional fees, tax, shipping and implementation costs. Apple's three-year horizon and a weak review-site estimate of 0.7 nominal EFC/day give {fs['horizon_EFC']:.1f} EFC (Apple, 2024; Aussems, 2025). Equal delivered charge prevents crediting capping for smaller charges per session.

We replace batteries at 80% initial capacity, assuming independent fresh replacement lives in a renewal calculation. S(t)=exp[-(t/eta)^k] uses common shape k={parameters['weibull_shape']['estimate']:.2f} (95% CI {parameters['weibull_shape']['ci_lo']:.2f}–{parameters['weibull_shape']['ci_hi']:.2f}), zero location and the tabulated strategy scales. We assume existing chargers, lifetime-transfer multiplier 1, no discounting and no separate calendar-aging model. Any-replacement probability falls from {100*before.replacement_probability:.1f}% to {100*after.replacement_probability:.1f}%. We don't price inconvenience.

We calculate intervals from {analysis['bootstrap_success']:,} whole-cell bootstrap refits. The {fs['grid_step_EFC']:.2f}-EFC renewal grid agrees with separately labeled simulation; halving the step changes spending by less than {money(math.ceil(fs['half_step_max_USD_change']*100)/100)}. Across 0.5–1.0 EFC/day usage, both fees and lifetime multipliers 0.5–1, savings range ${usual.min():,.0f}–${usual.max():,.0f}. If phone batteries last twice as long as KIT cells, savings fall to {money(doubled)} at 0.7 EFC/day. These are sensitivities, not confidence bounds. Lognormal, with sigma={parameters['lognormal_sensitivity']['sigma']:.3f} and the listed medians, gives {money(alt.savings_USD)} savings without a secondary bootstrap.

The horizon exceeds baseline measured follow-up, requiring extrapolation, and Weibull predicts held-out observations worse than lognormal. Phone transfer and everyday replacement behavior remain unvalidated. Positive conditional intervals leave those structural uncertainties out. We'd support funding validation and a pilot. We can't yet book fleet savings or guarantee benefits.''')
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
    interval=lambda p,d: f"{p['ci_lo']:,.{d}f}–{p['ci_hi']:,.{d}f}"
    tables=[('Table 1. Derived endpoint coverage.',
             ['Bath °C','Cells','Crossings','Right-censored'],[[int(r.temp),int(r.n),int(r.observed_crossings),int(r.n-r.observed_crossings)] for r in aggregate.itertuples()]),
            ('Table 2. Estimated Weibull parameters: reference 1C/100%/25°C; location fixed.',
             ['Parameter','Estimate','95% CI'],
             [['Shape k',f"{shape['estimate']:.2f}",interval(shape,2)],
              ['Scale eta (EFC)',f"{scale['estimate']:,.0f}",interval(scale,0)],
              ['Median (EFC)',f"{med['estimate']:,.0f}",interval(med,0)],
              ['Location (EFC)',0,'Fixed']]),
            ('Table 3. Fitted coefficients: bootstrap SE/CIs; intercept=log(reference eta/1000); log_shape=log(k).',
             ['Term','Estimate','SE','2.5%','97.5%'],[[r.term,f'{r.estimate:.2f}',f'{r.bootstrap_SE:.2f}',f'{r.ci_lo:.2f}',f'{r.ci_hi:.2f}'] for r in reg.itertuples()]),
            ('Table 4. Approximate interaction tests; Holm correction.',
             ['Interaction','LR','df','Raw p','Holm p'],[[r.interaction,f'{r.LR:.2f}',r.df,f'{r.p:.3g}',f'{r.p_holm:.3g}'] for r in tests.itertuples()]),
            ('Table 5. Estimated 25°C lifetimes/scales; *median beyond measured follow-up.',
             ['Rate','Cap','eta/EFC','95% CI','Median/EFC','95% CI'],
             [[LABEL[r.rate],f'{r.cap}%',f'{r.weibull_scale_EFC:,.0f}',f'{r.scale_ci_lo:,.0f}–{r.scale_ci_hi:,.0f}',f'{r.median_EFC:,.0f}'+('*' if r.median_beyond_max_followup else ''),f'{r.ci_lo:,.0f}–{r.ci_hi:,.0f}'] for r in pred.itertuples()])]
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
         [[f'{LABEL[r.rate]} {r.cap}%',f'{r.weibull_scale_EFC:,.0f}',f'{r.scale_ci_lo:,.0f}–{r.scale_ci_hi:,.0f}',f'{r.lognormal_median_EFC:,.0f}'] for r in pred.itertuples()]),
        ('Table 3. Conditional spending/saving versus 5/3C/100%; 95% intervals.',
         ['Strategy','Replacements','Spending/USD','Saving/USD (95% CI)'],[[f'{LABEL[r.rate]} {r.cap}%',f'{r.expected_replacements:.3f}',money(r.spend_USD),f'{money(r.savings_USD)} ({money(r.savings_ci_lo)}–{money(r.savings_ci_hi)})'] for r in f.itertuples()])]
    counts.update(build('Financial_Impacts','Capping Fast Charging: Financial Impacts',fin,ft,
          [('conditional_costs.png','Figure 1. Conditional replacement spending; 95% intervals.'),
           ('conditional_annual_spend.png','Figure 2. Conditional cumulative replacement spending.')],REFS))
    save_json('report_word_counts.json',counts)
    assert 100<=counts['Measures']<=150 and 90<=counts['Assumptions']<=120,counts
    assert 100<=counts['Model / approach']<=300 and 300<=counts['Results']<=600,counts
    assert 300<=counts['Financial Impacts']<=500,counts
    print('Section words including tables/captions (excluding headings/references):',counts)

if __name__=='__main__':main()
