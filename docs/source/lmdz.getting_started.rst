Getting started
===============


.. toctree::
   :maxdepth: 2

In this tutorial, we will deploy a Morays experiment for NEMO that is stored in the Morays collection. Objective of the experiment is to couple the ML model proposed by `Guillaumin and Zanna, 2021 <https://doi.org/10.1029/2021MS002534>`_ (GZ21) with the `DINO <https://github.com/vopikamm/DINO>`_ config.


Prerequisites to the tutorial:
    - Operating NEMO environment (see `NEMO doc <https://sites.nemo-ocean.io/user-guide/install.html>`_ for help)
    - Operating Python environment
or:
    - Installed Apptainer
    - Morays container (see below)

**Apptainer on Linux**

.. code-block :: bash
    
    # For Ubuntu
    sudo apt update && sudo apt install -y software-properties-common
    sudo add-apt-repository -y ppa:apptainer/ppa
    sudo apt update && sudo apt install -y apptainer
    
    # For amd64 Debian
    sudo apt update
    sudo apt install -y wget
    cd /tmp
    wget https://github.com/apptainer/apptainer/releases/download/v1.4.3/apptainer_1.4.3_amd64.deb
    sudo apt install -y ./apptainer_1.4.3_amd64.deb
    
.. warning :: For other Linux distributions, please refer to this `guide <https://github.com/apptainer/apptainer/blob/main/INSTALL.md>`_.
 

**Apptainer on macOS**

.. code-block:: bash
    
    # Apptainer is available on macOS via LIMA (LInux virtual MAchines)
    brew install qemu lima  # Install with brew
    port install qemu lima  # Install with macports

    # Create Linux VM with Apptainer
    limactl start template://apptainer
    limactl shell apptainer
    # IMPORTANT: type 'cd' to go in VM home, 'pwd' should return '/home/<your_name>.linux'
    cd
    
    # NB: copy files from VM to host
    limactl cp apptainer:/path/to/file  /host/destination


**Run Morays container**

.. code-block:: bash

    # Get your hardware architecture
    uname -m
    #  aarch64 --> arm64
    #  x86_64  --> amd64
    ARCH=arm64

    # Download image
    wget https://github.com/morays-community/morays-doc/releases/download/containers/morays_env_${ARCH}.sif

    # Run container: should print " >>>> Welcome in Morays environment ! <<<< "
    apptainer run --writable-tmpfs --bind $(pwd):/home/jdoe/to_host morays_env_${ARCH}.sif


Introduction
------------

DINO stands for `diabatic Neverworld2 <https://gmd.copernicus.org/articles/15/6567/2022/>`_ . It's an idealized configuration that aims to capture essential pole-to-pole ocean dynamics for mesoscale turbulence study.

The work of GZ21 takes place in the context of parameterizing the ocean subgrid momentum forcing with a ML model. The goal is to predict the mean and standard deviation of a Gaussian probability distribution at each grid cell. Those are intended to be used for a stochastic prediction of the subgrid forcing. We wish to use the GZ21 parameterization to enhance the solution of a DINO simulation. The model relies on a CNN that takes macroscale surface velocities as inputs and returns mean and deviation as outputs.

Here is the difficulty: the CNN model is written with native Python libraries while NEMO is written in Fortran. Thus, an interface is required to make both to coexist and exchange data. Since NEMO has an OASIS3-MCT interface, we can use the Eophis library to couple an external Python script that will contain the GZ21 model.


.. image:: images/NEMO_GZ21_XIOS.png
    :width: 600px
    :align: center


The experiment will execute the following steps:
    - NEMO is modeling the DINO ocean circulation
    - It sends the surface velocity fields towards the Python script every time step
    - GZ21 model in Python script predicts the mean and standard deviation and the forcing fields
    - Results are sent back to NEMO and written in an output file with XIOS
    - Forcing fields are finally used to parameterize the subgrid momentum



1. Morays environment
---------------------

Every Morays experiments with NEMO require a couple of shared libraries. We quickly summarize the steps to install them.

.. note::

    If you are running Morays container, you can skip this part until section 2.
  
  

Compile OASIS3-MCT_v5.0
~~~~~~~~~~~~~~~~~~~~~~~

OASIS3-MCT is the coupling library on which both NEMO and Eophis rely to perform field exchanges. OASIS3-MCT_v5.0 is the minimal required version and must be dynamically compiled. See `OASIS3-MCT documentation <https://oasis.cerfacs.fr/en/documentation/>`_ for more details.

.. code-block:: bash

    # Clone OASIS3-MCT_v5.0
    cd ~/
    git clone https://gitlab.com/cerfacs/oasis3-mct.git
    cd ~/oasis3-mct
    git checkout OASIS3-MCT_5.0
    cd util/make_dir
    
