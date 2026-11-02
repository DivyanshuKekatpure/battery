"""Prepare real KIT observations and censored cell endpoints. No imputation."""
import re
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from openpyxl import load_workbook
from .common import ROOT, OUT, save_json

MANUAL = datetime(2024,5,29,tzinfo=timezone.utc).timestamp()

def termination_map():
    file=next((ROOT/'data2/data/dataset').glob('Cycling*.xlsx'))
    sheet=load_workbook(file,read_only=True,data_only=True).worksheets[0]
    out={}
    # Positions are read from the actual three-block source table (header row 95).
    for rownum,row in enumerate(sheet.values,1):
        for ident,date,reason in [(0,1,2),(7,8,10),(15,17,19)]:
            val=row[ident]
            if isinstance(val,str) and (m:=re.fullmatch(r'(\d{2}) - (\d{2})',val.strip())):
                key=tuple(map(int,m.groups()))
                assert key not in out
                out[key]={'termination_reason':str(row[reason] or 'unspecified'),
                          'termination_date':str(row[date] or ''),
                          'termination_source':file.name,
                          'termination_sheet_row':rownum}
    assert len(out)==228, len(out)
    return out

def make_endpoints(obs, selected, variant='primary'):
    rows=[]
    for c in selected.to_dict('records'):
        g=obs[obs.cell==c['cell']].sort_values('timestamp_s').copy()
        if variant not in ['include_cold','include_all']:g=g[~g.cold_flag]
        if variant not in ['include_manual','include_all']:g=g[~g.manual_flag]
        assert len(g)>=2
        denominator=3 if variant=='rated_capacity' else g.capacity_Ah.iloc[0]
        xcol='operating_EFC' if variant=='operating_EFC' else 'total_EFC'
        x=g[xcol].to_numpy()-g[xcol].iloc[0]
        assert (np.diff(x)>=-1e-7).all()
        hit=np.flatnonzero(g.capacity_Ah.to_numpy()/denominator < 0.8)
        if len(hit):
            i=hit[0]
            assert i>0
            lo,hi=x[i-1],x[i]
            # Zero throughput interval is an exact endpoint only for alternate exposure.
            event='exact' if hi==lo else 'interval'
        else:lo,hi,event=x[-1],np.inf,'right'
        if variant=='pessimistic_shutdown' and event=='right' and c['termination_reason']!='survivor':
            # Explicitly assumed sensitivity event, never written as measured failure.
            hi=lo; event='assumed_exact_shutdown'
        rows.append({**c,'lower_EFC':lo,'upper_EFC':hi,'event_type':event,
                     'n_checkups':len(g),'initial_capacity_Ah':g.capacity_Ah.iloc[0],
                     'last_retention':g.capacity_Ah.iloc[-1]/denominator,
                     'last_EFC':x[-1], 'endpoint_class':'assumed' if event.startswith('assumed') else 'derived',
                     'variant':variant})
    return pd.DataFrame(rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cfg=pd.read_csv(ROOT/'outputs/kit_audit/cell_conditions.csv')
    obs=pd.read_csv(ROOT/'outputs/kit_audit/capacity_checkups.csv')
    terms=termination_map()
    cfg=pd.DataFrame([{**c,**terms[(int(c['slave']),int(c['channel']))]} for c in cfg.to_dict('records')])
    cfg['rate']=np.round(cfg.charge_rate_C*3).astype(int) # 1,3,5 represent exact thirds
    cfg['cap']=np.where(cfg.upper_voltage_V<4.19,90,100)
    cfg['temp']=cfg.temperature_degC.astype(int)
    cfg['selected']=(cfg.aging_type=='cyclic') & np.isclose(cfg.discharge_rate_C,1) & np.isclose(cfg.lower_voltage_V,3.249)
    selected=cfg[cfg.selected].sort_values(['temp','rate','cap','replicate'])
    assert len(selected)==72 and selected.groupby(['temp','rate','cap']).size().eq(3).all()
    cfg['inclusion_reason']=np.where(cfg.selected,'primary factorial design','outside prespecified fixed-discharge/fixed-lower-voltage design')
    cfg.to_csv(OUT/'cell_inclusion.csv',index=False)
    obs['cold_flag']=~obs.discharge_end_temperature_degC.between(20,30)
    obs['manual_flag']=obs.timestamp_s>=MANUAL
    obs['primary_included']=~obs.cold_flag & ~obs.manual_flag
    obs['quantity_class']='measured_capacity_and_derived_exposure'
    assert not obs.duplicated(['cell','checkup_counter']).any()
    obs=obs.merge(cfg[['cell','temp','rate','cap','selected']],on='cell',validate='many_to_one')
    for cell,idx in obs.groupby('cell').groups.items():
        first=obs.loc[idx].sort_values('timestamp_s').iloc[0]
        obs.loc[idx,'baseline_total_EFC']=obs.loc[idx,'total_EFC']-first.total_EFC
        obs.loc[idx,'retention_initial']=obs.loc[idx,'capacity_Ah']/first.capacity_Ah
    obs.to_csv(OUT/'observations.csv',index=False)
    variants=['primary','rated_capacity','operating_EFC','include_cold','include_manual','include_all','pessimistic_shutdown']
    for v in variants:make_endpoints(obs,selected,v).to_csv(OUT/f'endpoints_{v}.csv',index=False)
    primary=pd.read_csv(OUT/'endpoints_primary.csv')
    desc=primary.groupby(['temp','rate','cap']).agg(n=('cell','size'),observed_crossings=('event_type',lambda x:sum(x!='right')),min_last_EFC=('last_EFC','min'),max_last_EFC=('last_EFC','max')).reset_index()
    desc.to_csv(OUT/'descriptives.csv',index=False)
    summary={'selected_cells':len(primary),'conditions':len(desc),'all_reference_measurements':len(obs),
             'selected_measurements':int(obs.selected.sum()),'primary_selected_measurements':int((obs.selected & obs.primary_included).sum()),
             'cold_excluded_all':int(obs.cold_flag.sum()),'manual_excluded_selected':int((obs.selected & obs.manual_flag).sum()),
             'primary_crossings':int((primary.event_type!='right').sum()),'primary_right_censored':int((primary.event_type=='right').sum()),
             'term_reasons':primary.groupby('termination_reason').size().to_dict(),
             'source':'KIT v2 results DOI 10.35097/1969; source_file/source_row refer to EOC archive member and CSV row',
             'method':'Measured capacity unfilled; retention and lifetime intervals derived; pessimistic shutdown variant explicitly assumed.'}
    save_json('preparation_summary.json',summary)
    print(summary,flush=True)

if __name__=='__main__':main()
