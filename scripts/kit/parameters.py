"""Report existing fitted parameters on interpretable scales; never refit or fill data."""
import json
import numpy as np
import pandas as pd
from .common import OUT,save_json
from .model import design,median,SCALE
from .analysis import scenarios


def summarize():
    model=json.loads((OUT/'model.json').read_text())
    theta=np.asarray(model['theta'])
    names=model['names']
    boots=pd.read_csv(OUT/'bootstrap_fits.csv')
    draws=boots[boots.success][[f'p{i}' for i in range(len(theta))]].to_numpy()
    grid=scenarios();X,design_names,_=design(grid)
    assert names==design_names
    scale=SCALE*np.exp(X@theta[:-1])
    scale_draws=SCALE*np.exp(draws[:,:-1]@X.T)
    low,high=np.quantile(scale_draws,[.025,.975],axis=0)
    shape=np.exp(theta[-1]);shape_ci=np.quantile(np.exp(draws[:,-1]),[.025,.975])
    reference=int(grid.index[(grid.rate==3)&(grid.cap==100)&(grid.temp==25)][0])
    reference_medians=np.array([median(p,X[[reference]])[0] for p in draws])
    med_ci=np.quantile(reference_medians,[.025,.975])
    summary={'quantity_class':'model-estimated from existing fitted KIT data',
             'weibull_shape':{'estimate':shape,'ci_lo':shape_ci[0],'ci_hi':shape_ci[1],'units':'dimensionless','common_across_conditions':True},
             'reference_scale_EFC':{'estimate':scale[reference],'ci_lo':low[reference],'ci_hi':high[reference]},
             'reference_median_EFC':{'estimate':median(theta,X[[reference]])[0],'ci_lo':med_ci[0],'ci_hi':med_ci[1]},
             'reference_condition':{'charging_rate_C':1,'cap_percent':100,'temperature_degC':25},
             'fixed_location_EFC':{'value':0,'quantity_class':'fixed model assumption; not estimated'},
             'input_EFC_scale':SCALE,'bootstrap_samples':len(draws),
             'weibull_survival':'S(t|x)=exp[-(t/eta(x))^k], t>=0',
             'scale_equation':'eta(x)=1000*exp(X beta) EFC',
             'median_equation':'median(x)=eta(x)*(ln 2)^(1/k)',
             'sources':['model.json','bootstrap_fits.csv','sensitivity_models.json']}
    secondary=next(m for m in json.loads((OUT/'sensitivity_models.json').read_text()) if m['family']=='lognormal')
    ln=np.asarray(secondary['theta']);sigma=np.exp(ln[-1])
    summary['lognormal_sensitivity']={'sigma':sigma,'reference_median_EFC':SCALE*np.exp(ln[0]),
                                     'quantity_class':'model-estimated sensitivity point estimates; no bootstrap CIs',
                                     'equation':'log(L/1000)=X beta_LN + sigma*Z, Z~Normal(0,1)'}
    grid['weibull_scale_EFC']=scale;grid['scale_ci_lo']=low;grid['scale_ci_hi']=high
    grid['weibull_shape']=shape;grid['fixed_location_EFC']=0
    grid['lognormal_median_EFC']=SCALE*np.exp(X@ln[:-1]);grid['lognormal_sigma']=sigma
    grid['quantity_class']='model-estimated; lognormal sensitivity has point estimates only'
    # Verify that printed scales reconstruct the already-published life results.
    predictions=pd.read_csv(OUT/'predicted_life.csv')
    merged=grid.merge(predictions,on=['temp','rate','cap'],validate='one_to_one')
    np.testing.assert_allclose(merged.weibull_scale_EFC*np.log(2)**(1/shape),merged.median_EFC,rtol=1e-12)
    assert np.isclose(np.exp(-(scale[reference]/scale[reference])**shape),np.exp(-1))
    grid.to_csv(OUT/'distribution_parameters.csv',index=False)
    pd.DataFrame({'term':names+['log_sigma'],'estimate':ln,'quantity_class':'model-estimated sensitivity; no bootstrap CI'}).to_csv(OUT/'lognormal_regression.csv',index=False)
    save_json('model_parameters.json',summary)
    return summary,grid

if __name__=='__main__':
    result,_=summarize();print(json.dumps(result,indent=2,default=float))