Edit your own ``make.<YOUR_ARCH>`` file. Pay attention to the following important variables:

.. code-block:: makefile

     # Dynamic flags
     DYNOPT = -fPIC
     LDDYNOPT = -shared
     # inc and lib dir
     NETCDF_INCLUDE = /PATH/TO/NETCDF/include
     NETCDF_LIBRARY = -L/PATH/TO/NETCDF/lib -lnetcdf -lnetcdff
     MPI_INCLUDE = /PATH/TO/MPI/include
     MPILIB = -L/PATH/TO/MPI/lib -lmpi
     # Compilers and linker
     F90 = # mpifort -I$(MPI_INCLUDE) , ftn , mpiifort ...
     CC =  # mpicc , cc , mpiicc ...
     LD = $(F90) $(MPILIB)
     # Compilation flags - adapt with your compilers
     FCBASEFLAGS = -O2 ...
     CCBASEFLAGD = -O2 ...


.. code-block:: bash
    
    # Link your architecture file for compilation
    echo "include ~/oasis3-mct/util/make_dir/make.<YOUR_ARCH>"  >  make.inc
     
    # Compile dynamic libraries
    make -f TopMakefileOasis3 pyoasis

    # Libraries should be there
    ls ~/oasis3-mct/BLD/lib/
    libmct.so   libmpeu.so   liboasis.cbind.so   libpsmile.MPI1.so   libscrip.so

    
Activate OASIS3-MCT Python API. The best is to put this command in your ``bash_profile``:

.. code-block :: bash

    source ~/oasis3-mct/BLD/python/init.sh
    


Compile XIOS with OASIS3-MCT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

XIOS is used by NEMO to write results. It must be compiled with the abovementioned OASIS3-MCT libraries. See `XIOS documentation <https://forge.ipsl.jussieu.fr/ioserver/wiki/documentation>`_ for more details about compilation of XIOS with OASIS3-MCT.


.. code-block:: bash

    # Clone XIOS
    cd ~/
    git clone -b XIOS2 https://gitlab.in2p3.fr/ipsl/projets/xios-projects/xios.git XIOS_OASIS
    cd ~/XIOS_OASIS/

Edit your ``arch-<YOUR_MACHINE>.path`` file to include the OASIS3-MCT libraries directories and bindings:

.. code-block:: bash

    # edit arch files
    vi archs/arch-<YOUR_MACHINE>.path
        # ...
        OASIS_INCDIR="-I~/oasis3-mct/BLD/include/ -I~/oasis3-mct/BLD/build-shared/lib/cbindings/"
        OASIS_LIBDIR="-L~/oasis3-mct/BLD/lib"
        OASIS_LIB="-loasis.cbind -lpsmile.MPI1 -lscrip -lmct -lmpeu"

.. code-block:: bash

    # Compile
    ./make_xios --full --prod --arch <YOUR_MACHINE> --use_oasis oasis3_mct

    # library should be here
    ls lib/
    libxios.a



2. Experiment environment
-------------------------

Now that we have set up the common environment for all Morays experiments, we need to install the dependencies related to the specific experiment of interest. Let's find it in the `Morays repositories <https://github.com/orgs/morays-community/repositories>`_. Those are named with a simple convention: ``<OCEAN_CODE>-<EXPERIMENT>``. The corresponding repository for the tutorial is then ``NEMO-DINO_Subgrid_Momentum``:

.. code-block:: bash

    mkdir -p ~/to_host
    cd ~/to_host
    git clone https://github.com/morays-community/NEMO-DINO_Subgrid_Momentum.git

The repository contains a ``README`` with informations about experiment context and motivations.

The other informations listed in ``README`` are the software requirements:
    - **Compilation:** ocean code version to compile and with which potential additionnal material
    - **Python:** Eophis version to install and potential additional Python material
    - **Run:** submission tools to manage the experiment execution
    - **Post-Process:** post-processing libraries and plotting tools

In accordance with the ``README`` content, we must install *NEMO_v4.2.1*, *Eophis_v1.1.0* and GZ21 package. Other tools and scripts are already contained in the repository.

.. code-block:: bash

    # Clone NEMO_v4.2.1
    cd ~/to_host
    git clone --branch 4.2.1 https://forge.nemo-ocean.eu/nemo/nemo.git nemo_v4.2.1
    
    # Clone and install Eophis_v1.1.0
    cd ~/to_host
    git clone --branch v1.1.0 https://github.com/meom-group/eophis eophis_v1.1.0
    cd eophis_v1.1.0
    pip install .
    
    # README instructions for GZ21 package
    cd ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/INFERENCES/gz21_ocean_momentum
    pip install -e .
    
    
We will now browse the directories of the ``DINO_Subgrid_Momentum.GZ21`` experiment to deploy the test case.

