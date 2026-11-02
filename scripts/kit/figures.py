"""Figures distinguish observed trajectories from model-estimated summaries."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kit-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from .common import OUT

LABEL={1:'1/3C',3:'1C',5:'5/3C'}
COLORS={90:'#137c66',100:'#c64e43'}

def finish(fig,name):
    fig.savefig(OUT/'figures'/name,dpi=170,bbox_inches='tight');plt.close(fig)

def main():
    (OUT/'figures').mkdir(exist_ok=True)
    obs=pd.read_csv(OUT/'observations.csv');obs=obs[obs.selected & obs.primary_included]
    pred=pd.read_csv(OUT/'predicted_life.csv')
    fig,axes=plt.subplots(1,3,figsize=(11,3.4),sharey=True)
    for ax,r in zip(axes,[1,3,5]):
        for (cap,cell),g in obs[(obs.temp==25)&(obs.rate==r)].groupby(['cap','cell']):
            ax.plot(g.baseline_total_EFC,g.retention_initial*100,color=COLORS[cap],marker='.',lw=1,alpha=.85)
        ax.axhline(80,color='gray',ls='--',lw=.8);ax.set_title(LABEL[r]);ax.set_xlabel('Equivalent full cycles');ax.grid(alpha=.15)
    axes[0].set_ylabel('Measured capacity / initial (%)')
    axes[0].plot([],[],color=COLORS[90],label='~90% cap');axes[0].plot([],[],color=COLORS[100],label='100% cap');axes[0].legend(fontsize=8)
    fig.suptitle('Observed KIT capacity trajectories at 25°C (three cells per arm)',fontsize=12);fig.tight_layout();finish(fig,'observed_25C.png')
    fig,axes=plt.subplots(1,4,figsize=(11,3.5),sharey=False)
    for ax,t in zip(axes,[0,10,25,40]):
        for cap,off in [(100,-.07),(90,.07)]:
            g=pred[(pred.temp==t)&(pred.cap==cap)].sort_values('rate');x=np.arange(3)+off
            ax.errorbar(x,g.median_EFC,yerr=[g.median_EFC-g.ci_lo,g.ci_hi-g.median_EFC],fmt='o',capsize=3,color=COLORS[cap],label=f'{cap}%')
        ax.set_xticks(range(3),['1/3','1','5/3']);ax.set_xlabel('Charging rate (C)');ax.set_title(f'{t}°C');ax.grid(axis='y',alpha=.15)
    axes[0].set_ylabel('Model-estimated median life (EFC)');axes[0].legend(fontsize=8)
    fig.suptitle('Weibull AFT predictions; nominal 95% cell-bootstrap intervals',fontsize=12);fig.tight_layout();finish(fig,'modeled_life_by_temperature.png')
    fig,ax=plt.subplots(figsize=(8,4.5))
    df=pd.read_csv(OUT/'endpoints_primary.csv');d=df[df.temp==25].sort_values(['rate','cap','replicate'])
    for y,row in enumerate(d.itertuples()):
        if np.isfinite(row.upper_EFC):ax.plot([row.lower_EFC,row.upper_EFC],[y,y],color=COLORS[row.cap],lw=2)
        else:ax.plot(row.lower_EFC,y,marker='>',color=COLORS[row.cap])
    ax.set_yticks(range(len(d)),[f'{r.cell} {LABEL[r.rate]} {r.cap}%' for r in d.itertuples()],fontsize=7)
    ax.set_xlabel('Derived 80%-capacity crossing interval (EFC)');ax.set_title('Observed lifetime intervals at 25°C; > denotes right-censoring');ax.grid(axis='x',alpha=.15)
    fig.tight_layout();finish(fig,'observed_intervals_25C.png')
    from .model import design
    import json
    model=json.loads((OUT/'model.json').read_text());theta=np.array(model['theta']);shape=np.exp(theta[-1]);g=pred[pred.temp==25]
    G,_,_=design(g);scales=1000*np.exp(G@theta[:-1]);xx=np.linspace(0,4000,400)
    fig,ax=plt.subplots(figsize=(8,4.3))
    for row,scale in zip(g.itertuples(),scales):
        ax.plot(xx,np.exp(-(xx/scale)**shape),label=f'{LABEL[row.rate]} {row.cap}%',color=COLORS[row.cap],ls={1:':',3:'--',5:'-'}[row.rate])
    ax.set(xlabel='Equivalent full cycles',ylabel='Model-estimated survival probability',title='Weibull AFT survival at 25°C; extrapolation beyond observations')
    ax.legend(ncol=2,fontsize=8);ax.grid(alpha=.15);finish(fig,'modeled_survival_25C.png')

def financial_figures():
    d=pd.read_csv(OUT/'financial_strategies.csv')
    fig,ax=plt.subplots(figsize=(9,4))
    x=np.arange(len(d))
    ax.errorbar(x,d.spend_USD,yerr=[d.spend_USD-d.spend_ci_lo,d.spend_ci_hi-d.spend_USD],fmt='o',capsize=4,color='#255a8f')
    ax.set_xticks(x,[f'{LABEL[r.rate]}\n{r.cap}%' for r in d.itertuples()])
    ax.set(ylabel='Estimated replacement spending (USD)',xlabel='Charging rate and cap',title='Conditional three-year phone scenario at 25°C')
    ax.grid(axis='y',alpha=.2)
    fig.text(.5,-.04,'Dated $99 repair cost; 0.7 EFC/day assumed. Bars: nominal 95% Weibull cell-bootstrap CI.',ha='center',fontsize=9)
    fig.tight_layout();finish(fig,'conditional_costs.png')
    a=pd.read_csv(OUT/'annual_cost.csv')
    fig,ax=plt.subplots(figsize=(8,4))
    for cap in [100,90]:
        g=a[(a.rate==5)&(a.cap==cap)]
        ax.errorbar(g.year,g.spend_USD,yerr=[g.spend_USD-g.ci_lo,g.ci_hi-g.spend_USD],fmt='o-',capsize=4,color=COLORS[cap],label=f'5/3C, {cap}%')
    ax.set(xlabel='Year of assumed ownership',ylabel='Estimated replacement spending (USD)',title='Primary intervention: 90% cap at unchanged charging rate')
    ax.set_xticks([1,2,3]);ax.legend();ax.grid(alpha=.15);fig.tight_layout();finish(fig,'conditional_annual_spend.png')

if __name__=='__main__':
    main()
    if (OUT/'financial_strategies.csv').exists():financial_figures()
