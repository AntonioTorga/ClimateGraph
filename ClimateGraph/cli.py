from ClimateGraph.appkernel import AppKernel

import typer
from typing import Annotated
from pathlib import Path

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
            help="File defining the analysis.",
        ),
    ],
):
    appK = AppKernel()
    appK.run(control_file)


@app.command()
def version():
    """
    Print the version of ClimateGraph.
    """
    print("ClimateGraph version 0.1.0")


if __name__ == "__main__":
    app()