.. code-block:: bash

    ls ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/
    CONFIG  INFERENCES  POST-PROCESS  RES  RUN




3. CONFIG - NEMO case
---------------------

This directory contains the material to compile NEMO. Since the **Compilation** section of the ``README`` did not mention any specific tool for the compilation, we will follow the standard NEMO `configuration structure <https://sites.nemo-ocean.io/user-guide/install.html#preparing-an-experiment>`_. We first need to create a custom test case:

.. code-block:: bash

    # Create NEMO test case
    echo "DINO_GZ21 OCE" >> ~/to_host/nemo_v4.2.1/tests/work_cfgs.txt
    mkdir -p ~/to_host/nemo_v4.2.1/tests/DINO_GZ21/EXPREF
    mkdir -p ~/to_host/nemo_v4.2.1/tests/DINO_GZ21/MY_SRC


A list of active CPP keys is given as material in the CONFIG directory:
    
.. code-block:: bash

    # Copy CPP keys
    cp ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/CONFIG/cpp_DINO_GZ21.fcm   ~/to_host/nemo_v4.2.1/tests/DINO_GZ21/



An architecture file is compulsory to compile NEMO. A template for the experiment is also given in CONFIG. Depending on your hardware environment, it might not be not suitable. Feel free to copy and edit it in accordance with your machine. Alternatively, the automatic generation may be used:

.. code-block:: bash

    cd ~/to_host/nemo_v4.2.1/arch
    ./build_arch-auto.sh
    cp arch-auto.fcm arch-X64_DINO_GZ21.fcm
    

Regardless of the method you chose, be sure to have your architecture file copied in ``~/to_host/nemo_v4.2.1/arch/`` and to have the OASIS3-MCT and XIOS paths corresponding to those compiled with OASIS3-MCT_v5.0 libraries.



Morays patch
~~~~~~~~~~~~

``README`` mentionned that the  NEMO sources must be patched with Morays sources. Those are the minimal NEMO sources modifications to set up a Morays experiment. They enable flexible external communication through the OASIS3-MCT module. We can obtain them by cloning this repository:

.. code-block:: bash

    cd ~/to_host
    git clone https://github.com/morays-community/Patches-NEMO.git


We transfer the Morays sources for NEMO_v4.2.1 to our custom test case. Only the sources of the OCE module are needed:

