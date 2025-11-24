import typer
from typing_extensions import Annotated
from pathlib import Path
from .AppKernel import AppKernel


app = typer.Typer(
    name="ClimateGraph",
    help="ClimateGraph Command Line Interface",
    pretty_exceptions_enable=False,
)


@app.command()
def run(
    file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            file_okay=True,
            resolve_path=True,
            help="File defining the graphs.",
        ),
    ],
):
    appK = AppKernel()
    AppKernel.run(file)
