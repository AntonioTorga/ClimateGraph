import json
import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from ClimateGraph.data import Data
from ClimateGraph.domain import Domain
from ClimateGraph.plot import Plot
from ClimateGraph.utils.control_model import ControlFile

FILE_READERS = {".json": json.load, ".yaml": yaml.safe_load, ".yml": yaml.safe_load}


def _expand_domains(domain_models: dict) -> tuple[dict, dict[str, list[str]]]:
    """Expand domain configs flagged ``one_for_each`` into one config per value.

    Only ``AttributeConfig`` carries ``one_for_each``; other domain types don't
    have the attribute, so ``getattr(..., False)`` makes them a no-op here.

    Returns
    -------
    tuple[dict, dict[str, list[str]]]
        The expanded {name: domain_model} dict (un-flagged domains pass through
        unchanged), and a {original_name: [expanded_names]} rewrite map used to
        resolve plot ``domains:`` references that still point at the original name.
    """
    expanded = {}
    rewrite_map = {}
    for name, model in domain_models.items():
        if not getattr(model, "one_for_each", False):
            expanded[name] = model
            continue

        field_value = model.field_value
        if not isinstance(field_value, list):
            expanded[name] = model
            logging.debug(
                f"Attempted expansion of domain {name} but there was no expansible value en field_value. Left as is."
            )
            continue

        generated_names = []
        for value in field_value:
            new_name = f"{name}__{value}"
            expanded[new_name] = model.model_copy(
                update={"field_value": value, "one_for_each": False}
            )
            generated_names.append(new_name)
        rewrite_map[name] = generated_names

    return expanded, rewrite_map


class Parser:
    """Parser class, used for managing input configuration files for ClimateGraph"""

    @staticmethod
    def parse_control(control_path: Path):
        """parse_control Parse configuration file with Pydantic model.

        Parameters
        ----------
        control_path : Path
            Path to configuration file.

        Returns
        -------
        AnalysisModel, Dict[str, Data], Dict[str, Plot], Dict[str,Domain]
            analysis, data, plots and domains specified for ClimateGraph execution.

        Raises
        ------
        ValueError
            Configuration file doesn't meet the ControlFile pydantic model.
        """
        control_dict = Parser.read_control(control_path)

        try:
            valid = ControlFile.model_validate(control_dict)
        except ValidationError as err:
            error_str = ""
            for e in err.errors():
                error_str += f"Error {e['msg']}. Input given:\n{e['input']}\n    See more info at: {e['url']}\n"
            raise ValueError(
                f"Configuration file {control_path} doesn't meet the input structure.\n\n{error_str}\n\nFix this errors before retrying..."
            ) from err

        analysis = valid.analysis.model_dump()
        data = dict()
        plots = dict()
        domains = dict()

        # Default download cache for readers that fetch remote paths.
        # Per-data `cache_dir` in YAML overrides this; local-only readers
        # never look at it.
        default_cache_dir = analysis["output_path"] / ".cache"

        for data_name, data_model in valid.data.items():
            _name = data_name
            _topology, _reader, _path, _vars, _crs = (
                data_model.topology,
                data_model.reader,
                data_model.path,
                data_model.vars,
                data_model.crs,
            )
            # Only necessary for dict, but not REALLY sure how necessary it is
            if isinstance(_vars, dict):
                _vars = {
                    var: var_model.model_dump() for var, var_model in _vars.items()
                }

            # model_extra is reader-specific kwargs (rename overrides,
            # vertical_level for Chimere, etc.). Lifecycle settings
            # (load_mode, cache_dir) are declared fields — we add them
            # in explicitly so Data.load_obj has the full picture
            # without Data growing new parameters.
            reader_kwargs = dict(data_model.model_extra or {})
            reader_kwargs["load_mode"] = data_model.load_mode
            reader_kwargs["cache_dir"] = data_model.cache_dir or default_cache_dir
            reader_kwargs["save_to"] = data_model.save_to

            data_instance = Data.create(
                _name, _topology, _reader, _path, _vars, _crs, reader_kwargs
            )

            data[_name] = data_instance

        rewrite_map = {}
        if valid.domains:
            expanded_domains, rewrite_map = _expand_domains(valid.domains)
            for domain_name, domain_model in expanded_domains.items():
                _type = domain_model.type
                domain_instance = Domain.create(domain_name, _type, domain_model)
                domains[domain_name] = domain_instance
        if valid.plots:
            for plot_name, plot_model in valid.plots.items():
                if rewrite_map and getattr(plot_model, "domains", None):
                    resolved = []
                    for ref in plot_model.domains:
                        resolved.extend(rewrite_map.get(ref, [ref]))
                    plot_model.domains = resolved

                _type = plot_model.type
                plot_instance = Plot.create(
                    plot_name,
                    _type,
                    plot_model,
                    data,
                    domains,
                    output_path=analysis["output_path"],
                )
                plots[plot_name] = plot_instance

        return analysis, data, plots, domains

    @staticmethod
    def read_control(control_path: Path):
        """read_control Reads files into Mappings. Currently manages .json, .yml and .yaml

        Parameters
        ----------
        control_path : Path
            Path to configuration file.

        Returns
        -------
        Dict
            Mapping with configuration arguments.

        Raises
        ------
        FileNotFoundError
            Path doesn't point to any file.
        ValueError
            File type not supported.
        """
        control_path = control_path.resolve()
        if not (control_path.exists() and control_path.is_file()):
            raise FileNotFoundError(f"File {control_path} not found.")
        if (reader := FILE_READERS.get(control_path.suffix)) is None:
            raise ValueError(f"File type {control_path.suffix} not supported.")

        with open(control_path) as fp:
            control_dict = reader(fp)
        return control_dict