.. code-block:: bash

    # Copy Morays sources
    cp ~/to_host/Patches-NEMO/NEMO_v4.2.1/OCE/*   ~/to_host/nemo_v4.2.1/tests/DINO_GZ21/MY_SRC/




Experiment patch
~~~~~~~~~~~~~~~~

``README`` also specified to patch NEMO with the experiment specific sources. Morays sources do not configure the external communication module in accordance with ``DINO_Subgrid_Momentum.GZ21`` but experiment sources do. They also contain the code to write and use the outsourced forcing fields. They are also stored in CONFIG:

.. code-block:: bash

    # Copy experiment sources
    cp ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/CONFIG/my_src/*   ~/to_host/nemo_v4.2.1/tests/DINO_GZ21/MY_SRC/




4. RUN - NEMO settings
----------------------

This directory contains all the production material, such as XIOS configuration files and NEMO namelists. We need them obviously:

.. code-block:: bash
    
    # Copy xml files and namelists
    cp ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/RUN/NAMELISTS/*   ~/to_host/nemo_v4.2.1/tests/DINO_GZ21/EXPREF/
    cp ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/RUN/XML/*   ~/to_host/nemo_v4.2.1/tests/DINO_GZ21/EXPREF/


We have everything we need to compile NEMO:

.. code-block:: bash

    cd ~/to_host/nemo_v4.2.1
    ./makenemo -m "X64_DINO_GZ21_GCC" -a DINO_GZ21 -n "MY_DINO_GZ21" -j 8


In RUN directory is also contained the execution material for the experiment. Except ``job.ksh``, no particular tool to manage the run is specified in ``README``:

.. code-block:: bash
    
    cp ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/RUN/job.ksh   ~/to_host/nemo_v4.2.1/tests/MY_DINO_GZ21/EXP00/


Script ``job.ksh`` assumes that NEMO will run on a HPC system via a SBATCH scheduler. Adapt script content or remove SBATCH header if necessary.




5. INFERENCES - Python material
-------------------------------

This directory contains the Python scripts for hybrid modeling. It also includes additional packages for the Python model (if necessary). Here, GZ21 model sources and its dependencies are contained in a git submodule ``gz21_ocean_momentum``. The model is imported and used in accordance with the experiment objectives in ``ml_models.py``. Finally, ``main.py`` contains the Eophis instructions to couple ``ml_models.py`` with NEMO.  Let's copy them to the test case:

.. code-block:: bash

    cp ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/INFERENCES/*.py   ~/to_host/nemo_v4.2.1/tests/MY_DINO_GZ21/EXP00/
    
    
Model weights are in the folder of the same name. For this tutorial, we will use those:
    
.. code-block:: bash

    cp ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/INFERENCES/weights/gz21_huggingface/low-resolution/files/trained_model.pth   ~/to_host/nemo_v4.2.1/tests/MY_DINO_GZ21/EXP00/


We already installed GZ21 package in section **2. Experiment environment**. It may be tested by running ``ml_models.py`` as a standalone script:

.. code-block:: bash

    cd ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/INFERENCES/
    python3 ./ml_models.py
    # Should print "Test successful"
        
    

6. Running the experiment
-------------------------

Everything is ready to execute the hybrid experiment. Submit the run with ``job.ksh`` in accordance with your computing environment. If you are not running NEMO on a HPC system, execute commands below inside the experiment directory:

.. code-block:: bash

    cd ~/to_host/nemo_v4.2.1/tests/MY_DINO_GZ21/EXP00/

    # clean working directory
    touch namcouple
    rm namcouple*

    # execute eophis in preproduction mode to generate namcouple
    python3 ./main.py --exec preprod
    
    # save eophis preproduction logs
    mv eophis.out eophis_preprod.out
    mv eophis.err eophis_preprod.err
    
    # run coupled NEMO-Python
    mpirun -np 1 ./nemo : -np 1 python3 ./main.py --exec prod


If run is going well, Eophis log should contain messages like these:

.. code-block:: bash

    tail eophis.out
    Iteration 2: 2700s -- 0:45:00
       Treating u, v received through tunnel TO_NEMO_FIELDS
       Sending back u_f, v_f through tunnel TO_NEMO_FIELDS
    Iteration 3: 5400s -- 1:30:00
       Treating u, v received through tunnel TO_NEMO_FIELDS
       Sending back u_f, v_f through tunnel TO_NEMO_FIELDS
    Iteration 4: 8100s -- 2:15:00
       Treating u, v received through tunnel TO_NEMO_FIELDS
       Sending back u_f, v_f through tunnel TO_NEMO_FIELDS
    Iteration 5: 10800s -- 3:00:00
       Treating u, v received through tunnel TO_NEMO_FIELDS
       Sending back u_f, v_f through tunnel TO_NEMO_FIELDS


This means that the exchanges are well performed. Check out also that output files ``NEVERWORLD.1d_gridUsurf.nc`` and ``NEVERWORLD.1d_gridVsurf.nc`` have been created. They contain the subgrid forcing fields computed by GZ21 model.


.. note:: If your computing environment is able to give you an access to a CUDA-compatible GPU, ``ml_models.py`` will automatically execute the prediction on the GPU while NEMO and Eophis will be executed on CPUs.



7. POST-PROCESS and RES
-----------------------

POST-PROCESS directory contains material and/or scripts to compute and plot results. The latter are stored in the RES directory to be available for consultation. In this tutorial, only a simple Python script ``plots_res.py`` should be executed to plot figures. Required dependencies are also given.


.. code-block:: bash

    # install dependencies, if necessary
    cd ~/to_host/NEMO-DINO_Subgrid_Momentum/DINO_Subgrid_Momentum.GZ21/POST-PROCESS/
    pip install -r requirements.txt
    cp plots_res.py  ~/to_host/nemo_v4.2.1/tests/MY_DINO_GZ21/EXP00/
    
    # Plot, you might need to exit container (and lima VM) to visualize figures
    cd ~/to_host/nemo_v4.2.1/tests/MY_DINO_GZ21/EXP00/
    python3 ./plots_res.py


If everything went good, we should have similar figures than those stored in RES. Same plots for a standard DINO config without GZ21 model are also stored for comparison.

As described in the introduction, NEMO only sends the surface velocities towards GZ21 model. However, the implementation allows to send the whole 3D grid if you wish. Adapt the value of ``nn_lvl`` in NEMO namelist.




Going further
-------------

From now on, you have an usable deployed Morays experiment for NEMO. Do not hesitate to check out and deploy other test cases to get inspired.

Here are the locations where you can play with:
    - global coupling settings: ``main.py``
    - Fortran interface: functions ``send_to_python()`` , ``receive_from_python()`` from ``pycpl.F90``
    - fields sent by NEMO: routine ``inputs_gz21()`` in ``pyfld.f90``
    - computation of forcing fields and ML model configuration: ``ml_models.py``
    - use of received forcing fields: routine ``update_from_gz21()`` in ``pyfld.f90``
    - calling of abovementionned routines within NEMO: ``stpmlf.F90``
    - NEMO settings: namelists and xml files
 
Next sections provide more details on how to configure the NEMO external communication module, and to create a Morays experiment for NEMO from scratch.
