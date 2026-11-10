LMDZ for hybrid modelling
=========================

.. toctree::
   :maxdepth: 2

Let's recall that a hybrid LMDZ experiment is an atmospheric simulation that exchanges fields with an external Python script through OASIS3-MCT. The strategy is to deploy the OASIS3-MCT interface on the Python side and configure the global coupling environment with help of the Eophis library.

From this point, we consider that all the Python material is already well configured. See `Eophis documentation <https://eophis.readthedocs.io/en/latest/>`_ or this `tutorial <https://eophis.readthedocs.io/en/latest/tutorial.html>`_ for more details. What remains now is to configure the OASIS3-MCT interface on LMDZ side in accordance with Eophis. This is described in this section.


.. important:: This documentation is valid for LMDZ6.

.. note ::
    - **Developer guide** describes how to build a LMDZ6 communication module from scratch.

    - **User guide** describes a provided ready-to-use communication module -- **recommended**.



Developer guide
---------------

We describe here how to use the OASIS3-MCT interface within LMDZ6 to build a whole new module dedicated to external communication, here Python.

Modified OASIS3-MCT interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Current LMDZ releases do include an OASIS3-MCT module. However, it is restricted for coupling the surface boundary condition only. Modifications of the LMDZ6 sources are required to make it usable for other coupling purposes.


TRACCS-COMPACT provides `patches <https://github.com/TRACCS-COMPACT/Hybrid_Python-LMDZ/tree/main/LMDZ_Patches>`_ with the abovementionned modifications of the LMDZ code. More details about modifications are available `here <https://github.com/TRACCS-COMPACT/Hybrid_Python-LMDZ/blob/main/LMDZ_Patches/README.md>`_. As a user, you just need to copy them in the ``libf`` directory of LMDZ6.


Coupling properties of the fields to send and receive are stored in ``infosend`` and ``inforecv`` arrays, respectively. Flexibility of OASIS3-MCT in LMDZ6 relies on an extra dimension in ``infosend`` and ``inforecv`` to sort coupling fields properties between the modules that are using the OASIS3-MCT interface. To optimize memory, ``infosend`` and ``inforecv`` are variables that allow to create batches of coupling properties arrays. This way, it is possible to allocate different array sizes according to the modules. For example:

.. code-block :: Fortran

    infosend( mod_ID_1 )%fld( field_ID_1 )%field_property_1
    inforecv( mod_ID_1 )%fld( field_ID_2 )%field_property_2
    infosend( mod_ID_2 )%fld( field_ID_3 )%field_property_3


- First level dimension of ``infosend / inforecv`` corresponds to module IDs. It is automatically allocated.

- Second level dimension corresponds to IDs of coupled fields you wish the module to manage. This dimension is not allocated by default to save memory.


Register a new module
~~~~~~~~~~~~~~~~~~~~~

The first thing to do is to register your module ID in the ``oasis.F90`` global parameters:

.. code-block :: Fortran

    vi oasis3.F90
    ##   [...]
    33  INTEGER, PUBLIC, PARAMETER ::   midmax=2    ! Maximum number of identified modules
    34  INTEGER, PUBLIC, PARAMETER ::   midcpl=1    ! module ID #1 : ocean coupling
    35  INTEGER, PUBLIC, PARAMETER ::   midpycpl=2  ! module ID #2 : Eophis-equipped external python scripts

In this example, two modules are registered:
    1. A module used by LMDZ to couple with ocean
    2. A module used in the Eophis and OASIS3-MCT framework to couple Python script


Each time a module calls the OASIS3-MCT routines within LMDZ, the ID of the calling module must be passed as argument. Set an ID for your new module and create it. Then, import the OASIS3-MCT module:

.. code-block :: fortran

    USE oasis



Define coupled fields
~~~~~~~~~~~~~~~~~~~~~

