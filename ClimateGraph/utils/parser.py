import json
import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from ClimateGraph.data import Data
from ClimateGraph.data.point_surface import PointSurface
from ClimateGraph.domain import Domain
from ClimateGraph.domain.domains import AttributeConfig, PointsConfig
from ClimateGraph.plot import Plot
from ClimateGraph.utils.control_model import ControlFile

log = logging.getLogger(__name__)

FILE_READERS = {".json": json.load, ".yaml": yaml.safe_load, ".yml": yaml.safe_load}


def _expansion_entries(name: str, model) -> list[tuple[str, object]] | None:
    """Compute the per-value expansions for a ``one_for_each`` domain.

    Returns ``[(expanded_name, expanded_model), ...]``, or ``None`` when the model
    can't be expanded (so the caller leaves it as-is). Handles the two domain types
    that carry ``one_for_each``:

    - ``AttributeConfig``: one domain per ``field_value`` (needs a list), named
      ``{name}__{value}``.
    - ``PointsConfig``: one domain per named point, named by the point; each keeps
      the full point set and gets a ``select_name`` so they share one resample
      target and just ``.sel`` their site.
    """
    if isinstance(model, PointsConfig):
        return [
            (
                pname,
                model.model_copy(update={"select_name": pname, "one_for_each": False}),
            )
            for pname, _lat, _lon in model.resolve_points()
        ]
    if isinstance(model, AttributeConfig):
        if not isinstance(model.field_value, list):
            return None
        return [
            (
                f"{name}__{value}",
                model.model_copy(update={"field_value": value, "one_for_each": False}),
            )
            for value in model.field_value
        ]
    return None


def _points_target(model: PointsConfig, cache: dict) -> PointSurface:
    """Build (or reuse) the in-memory PointSurface target for a Points domain.

    Memoized on the resolved points so all fan-out expansions of one block share a
    single target object — giving them one resample-cache entry (keyed by the
    target's unique name) instead of recomputing the projection per point. A new
    distinct point set gets a fresh unique name so different geometries never
    collide in the resample cache.
    """
    pts = tuple(model.resolve_points())
    target = cache.get(pts)
    if target is None:
        names = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        lons = [p[2] for p in pts]
        target = PointSurface.from_points(
            f"__points_target_{len(cache)}", names, lats, lons
        )
        cache[pts] = target
    return target


def _expand_domains(domain_models: dict) -> tuple[dict, dict[str, list[str]]]:
    """Expand domain configs flagged ``one_for_each`` into one config per value.

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

        entries = _expansion_entries(name, model)
        if not entries:
            expanded[name] = model
            log.debug(
                f"Attempted expansion of domain {name} but there was no expansible "
                "value. Left as is."
            )
            continue

        generated_names = []
        for new_name, new_model in entries:
            expanded[new_name] = new_model
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
            # Points domains build their own in-memory target from the point set;
            # memoize by the resolved points so every fan-out expansion (and the
            # grouped case) shares one target -> one resample cache entry.
            points_targets: dict[tuple, PointSurface] = {}
            for domain_name, domain_model in expanded_domains.items():
                _type = domain_model.type
                # Optional resample pre-step: resolve the target geometry so the
                # domain can reproject onto it.
                target_data = None
                if isinstance(domain_model, PointsConfig):
                    target_data = _points_target(domain_model, points_targets)
                elif getattr(domain_model, "resample_to", None):
                    target_data = data.get(domain_model.resample_to)
                    if target_data is None:
                        raise ValueError(
                            f"Domain '{domain_name}' resample_to references unknown "
                            f"dataset '{domain_model.resample_to}'."
                        )
                domain_instance = Domain.create(
                    domain_name, _type, domain_model, target_data=target_data
                )
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
