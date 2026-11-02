"""CONDITIONAL modeled phone-cost scenarios, not observed financial outcomes."""
import json
import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.fft import rfft,irfft,next_fast_len
from .model import design,SCALE
from .analysis import scenarios
from .common import OUT,SEED,save_json


def cdf(t,scale,param,family='weibull'):
    t=np.asarray(t)
    if family=='weibull':return -np.expm1(-(np.maximum(t,0)/scale)**param)
    with np.errstate(divide='ignore'):return ndtr(np.log(np.maximum(t,0)/scale)/param)


def renewal(scale,param,horizons,family='weibull',step=.25):
    """Expected count via sums of truncated linear convolutions of lifetime masses.

    Lifetimes rounded up to grid -> counts are a numerical approximation, not data.
    Convolutions truncated to horizon, padded to avoid FFT circular aliasing.
    """
    hs=np.atleast_1d(horizons).astype(float)
    if hs.max()==0:return np.zeros(len(hs))
    n=int(np.ceil(hs.max()/step));edges=np.arange(n+1)*step
    q=np.r_[0,np.diff(cdf(edges,scale,param,family))]
    term=q.copy();total=term.copy();size=next_fast_len(2*n+1);fq=rfft(q,size)
    for _ in range(1000):
        term=np.maximum(irfft(rfft(term,size)*fq,size)[:n+1],0)
        total+=term
        if term.sum()<1e-12:break
    else:raise ValueError('Renewal sum did not converge')
    expected=np.cumsum(total)
    return np.interp(hs,edges,expected)


def costs(theta,G,horizons,family='weibull',multiplier=1,step=.25):
    scales=SCALE*np.exp(G@theta[:-1])*multiplier
    par=np.exp(theta[-1])
    return np.array([renewal(s,par,horizons,family,step) for s in scales])


def monte_carlo(scale,param,horizon,family='weibull',n=300000):
    """Labeled simulated validation only; never used as empirical cell data."""
    rng=np.random.default_rng(SEED+999);elapsed=np.zeros(n);count=np.zeros(n);active=np.arange(n)
    while len(active):
        draws=scale*(rng.weibull(param,len(active)) if family=='weibull' else rng.lognormal(0,param,len(active)))
        elapsed[active]+=draws;active=active[elapsed[active]<=horizon];count[active]+=1
    return float(count.mean()),float(count.std(ddof=1)/np.sqrt(n))