As in many codes, your module must contain an initialization routine in which the coupling properties of the exchanged fields are defined. All initialization routines that use the OASIS3-MCT interface must be called during the LMDZ physics core initialization phase in ``phyetat0_mod.f90``, after ``cpl_def_domain()`` and before ``cpl_enddef()``. For example:


.. code-block:: fortran

    vi phyetat0_mod.d90
    ###  [...]
    761  ! --------- COUPLING SECTION --------
    762  ! Initialize coupling module
    763  IF ( type_ocean == 'couple' .OR. lk_pycpl ) CALL cpl_def_domain()
    764
    765  ! Initialize module ocean_cpl_mod for the case of coupled ocean
    766  IF ( type_ocean == 'couple' ) THEN
    767     CALL ocean_cpl_init(phys_tstep, longitude_deg, latitude_deg)
    768  ENDIF
    769
    770  ! Initialize python communication module
    771  IF ( lk_pycpl ) THEN
    772     CALL pyfld_alloc()
    773     CALL init_python_coupling()
    774  ENDIF
    775
    776  ! Finalize coupling definition
    777  IF ( type_ocean == 'couple' .OR. lk_pycpl ) CALL cpl_enddef()


Main purpose of the initialization routine is to fill ``infosend`` and ``inforecv`` second-level array. Second-level dimension must be first allocated in accordance with the number of coupling fields you wish your module to manage:

.. code-block :: Fortran

    ALLOCATE( inforecv(midpycpl)%fld( jpr_ext ) )
    ALLOCATE( infosend(midpycpl)%fld( jps_ext ) )

IDs of the coupled fields are locally defined by the considered module, proceed as you prefer.


Each identified field in the second-level array has a list of attributes to fill in accordance with the exchange you wish to realize (i.e. the exchanges defined in the Eophis script):

.. code-block:: fortran

    TYPE, PUBLIC ::   FLD_CPL            ! Type for coupling field information
        CHARACTER(len = 8) ::   name      ! Name of the coupling field
        LOGICAL            ::   action    ! To be exchanged or not
        INTEGER            ::   nid       ! Id of the field
        INTEGER            ::   nlvl      ! Number of level to exchange
    END TYPE FLD_CPL


Longitude and latitude sizes of the field do not need to be specified. It is automatically done during the initialization of the OASIS3-MCT environment. Exchange frequencies do not need to be specified either since they are managed by Eophis.

For instance, here are the properties for two variables ``u`` and ``u_f`` whose IDs are ``jps_su`` and ``jpr_uf``. They are defined in the communication module whose ID is ``midpycpl``.

.. code-block:: fortran

    ! default values for infosend and inforecv batches
    infosend(midpycpl)%fld(:)%action = .FALSE.  ;  infosend(midpycpl)%fld(:)%name = ''  ;  infosend(midpycpl)%fld(:)%nlvl = 1
    inforecv(midpycpl)%fld(:)%action = .FALSE.  ;  inforecv(midpycpl)%fld(:)%name = ''  ;  inforecv(midpycpl)%fld(:)%nlvl = 1
    !
    ! Properties for sending 2D U-velocity : "u" in Eophis
    infosend( midpycpl )%fld( jps_su )%name = 'E_OUT_0'
    infosend( midpycpl )%fld( jps_su )%action = .TRUE.
      
    ! Properties for receiving 2D forcing term on U-grid : "u_f" in Eophis
    inforecv( midpycpl )%fld( jpr_uf )%name = 'E_IN_0'
    inforecv( midpycpl )%fld( jpr_uf )%action = .TRUE.


The attribute ``name`` corresponds to the alias that OASIS3-MCT uses to perform the communications. ``u_f`` is manipulated by OASIS3-MCT under ``E_IN_0`` from the LMDZ side and under another name from the Python side. Those aliases are used in the OASIS3-MCT namelist. ``name`` must absolutely be in accordance with the content of the OASIS3-MCT namelist.

.. note:: Eophis provides useful `tools <https://eophis.readthedocs.io/en/latest/usage.html#oasis-namcouple>`_ to know and manipulate OASIS3-MCT aliases.


