"""Acceptance checks for real outputs and shared-source report renderings."""
import json,zipfile,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from docx import Document
from .common import OUT,ROOT,save_json
from .reports import content


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
    report_checks=[]
    for name,sections,nimages in [('Preliminary_Methods_and_Results',p,3),('Financial_Impacts',fbody,2)]:
        path=OUT/'report_drafts'/(name+'.docx');doc=Document(path)
        text='\n'.join(x.text for x in doc.paragraphs)
        for _,body in sections:
            for para in body.split('\n\n'):assert para in text,(name,'narrative differs')
        assert len(doc.inline_shapes)==nimages
        assert len(doc.tables)>0
        assert not any(token in text for token in ['5,237','820.2','multistage','[insert','TODO','$4.55'])
        assert 'References' in text and 'https://doi.org/10.35097/1969' in text
        xml=zipfile.ZipFile(path).read('word/document.xml')
        report_checks.append({'report':name,'tables':len(doc.tables),'figures':len(doc.inline_shapes),'document_xml_sha256':hashlib.sha256(xml).hexdigest(),'shared_narrative_verified':True})
    save_json('acceptance_checks.json',{'primary_design_valid':True,'source_columns_present':True,'bootstrap_count':len(b),
             'bootstrap_success':int(b.success.sum()),'financial_identity_valid':True,'word_limits':json.loads((OUT/'report_word_counts.json').read_text()),'reports':report_checks})
    print('Acceptance checks passed',flush=True)

if __name__=='__main__':main()
