"""Acceptance checks for real outputs and shared-source report renderings."""
import json,zipfile,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from .common import OUT,ROOT,save_json
from .reports import content,words


def main():
    d=pd.read_csv(OUT/'endpoints_primary.csv');o=pd.read_csv(OUT/'observations.csv')
    assert len(d)==72 and d.groupby(['temp','rate','cap']).size().eq(3).all()
    assert np.allclose(d.discharge_rate_C,1) and np.allclose(d.lower_voltage_V,3.249)
    assert (d.lower_EFC>=0).all() and (d.upper_EFC>=d.lower_EFC).all()
    assert (o.selected & o.primary_included).sum()==859
    assert 'source_file' in o and 'source_row' in o
    b=pd.read_csv(OUT/'bootstrap_fits.csv');assert len(b)==2000 and b.success.mean()>=.95
    assert b.sample_hash.nunique()>1900
    assert not o.duplicated(['cell','checkup_counter']).any()
    f=pd.read_csv(OUT/'financial_strategies.csv');base=f[(f.rate==5)&(f.cap==100)].iloc[0]
    assert base.savings_USD==base.savings_ci_lo==base.savings_ci_hi==0
    assert np.allclose(f.savings_USD,base.spend_USD-f.spend_USD)
    p,fbody=content()
    parameters=json.loads((OUT/'model_parameters.json').read_text())
    distributions=pd.read_csv(OUT/'distribution_parameters.csv')
    life=pd.read_csv(OUT/'predicted_life.csv')
    joined=distributions.merge(life,on=['temp','rate','cap'],validate='one_to_one')
    assert len(joined)==24
    np.testing.assert_allclose(joined.weibull_scale_EFC*np.log(2)**(1/parameters['weibull_shape']['estimate']),joined.median_EFC,rtol=1e-12)
    parameter_rows=distributions[distributions.temp==25]

    reported_counts=json.loads((OUT/'report_word_counts.json').read_text())
    report_checks=[]
    for name,sections,nimages in [('Preliminary_Methods_and_Results',p,3),('Financial_Impacts',fbody,2)]:
        path=OUT/'report_drafts'/(name+'.docx');doc=Document(path)
        text='\n'.join(x.text for x in doc.paragraphs)
        headings=[x.text for x in doc.paragraphs if x.style.name=='Heading 1']
        assert headings==[heading for heading,_ in sections]+['References'],headings
        assert 'Supporting results' not in text
        # Count the rendered section, including all table text and captions.
        rendered_counts={};current=None
        for block in doc.iter_inner_content():
            if isinstance(block,Paragraph):
                if block.style.name=='Heading 1':
                    current=block.text if block.text!='References' else None
                    if current:rendered_counts[current]=0
                elif current:rendered_counts[current]+=words(block.text)
            elif isinstance(block,Table) and current:
                rendered_counts[current]+=sum(words(cell.text) for row in block.rows for cell in row.cells)
        for heading,count in rendered_counts.items():assert reported_counts[heading]==count,(heading,count,reported_counts)
        assert 300<=rendered_counts.get('Financial Impacts',400)<=500
        if 'Results' in rendered_counts:assert 300<=rendered_counts['Results']<=600

        for _,body in sections:
            for para in body.split('\n\n'):assert para in text,(name,'narrative differs')
        assert len(doc.inline_shapes)==nimages
        assert len(doc.tables)>0
        table_text='\n'.join(' '.join(c.text for c in row.cells) for table in doc.tables for row in table.rows)
        complete_text=text+'\n'+table_text
        assert f"{parameters['weibull_shape']['estimate']:.2f}" in complete_text
        assert 'S(t' in text and 'location' in text.lower()
        for row in parameter_rows.itertuples():
            # Both reports round scales to whole EFC.
            displayed=f'{row.weibull_scale_EFC:,.0f}'
            assert displayed in table_text,(name,displayed)
        assert f"{parameters['lognormal_sensitivity']['sigma']:.3f}" in text

        assert not any(token in text for token in ['5,237','820.2','multistage','[insert','TODO','$4.55'])
        assert 'References' in text and 'https://doi.org/10.35097/1969' in text
        xml=zipfile.ZipFile(path).read('word/document.xml')
        report_checks.append({'report':name,'tables':len(doc.tables),'figures':len(doc.inline_shapes),'document_xml_sha256':hashlib.sha256(xml).hexdigest(),'shared_narrative_verified':True,'rendered_section_word_counts':rendered_counts,'assignment_headings_only':True})
    save_json('acceptance_checks.json',{'primary_design_valid':True,'source_columns_present':True,'bootstrap_count':len(b),
             'bootstrap_success':int(b.success.sum()),'financial_identity_valid':True,'distribution_parameters_reconstruct_published_medians':True,'word_limits':json.loads((OUT/'report_word_counts.json').read_text()),'reports':report_checks})
    print('Acceptance checks passed',flush=True)

if __name__=='__main__':main()
