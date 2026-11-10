# eophis API
import eophis
from eophis import Freqs, Domains
# other modules
import argparse
import os
from pathlib import Path

def read_def(filename):
    path = Path(filename)
    if not path.is_file():
        path = Path("~/to_host/LMDZ6_PY/modipsl/config/BENCH32x32x39").expanduser() / filename

    with open(path) as f:
        return dict(line.strip().split("=", 1) for line in f
                    if "=" in line and not line.lstrip().startswith("#"))


def earth_info():
    """
    Return arguments for a Tunnel object that will configure coupling. Return run info for namelist
    """

    # Step 1: define exchanges
    tunnel_config = list()
    tunnel_config.append( { 'label' : 'TO_NEMO', \
                            'grids' : {}, \
                            'exchs' : [ {} ] }
                        )

    # Step 2: tunnel registration
    # ...


    # Step 3: get info from LMDZ namelists
    run = read_def("run.def")
    gcm = read_def("gcm.def")
    
    nday = int(run["nday"])
    day_step = int(gcm["day_step"])
    iphysiq = int(gcm["iphysiq"])

    step = # ...
    ite_end = # ... 
    ite_0 = # ...

    return to_lmdz, step, ite_end, ite_0


def preproduction():
    eophis.info('========= EOPHIS: Pre-Production =========')
    eophis.info('  Aim: write coupling namelist\n')

    # earth info
    to_lmdz, step, it_end, it_0 = earth_info()
    
    # Step 4: write OASIS namelist
    # ...

def production():
    eophis.info('========= EOPHIS: Production =========')
    eophis.info('  Aim: execute coupled simulation\n')

    #  Earth Coupling
    # ++++++++++++++++
    to_lmdz, step, it_end, it_0 = earth_info()
    niter = it_end - it_0 + 1
    total_time = niter * step

    # Step 5: deploy OAISS interface
    # ...

    #  Step 6: import DJ08
    # ++++++++++++++++++++
    # ...

    #  Step 7: Time synchronization
    # +++++++++++++++++++++++++++++
    @eophis.all_in_all_out( ... )
    def loop_core(**inputs):

        # step 8: connect exchanged fields with DJ08
        outputs = {}
        outputs['an_output'] = a_model( inputs['an_input'] )
        return outputs

    #  Run
    # +++++
    eophis.starter(loop_core)
    
# ============================ #
if __name__=='__main__':
    """ Switch between preproduction and production mode. Call different instructions depending on the selected mode. """

    parser = argparse.ArgumentParser()
    parser.add_argument('--exec', dest='exec', type=str, default='prod', help='Execution type: preprod or prod')
    args = parser.parse_args()

    eophis.set_mode(args.exec)
    
    if args.exec == 'preprod':
        preproduction()
    elif args.exec == 'prod':
        production()
    else:
        eophis.abort(f'Unknown execution mode {args.exec}, use "preprod" or "prod"')
