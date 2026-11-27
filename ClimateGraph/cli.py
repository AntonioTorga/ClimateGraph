"""Command line interface.
Exposes the main ClimateGraph reading->processing->plotting routine through the command line, and a version check useful for installation check.
Now the only existing option is creating a configuration file and passing it through the Run command.
"""

from importlib.metadata import version as _package_version
from pathlib import Path
from typing import Annotated

import typer

from ClimateGraph.appkernel import AppKernel

app = typer.Typer(
    name="ClimateGraph",
    help="ClimateGraph Command Line Interface",
    pretty_exceptions_enable=False,
)


@app.command()
def run(
    control_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            file_okay=True,
            resolve_path=True,
            help="File configuring the analysis run.",
        ),
    ],
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Force DEBUG-level logging, all of it on stdout. ORed with the control file's debug setting.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Per-stage detail on stdout, warnings and errors on stderr. ORed with the control file's verbose setting.",
        ),
    ] = False,
):
    """Run the ClimateGraph routine with a control file.

    Parameters
    ----------
    control_file : Path
        Path to the control file (``.yaml``, ``.yml`` or ``.json``) describing
        the analysis. Typer checks that it exists and is a file, and resolves it
        to an absolute path, before this function runs.
    debug : bool, optional
        Force DEBUG-level logging on ClimateGraph's own logger, with every
        record on stdout. If either the config states debug mode or this flag
        is on, debug mode is on.
    verbose : bool, optional
        Per-stage detail on stdout, keeping warnings and errors on stderr.
        ORed with the control file the same way. Implied by ``--debug``.
    """
    appK = AppKernel()
    appK.run(control_file, debug_override=debug, verbose_override=verbose)


@app.command()
def version():
    """Print the version of ClimateGraph, as recorded in the package metadata."""
    print(f"ClimateGraph version {_package_version('ClimateGraph')}")


if __name__ == "__main__":
    app()