def run():
    inputs=pd.read_csv(OUT/'sources/cost_inputs.csv').set_index('item').value
    price=float(inputs.battery_replacement_price);usage=float(inputs.usage_EFC_day);years=float(inputs.ownership_years)
    model=json.loads((OUT/'model.json').read_text());theta=np.array(model['theta'])
    grid=scenarios();g=grid[grid.temp==25].reset_index(drop=True);G,_,_=design(g)
    base=int(g.index[(g.rate==5)&(g.cap==100)][0]);target=int(g.index[(g.rate==5)&(g.cap==90)][0])
    horizons=np.array([usage*365*y for y in [1,2,3]]+[1000.])
    primary=costs(theta,G,horizons)
    boot=pd.read_csv(OUT/'bootstrap_fits.csv');ps=boot[boot.success][[f'p{i}' for i in range(len(theta))]].to_numpy()
    draws=[]
    for i,p in enumerate(ps):
        draws.append(costs(p,G,horizons))
        if (i+1)%400==0:print('Financial bootstrap',i+1,flush=True)
    draws=np.array(draws)
    np.savez_compressed(OUT/'financial_bootstrap.npz',expected_counts=draws,quantity_class='model-estimated conditional scenarios')
    rows=[]
    point_shares=cdf(horizons[2],SCALE*np.exp(G@theta[:-1]),np.exp(theta[-1]))
    bs_shares=np.array([cdf(horizons[2],SCALE*np.exp(G@p[:-1]),np.exp(p[-1])) for p in ps])
    for j,row in g.iterrows():
        diff=price*(draws[:,base,2]-draws[:,j,2]);spend=price*draws[:,j,2]
        rows.append({**row.to_dict(),'expected_replacements':primary[j,2], 'replacement_probability':point_shares[j],
                     'prob_ci_lo':np.quantile(bs_shares[:,j],.025),'prob_ci_hi':np.quantile(bs_shares[:,j],.975),
                     'spend_USD':price*primary[j,2], 'spend_ci_lo':np.quantile(spend,.025),'spend_ci_hi':np.quantile(spend,.975),
                     'savings_USD':price*(primary[base,2]-primary[j,2]),'savings_ci_lo':np.quantile(diff,.025),'savings_ci_hi':np.quantile(diff,.975),
                     'cost_per_1000_EFC_USD':price*primary[j,3],
                     'quantity_class':'model-estimated; conditional phone scenario'})
    pd.DataFrame(rows).to_csv(OUT/'financial_strategies.csv',index=False)
    annual=[]
    for y in [1,2,3]:
        for j,row in g.iterrows():
            d=price*draws[:,j,y-1]
            annual.append({**row.to_dict(),'year':y,'spend_USD':price*primary[j,y-1],'ci_lo':np.quantile(d,.025),'ci_hi':np.quantile(d,.975),'quantity_class':'model-estimated'})
    pd.DataFrame(annual).to_csv(OUT/'annual_cost.csv',index=False)
    # Numerical discretization check, before interpreting monetary results.
    fine=costs(theta,G,horizons,step=.125)
    refine=float(np.max(np.abs(primary-fine))*price)
    assert refine<.10,refine
    simulations=[]
    for family,p in [('weibull',theta)]+[(m['family'],np.array(m['theta'])) for m in json.loads((OUT/'sensitivity_models.json').read_text()) if m['family']=='lognormal']:
        scales=SCALE*np.exp(G@p[:-1]);par=np.exp(p[-1])
        for j in [base,target]:
            estimate=renewal(scales[j],par,[horizons[2]],family)[0]
            mc,se=monte_carlo(scales[j],par,horizons[2],family)
            assert abs(estimate-mc)<max(6*se,.003)
            simulations.append({'family':family,'cap':int(g.iloc[j].cap),'numerical_expected_count':estimate,'simulation_mean':mc,'simulation_SE':se,'simulation_owners':300000,'quantity_class':'simulated validation only'})
    pd.DataFrame(simulations).to_csv(OUT/'renewal_validation.csv',index=False)
    sens=[]
    for use in [.5,.7,1.]:
        for mult in [.5,1,2]:
            for cost in [price,119.]:
                values=costs(theta,G,[use*365*years],multiplier=mult)[:,0]
                sens.append({'case':'assumed_usage_transfer_and_dated_price','usage_EFC_day':use,'lifetime_multiplier':mult,'price_USD':cost,
                             'baseline_USD':cost*values[base],'cap90_USD':cost*values[target],'savings_USD':cost*(values[base]-values[target]),'quantity_class':'model-estimated sensitivity; inputs assumed or dated'})
    for m in json.loads((OUT/'sensitivity_models.json').read_text()):
        values=costs(np.array(m['theta']),G,[horizons[2]],family=m['family'])[:,0]
        sens.append({'case':m['variant']+'_'+m['family'],'usage_EFC_day':usage,'lifetime_multiplier':1,'price_USD':price,
                     'baseline_USD':price*values[base],'cap90_USD':price*values[target],'savings_USD':price*(values[base]-values[target]),'quantity_class':'model-estimated sensitivity'})
    pd.DataFrame(sens).to_csv(OUT/'financial_sensitivity.csv',index=False)
    save_json('financial_summary.json',{'horizon_EFC':float(horizons[2]),'price_USD_dated_2024':price,'baseline_index':base,'primary_intervention_index':target,
              'break_even_implementation_USD':rows[target]['savings_USD'],'grid_step_EFC':.25,'half_step_max_USD_change':refine,
              'bootstrap_models':len(ps),'scope':'conditional phone scenario; no calibrated cylindrical-to-phone transfer; no calendar submodel',
              'financial_inputs_class':'assumed usage and horizon; dated sourced repair price','quantity_class':'model-estimated'})
    print(pd.DataFrame(rows).to_string(index=False),flush=True)

if __name__=='__main__':run()
