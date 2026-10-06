Command line interface
======================

:mod:`ClimateGraph.cli`

Purpose
-------

The CLI exposes the main routine of ClimateGraph. The entry point offered is a very general and
configurable one. It is one canonical run — hand it a control file and it
executes the analysis configured.

It is deliberately thin and only calls the main function of
:class:`~ClimateGraph.appkernel.AppKernel`. Refer to
:meth:`AppKernel.run <ClimateGraph.appkernel.AppKernel.run>` for any routine
schedule questions.

Commands
--------

``run``
^^^^^^^

Implemented by :func:`ClimateGraph.cli.run`.

.. code-block:: console

   $ ClimateGraph run path/to/config.yaml
   $ ClimateGraph run path/to/config.yaml --debug

Takes the path to a control file (``.yaml``, ``.yml`` or ``.json``) and runs the
analysis it describes.

The path argument is verified in the CLI by typer, and the rest will be checked
by the parser through a Pydantic model — see
:class:`~ClimateGraph.utils.control_model.ControlFile` in
:mod:`ClimateGraph.utils.control_model`.

``version``
^^^^^^^^^^^

Implemented by :func:`ClimateGraph.cli.version`.

.. code-block:: console

   $ ClimateGraph version

Prints the package version.

Keep in mind
------------

``--debug`` cannot turn debugging *off*
   The configuration file argument "debug" takes precedence over the flag (``self.debug = debug_override or self.debug``).
   Passing the flag always ensures it is turned on when running.