Once ``infosend`` and ``inforecv`` have been correctly filled. Finalize fields registration with:

.. code-block:: fortran

    CALL cpl_vardef( kmod )
    ! INTEGER :: kmod      ! calling module ID

    ! For above example
    CALL cpl_var( midpycpl )



Send a field
~~~~~~~~~~~~

During a physics core time iteration only, a coupled field can be sent with this function:

.. code-block:: fortran

    CALL cpl_snd( kmod, kid, kstep, pdata )
    ! INTEGER                :: kmod   ! calling module ID
    ! INTEGER                :: kid    ! field index in infosend for calling module
    ! INTEGER                :: kstep  ! physics time-step in second
    ! REAL, DIMENSION(:,:)   :: pdata  ! field to send (shape is (:,1) for 2D)

The ``pdata`` shape must be equivalent to the horizontal flattened OMP-gathered LMDZ physics grid size for the first dimension. The second dimension is compulsory even for 2D fields and must be at least equal to the ``nlvl`` value defined during initialization.

.. code-block:: fortran

    ! Example to send a 2D array named to_send, as "u"
    ## [...]
    REAL, DIMENSION(nbp_lon*jj_nb,1) :: to_send
    INTEGER :: isec
    
    ! Array bounds
    kstart = ii_begin
    IF (is_south_pole_dyn) THEN
        kend = (jj_end-jj_begin)*nbp_lon + nbp_lon
    ELSE
        kend = (jj_end - jj_begin)*nbp_lon + ii_end
    ENDIF
    
    isec = ( itap - 1 ) * phys_tstep
    
    CALL cpl_snd(midpycpl, jps_su, isec, zbuf(kstart:kend,:))




Receive a field
~~~~~~~~~~~~~~~

During a physics core time iteration only, a coupled field can be received with this function:

.. code-block:: fortran

    CALL cpl_rcv( kmod, kid, kstep, pdata )
    ! INTEGER                :: kmod   ! calling module ID
    ! INTEGER                :: kid    ! field index in inforecv for calling module
    ! INTEGER                :: kstep  ! ocean time-step in second
    ! REAL, DIMENSION(:,:)  :: pdata  ! returned received field (shape is (:,1) for 2D)

As for sending, ``pdata`` shape must be equivalent to the horizontal flattened OMP-gathered LMDZ physics grid size for the first dimension, and ``nlvl`` for the second dimension.

.. code-block:: fortran

    ! Example to receive the 2D forcing field "u_f" in an array named to_rcv
    INTEGER :: isec
    REAL, DIMENSION(nbp_lon*jj_nb,1) :: to_rcv
    
    isec = ( itap - 1 ) * phys_tstep
    CALL cpl_rcv(midpycpl, jpr_uf, isec, to_rcv(kstart:kend,:))



User guide
----------

To facilitate deployment or modification of a hybrid LMDZ experiment, `TRACCS-COMPACT patches <https://github.com/TRACCS-COMPACT/Hybrid_Python-LMDZ/tree/main/LMDZ_Patches/>`_ directly provide pre-defined communication modules named ``pycpl.f90`` and ``pyfld.f90``. This section describes how to use them.


.. warning:: The pre-defined communication modules require Eophis version 1.1.0 or later to be used.


The presented examples rely on the BENCH32x32x39.DJ08 test case. Purposes and behaviors of BENCH32x32x39.DJ08 are described in the LMDZ **Getting started** section of this documentation. Let's resume what both entities are exchanging.

LMDZ intends to send:
    - three time-evolving atmospheric fields named ``pres``, ``temp``, and ``q_spec`` at a ``900s`` frequency, on grid ``(32,33,39)``
and to receive from DJ08 formulation:
    - the wet-bulb potential temperature fields ``theta_w``, with the same dimensions


**with corresponding Eophis exchange definition:**

.. code-block:: python

    {'freq' : step, 'grd' : 'lmdz', 'lvl' : 39, 'in' : ['pres','temp','q_spec'], 'out' : ['theta_w'] }



