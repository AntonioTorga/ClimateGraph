"""Reading names out of control-file models.

The cross-reference checks in :mod:`ClimateGraph.utils.control_model` need to
know which datasets and variables a plot points at. A field can take several
shapes — a string, a list, a mapping — so each lookup is flattened here and
the schema stays a schema.
"""

from typing import TYPE_CHECKING

from ClimateGraph.plot.primitive import Primitive

if TYPE_CHECKING:
    from ClimateGraph.utils.control_model import VarModel

# The fields a plot can name a dataset in. Four spellings across the plot
# types, so every reference check sweeps all of them.
DATASET_REF_FIELDS = ("base", "superposed", "data")

# Qualifies a variable with the dataset it comes from, so one layer can draw
# from several: ``lower: MODEL::PM25``.
REF_SEPARATOR = "::"


def split_ref(ref: str, default_dataset: str | None = None) -> tuple[str | None, str]:
    """Resolve a variable reference into its dataset and its variable.

    Shorthand, read at config time, so nothing downstream handles the
    separator — a layer naming one dataset folds straight into ``dataset:``
    and ``var:``.

    Parameters
    ----------
    ref : str
        ``"VAR"`` or ``"DATASET::VAR"``.
    default_dataset : str | None
        Used when the reference names no dataset — the layer's own.

    Returns
    -------
    tuple[str | None, str]
        Dataset name, None when neither the reference nor the default gives
        one, and the bare variable name.
    """
    dataset, separator, var = ref.partition(REF_SEPARATOR)
    return (dataset, var) if separator else (default_dataset, ref)


def subplot_role_refs(subplot) -> set[tuple[str | None, str]]:
    """``(dataset, variable)`` pairs a subplot's primitive names by role.

    Empty for the single-variable primitives, and for a ``type`` the registry
    does not know — the discriminated union has already rejected that.
    """
    subplot_type = getattr(subplot, "type", None)
    if not subplot_type or not Primitive.check_primitive_class(subplot_type):
        return set()
    roles = Primitive.get_primitive_class(subplot_type).required_vars(subplot)
    return {ref for ref in roles.values() if ref[1] is not None}


def plot_var_names(vars: str | list[str] | dict[str, str] | None) -> set[str]:
    """Variable names a plot references, regardless of the form ``vars`` took."""
    if vars is None:
        return set()
    if isinstance(vars, str):
        return {vars}
    if isinstance(vars, dict):
        return set(vars.keys())
    return set(vars)


def declared_var_names(
    vars: "dict[str, VarModel] | list[str] | None",
) -> set[str] | None:
    """Names a dataset exposes, or ``None`` when vars was omitted (unknowable)."""
    if isinstance(vars, dict):
        return set(vars.keys())
    if isinstance(vars, list):
        return set(vars)
    return None


def referenced_datasets(plot_model, fields: tuple[str, ...]) -> set[str]:
    """Collect data-block names a plot points at across its reference fields."""
    names: set[str] = set()
    for field in fields:
        value = getattr(plot_model, field, None)
        if isinstance(value, str):
            names.add(value)
        elif isinstance(value, list):
            names.update(v for v in value if isinstance(v, str))
    return names
