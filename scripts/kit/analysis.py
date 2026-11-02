"""Prespecified KIT survival analysis. Bootstrap rows are MODEL ESTIMATES."""
import os
os.environ.setdefault('VECLIB_MAXIMUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import hashlib,json
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from scipy.stats import chi2
from .common import OUT,SEED,save_json
from .model import design,fit,median,contributions


def bootstrap_one(args):
    b,X,lo,up,strata,theta=args
    rng=np.random.default_rng(SEED+b)
    idx=np.concatenate([rng.choice(s,len(s),replace=True) for s in strata])
    r=fit(X[idx],lo[idx],up[idx],start=theta)
    return {'replicate':b,'success':r['success'],'gradient_max':r['gradient_max'],'attempts':r['attempts'],'nll':r['nll'],
            'sample_hash':hashlib.sha256(idx.tobytes()).hexdigest(),**{f'p{i}':v for i,v in enumerate(r['theta'])}}

def scenarios():
    return pd.DataFrame([{'temp':t,'rate':r,'cap':c} for t in [0,10,25,40] for r in [1,3,5] for c in [100,90]])

def cross_validate(df,X,lo,up):
    """Three-fold held-out likelihood, per fold and per held-out cell."""
    validation=[];cells=[]
    for family in ['weibull','lognormal']:
        for rep in [1,2,3]:
            hold=df.replicate.to_numpy()==rep;f=fit(X[~hold],lo[~hold],up[~hold],family=family)
            assert f['success'],(family,rep,f)
            ll,_=contributions(f['theta'],X[hold],lo[hold],up[hold],family)
            pred=median(f['theta'],X[hold],family)
            validation.append({'family':family,'held_out_replicate':rep,'n_train':int((~hold).sum()),'n_test':int(hold.sum()),'held_out_log_likelihood':float(ll.sum()),'quantity_class':'model-estimated predictive validation'})
            for (_,r),l,m in zip(df[hold].iterrows(),ll,pred):
                cells.append({'family':family,'held_out_replicate':rep,'cell':r.cell,'temp':r.temp,'rate':r.rate,'cap':r.cap,'lower_EFC':r.lower_EFC,'upper_EFC':r.upper_EFC,
                              'predicted_median_EFC':float(m),'held_out_log_likelihood':float(l),'quantity_class':'model-estimated predictive validation'})
    pd.DataFrame(validation).to_csv(OUT/'cross_validation.csv',index=False)
    pd.DataFrame(cells).to_csv(OUT/'cross_validation_cells.csv',index=False)


def run(bootstrap=2000,workers=4):
    df=pd.read_csv(OUT/'endpoints_primary.csv');X,names,groups=design(df)
    lo,up=df.lower_EFC.to_numpy(),df.upper_EFC.to_numpy()
    point=fit(X,lo,up);assert point['success'],point
    params=point.pop('theta');print('Primary fit',point,'shape',np.exp(params[-1]),flush=True)
    save_json('model.json',{'family':'weibull','names':names,'theta':params.tolist(),'fit':point,
                           'quantity_class':'model-estimated','n_cells':len(df),'input_sha256':hashlib.sha256((OUT/'endpoints_primary.csv').read_bytes()).hexdigest()})
    strata=list(df.groupby(['temp','rate','cap'],sort=True).indices.values())
    boot=[]
    jobs=((b,X,lo,up,strata,params) for b in range(bootstrap))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i,result in enumerate(pool.map(bootstrap_one,jobs,chunksize=10),1):
            boot.append(result)
            if i%200==0:print(f'Bootstrap {i}/{bootstrap}',flush=True)
    boot=pd.DataFrame(boot);boot['quantity_class']='model-estimated bootstrap refits';boot.to_csv(OUT/'bootstrap_fits.csv',index=False)
    success=boot[boot.success];assert len(success)>=.95*bootstrap,f'Only {len(success)} valid bootstrap fits'
    ps=success[[f'p{i}' for i in range(len(params))]].to_numpy()
    reg=pd.DataFrame({'term':names+['log_shape'],'estimate':params,'ci_lo':np.quantile(ps,.025,axis=0),'ci_hi':np.quantile(ps,.975,axis=0),'bootstrap_SE':ps.std(axis=0,ddof=1)})
    reg['quantity_class']='model-estimated';reg.to_csv(OUT/'regression.csv',index=False)
    grid=scenarios();G,_,_=design(grid);grid['median_EFC']=median(params,G)
    med=np.array([median(p,G) for p in ps])
    grid['ci_lo'],grid['ci_hi']=np.quantile(med,[.025,.975],axis=0)
    grid['quantity_class']='model-estimated'
    support=df.groupby(['temp','rate','cap']).last_EFC.agg(['min','max']).reset_index().rename(columns={'min':'min_followup_EFC','max':'max_followup_EFC'})
    grid=grid.merge(support,on=['temp','rate','cap'],sort=False)
    grid['median_beyond_max_followup']=grid.median_EFC>grid.max_followup_EFC
    grid.to_csv(OUT/'predicted_life.csv',index=False)
    contrasts=[]
    for t in [0,10,25,40]:
        for r in [1,3,5]:
            a=grid.index[(grid.temp==t)&(grid.rate==r)&(grid.cap==90)][0]
            b=grid.index[(grid.temp==t)&(grid.rate==r)&(grid.cap==100)][0]
            samples=np.exp(ps[:,:-1]@(G[a]-G[b]))
            contrasts.append({'temp':t,'rate':r,'comparison':'90% / 100% life ratio','life_ratio':float(np.exp((G[a]-G[b])@params[:-1])),
                              'ci_lo':np.quantile(samples,.025),'ci_hi':np.quantile(samples,.975),'quantity_class':'model-estimated'})
    pd.DataFrame(contrasts).to_csv(OUT/'cap_contrasts.csv',index=False)
    tests=[]
    for term in ['rate:cap','rate:temp','cap:temp']:
        reduced,_,_=design(df,omit=term)
        f=fit(reduced,lo,up);assert f['success'],f
        stat=max(0,2*(f['nll']-point['nll']));dfree=len(groups[term])
        tests.append({'interaction':term,'LR':stat,'df':dfree,'p':chi2.sf(stat,dfree),'quantity_class':'model-estimated; approximate test'})
    order=np.argsort([r['p'] for r in tests]);running=0
    for j,i in enumerate(order):running=max(running,min(1,tests[i]['p']*(3-j)));tests[i]['p_holm']=running
    pd.DataFrame(tests).to_csv(OUT/'interaction_tests.csv',index=False)
    sensitivity=[];models=[]
    for variant,family in [('primary','lognormal')]+[(v,'weibull') for v in ['rated_capacity','operating_EFC','include_cold','include_manual','include_all','pessimistic_shutdown']]:
        d=pd.read_csv(OUT/f'endpoints_{variant}.csv');xx,_,_=design(d)
        f=fit(xx,d.lower_EFC.to_numpy(),d.upper_EFC.to_numpy(),family=family,start=params if family=='weibull' else None)
        assert f['success'],(variant,family,f)
        pred=median(f['theta'],G,family)
        models.append({'variant':variant,'family':family,'theta':f['theta'].tolist(),'nll':f['nll'],'success':f['success']})
        for i,row in grid.iterrows():
            sensitivity.append({'variant':variant,'family':family,'temp':row.temp,'rate':row.rate,'cap':row.cap,'median_EFC':pred[i],'quantity_class':'model-estimated sensitivity'})
    pd.DataFrame(sensitivity).to_csv(OUT/'sensitivity_predictions.csv',index=False);save_json('sensitivity_models.json',models)
    cross_validate(df,X,lo,up)
    save_json('analysis_summary.json',{'bootstrap_requested':bootstrap,'bootstrap_success':len(success),'seed':SEED,'shape':float(np.exp(params[-1])),
                                      'fit':point,'n_coefficients':len(names),'n_cells':len(df),'events':int(np.isfinite(up).sum()),
                                      'sensitivity_models':len(models),'quantity_class':'model-estimated'})
    print('Analysis complete',len(success),'bootstrap fits',flush=True)

if __name__=='__main__':run()