Python fields
~~~~~~~~~~~~~

Module ``pyfld.F90`` is dedicated to the definition of arrays containing the fields returned by the external Python script.


.. code-block:: fortran

    !!-------------------------------------------------------------------------
    !!                   Fields on the OMP-shared physics grid
    !!-------------------------------------------------------------------------
    REAL, PUBLIC, ALLOCATABLE, SAVE, DIMENSION(:,:)  :: theta_w  ! ! outsourced wet-bulb pot. temp.
    !$OMP THREADPRIVATE(theta_w)

We just need to store the results exchanged and/or computed by the communication module in ``theta_w``. Then, it can be imported to be used by any other module with:

.. code-block:: fortran

    USE pyfld, ONLY: theta_w


A function to allocate the arrays with the right grid size is present in the module and must be correctly set. For instance:

.. code-block:: fortran

   SUBROUTINE pyfld_alloc()
      !!----------------------------------------------------------------------
      !!             ***  ROUTINE pyfld_alloc  ***
      !!
      !! ** Purpose :   Initialisation of the Python coupling working arrays
      !!
      !! ** Method  :   * Allocate arrays for Python fields
      !!----------------------------------------------------------------------
      !
      ! [...]
      !
      ! Allocate fields on physics grid
      ALLOCATE( theta_w(klon, klev) )
      !
      ! [...]
      !
   END SUBROUTINE pyfld_alloc
   
   
It is automatically called during LMDZ6 initialization.

.. note :: Depending on the grid on which you wish to define the array, the allocation and declaration must be performed differently. ``pyfld.F90`` contains commented templates for arrays defined on the coupling grid (horizontal flattened OMP-gathered physics grid), OMP-shared physics grid, or dynamic grid.


Exchange fields
~~~~~~~~~~~~~~~

Configuration of OASIS3-MCT following Eophis definitions in LMDZ6 is automatically handled by the ``pycpl.F90`` module. The latter simply provides two functions to send and receive fields in accordance with the Eophis framework:


.. code-block:: fortran

    CALL send_to_python_GRD(varname, to_send, kt)
    ! CHAR                    :: varname  ! field name defined in Eophis
    ! REAL                    :: to_send  ! array to send, 2D or 3D
    ! INTEGER                 :: kt       ! physics time step
    
    # ---------------------------------------------------------------- #
    ! Example to send velocity field pplay in pipeline "pres"
    CALL send_to_python_phys('pres', pplay, itap)


.. code-block:: fortran

    CALL receive_from_python_GRD(varname, to_rcv, kt)
    ! CHAR                    :: varname  ! field name defined in Eophis
    ! REAL                    :: to_rcv   ! array that will receive data, 2D or 3D
    ! INTEGER                 :: kt       ! physics time step
    
    # ---------------------------------------------------------------- #
    ! Example to receive result from pipeline "thetaw" in theta_w
    CALL receive_from_python_phys('theta_w', theta_w, itap)


.. note :: ``GRD`` is here to specify that it should be replaced by ``cpl`` or ``phys``. The former functions handle fields discretized on the coupling grid (flattened OMP-gathered physics grid), while the latter handles fields discretized on the OMP-shared physics grid and perform the conversion. For fields defined on the dynamic grid or others, the conversion must be done by the user. For a demonstration of array tranfer, check the use case LMDZ-GCM96x96x35.K26.


These functions can be used anywhere in LMDZ by importing the ``pycpl`` module. For more convenience, it can be useful to gather all sendings and or receivings in two different routines, then to call them at different moments of the time loop. This is the way to take advantage of parallel execution of LMDZ6 and the Python scripts and reduce waiting time for Python returns.


Compile LMDZ
------------

After configurating the communication module, LMDZ must be compiled with active *key_eophis* CPP key and OASIS3-MCT_v5.0 (see this `guide <https://morays-doc.readthedocs.io/en/latest/nemo.getting_started.html#morays-environment>`_).
