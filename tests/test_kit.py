"""Explicit SYNTHETIC fixtures for numerical validation; never empirical inputs."""
import unittest
import numpy as np
from scipy.optimize import check_grad
from scipy import stats
from scripts.kit.model import fit,objective

class LikelihoodTests(unittest.TestCase):
    def test_gradient(self):
        X=np.array([[1.,0],[1,1],[1,0],[1,1]])
        lo=np.array([0.,200,700,1000]);up=np.array([100.,500,700,np.inf])
        for family in ['weibull','lognormal']:
            t=np.array([0.,.2,.2])
            error=check_grad(lambda p:objective(p,X,lo,up,family)[0],lambda p:objective(p,X,lo,up,family)[1],t)
            self.assertLess(error,1e-4)
    def test_synthetic_recovery_and_scipy(self):
        rng=np.random.default_rng(1234)
        life=800*rng.weibull(2.4,5000)
        lo=np.floor(life/50)*50;up=lo+50
        cens=life>1100;lo[cens]=1100;up[cens]=np.inf
        result=fit(np.ones((len(life),1)),lo,up)
        self.assertTrue(result['success'])
        self.assertAlmostEqual(np.exp(result['theta'][0])*1000,800,delta=35)
        self.assertAlmostEqual(np.exp(result['theta'][1]),2.4,delta=.2)
        shape,_,scale=stats.weibull_min.fit(stats.CensoredData.interval_censored(lo,up),floc=0)
        self.assertAlmostEqual(np.exp(result['theta'][1]),shape,delta=.002)
        self.assertAlmostEqual(np.exp(result['theta'][0])*1000,scale,delta=.2)

if __name__=='__main__':unittest.main()
