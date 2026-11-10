"""
Contains User Inference/Analytic Models or Functions.

A model must fit the following requisites and structure :
-------------------------------------------------------
    1. must be a callable function that takes N numpy arrays as inputs
    2. /!\ returns N None for the N awaited outputs if at least one of the input is None /!\
    3. inputs may be freely formatted and transformed into what you want BUT...
    4. ...outputs must be formatted as numpy array for sending back
"""
import metpy.calc as mpcalc
from metpy.units import units
import numpy as np


# ++++++++++++++++++++++++++++ #
#            Utils             #
# ++++++++++++++++++++++++++++ #
def Is_None(*inputs):
    """ Test presence of at least one None in inputs """
    return any(item is None for item in inputs)


def sub_wet_temp(p, T, q):
    """Compute wet-bulb potential temperature theta_w from pressure, temperature
       and specific humidity using Davies-Jones, 2008 formulation.

    Parameters
    ----------
    p : ndarray (lat,lon,lev)
        Mid-layer pressure [Pa]
    T : ndarray (lat,lon,lev)
        Temperature [K]
    q : ndarray (lat,lon,lev)
        Water-vapour specific humidity [kg/kg].

    Returns
    -------
    theta_w : ndarray
        Wet-bulb potential temperature [K], same shape as inputs 

    """
    # -- Attach native units here
    p_q = units.Quantity(np.asarray(p), 'Pa')
    T_q = units.Quantity(np.asarray(T), 'K')
    # clip q to avoid log(0) -> -inf dewpoint on dry upper levels
    q_q = units.Quantity(np.maximum(np.asarray(q), 1e-12), 'kg/kg')

    # -- dewpoint from specific humidity (WMO8 eq. 4.A.6)
    # [...]

    # -- theta_e (Bolton 1980) then theta_w (Davies-Jones 2008 polynomial)
    # [...]

    return np.asarray(theta_w.m_as('K'))



if __name__ == '__main__' :

    # Testing inputs
    # --------------
    shape = (10,12,10)
    rng = np.random.default_rng(42) 

    p = rng.uniform(3.0e4, 1.013e5, shape)
    T = rng.uniform(200.0, 310.0, shape) 
    es = 611.2*np.exp(17.67*(T-273.15)/(T-29.65))
    RH = rng.uniform(0.05, 1.0, shape)
    q = RH*0.622*es/(p - (1-0.622)*es) 

    print(f'Inputs -- <p>: {p.mean():.2f}, <T>: {T.mean():.2f}, <Spec.hum>: {q.mean():.2f}')

    # Run model
    # ---------
    theta_w = sub_wet_temp(p,T,q)

    print(f'Res    -- <theta_w>: <theta_w>: {theta_w.mean():.2f}')
    print(f'Test successful')
