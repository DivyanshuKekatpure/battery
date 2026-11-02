"""Interval/right-censored AFT likelihood. All predictions are MODEL ESTIMATES."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import log_ndtr

SCALE=1000.0

def design(df, omit=None):
    main={'rate':{'rate_1third':(df.rate.to_numpy()==1).astype(float),'rate_5third':(df.rate.to_numpy()==5).astype(float)},
          'cap':{'cap90':(df.cap.to_numpy()==90).astype(float)},
          'temp':{f'temp{t}':(df.temp.to_numpy()==t).astype(float) for t in (0,10,40)}}
    cols={'Intercept':np.ones(len(df))}; groups={'Intercept':['Intercept']}
    for k,d in main.items():cols.update(d); groups[k]=list(d)
    for a,b in [('rate','cap'),('rate','temp'),('cap','temp')]:
        key=a+':'+b; groups[key]=[]
        for n,v in main[a].items():
            for m,w in main[b].items():cols[n+':'+m]=v*w;groups[key].append(n+':'+m)
    for n in groups.get(omit,[]):cols.pop(n)
    return np.column_stack(list(cols.values())),list(cols),groups

def logdiff(a,b):
    # a >= b; log(exp(a)-exp(b)) without catastrophic cancellation.
    return a+np.log(-np.expm1(np.minimum(b-a,-1e-15)))

def contributions(theta,X,lower,upper,family='weibull'):
    mu=X@theta[:-1]; s=np.exp(theta[-1])
    lo=np.maximum(np.asarray(lower)/SCALE,0); up=np.asarray(upper)/SCALE
    right=np.isinf(up); exact=(lo==up)&~right; interval=~right&~exact
    ll=np.zeros(len(lo)); gm=np.zeros(len(lo)); gs=np.zeros(len(lo))
    with np.errstate(over='ignore',invalid='ignore',divide='ignore',under='ignore'):
        if family=='weibull':
            loglo=np.log(np.maximum(lo,1e-300)); zl=s*(loglo-mu)
            a=np.where(lo>0,np.exp(np.clip(zl,-700,80)),0)
            ll[right]=-a[right];gm[right]=s*a[right];gs[right]=-a[right]*zl[right]
            if exact.any():
                z=zl[exact];aa=a[exact]
                ll[exact]=theta[-1]-loglo[exact]+z-aa-np.log(SCALE)
                gm[exact]=s*(aa-1);gs[exact]=1+z*(1-aa)
            if interval.any():
                idx=interval; zu=s*(np.log(up[idx])-mu[idx]); b=np.exp(np.clip(zu,-700,80))
                aa=a[idx]; d=np.maximum(b-aa,1e-300)
                ll[idx]=-aa+np.log(-np.expm1(-d))
                inv=np.where(d<700,1/np.expm1(np.minimum(d,700)),0)
                gm[idx]=s*(aa-d*inv)
                az=np.where(lo[idx]>0,aa*zl[idx],0)
                gs[idx]=-az+(b*zu-az)*inv
        else:
            loglo=np.log(np.maximum(lo,1e-300)); zl=(loglo-mu)/s
            zup=(np.log(np.where(np.isfinite(up),np.maximum(up,1e-300),1))-mu)/s
            logphi=lambda z:-0.5*z*z-0.5*np.log(2*np.pi)
            lsf=log_ndtr(-zl)
            ll[right]=lsf[right]
            ratio=np.exp(logphi(zl[right])-lsf[right])
            gm[right]=ratio/s;gs[right]=zl[right]*ratio
            if exact.any():
                z=zl[exact];ll[exact]=logphi(z)-theta[-1]-loglo[exact]-np.log(SCALE)
                gm[exact]=z/s;gs[exact]=z*z-1
            if interval.any():
                idx=interval; z1=zl[idx];z2=zup[idx]
                # Use CDF on the negative tail and survival on the positive tail.
                lp=np.where(z1<0,logdiff(log_ndtr(z2),log_ndtr(z1)),logdiff(log_ndtr(-z1),log_ndtr(-z2)))
                r1=np.exp(logphi(z1)-lp);r2=np.exp(logphi(z2)-lp)
                ll[idx]=lp;gm[idx]=(r1-r2)/s;gs[idx]=z1*r1-z2*r2
    grad=np.column_stack([gm[:,None]*X,gs])
    return ll,grad

def objective(theta,X,lower,upper,family='weibull'):
    ll,g=contributions(theta,X,lower,upper,family)
    if not np.all(np.isfinite(ll)) or not np.all(np.isfinite(g)):return 1e100,np.zeros_like(theta)
    return -ll.sum(),-g.sum(axis=0)

def fit(X,lower,upper,family='weibull',start=None):
    # Initial values are numerical starting points, not substituted failure data.
    bounds=[(-30,30)]*X.shape[1]+[(-4,4)]
    initial=np.zeros(X.shape[1]+1);initial[0]=np.log(np.median(np.where(np.isfinite(upper),upper,np.maximum(lower,1)))/SCALE)
    initial[-1]=np.log(2) if family=='weibull' else np.log(.6)
    starts=[start if start is not None else initial,initial]
    best=None
    for attempt,st in enumerate(starts):
        res=minimize(objective,np.asarray(st),args=(X,lower,upper,family),jac=True,method='L-BFGS-B',bounds=bounds,
                     options={'maxiter':1800,'ftol':1e-12,'gtol':1e-7,'maxls':40})
        norm=float(np.max(np.abs(res.jac)))
        valid=np.isfinite(res.fun) and norm<.01 and np.max(np.abs(res.x[:-1]))<29.99 and abs(res.x[-1])<3.99
        info={'theta':res.x,'nll':float(res.fun),'gradient_max':norm,'success':bool(valid),'attempts':attempt+1,'message':str(res.message)}
        if best is None or info['nll']<best['nll']:best=info
        if valid:return info
    return best

def median(theta,X,family='weibull'):
    mu=X@theta[:-1]
    return SCALE*np.exp(mu)*(np.log(2)**(1/np.exp(theta[-1])) if family=='weibull' else 1)
