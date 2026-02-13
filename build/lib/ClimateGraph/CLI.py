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
    output_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=True,
            file_okay=False,
            resolve_path=True,
            help="Analysis output directory",
        ),
    ],
):
    appK = AppKernel(output_path=output_path)
    AppKernel.run(control_file)
