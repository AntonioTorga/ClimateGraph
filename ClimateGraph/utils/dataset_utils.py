import ast
import logging
import operator as _op
from datetime import UTC, datetime

import pint_xarray  # noqa: F401
import xarray as xr

from .general_utils import ReductionMethodEnum, manage_time_interval


def _record(obj: xr.Dataset | xr.DataArray, entry: str) -> None:
    """Append a timestamped entry to obj.attrs['history']."""
    history = obj.attrs.get("history", [])
    if not isinstance(history, list):
        history = [history]  # handle pre-existing CF string history
    log_item = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {entry}"
    history.append(log_item)
    obj.attrs["history"] = history
    logging.debug(log_item)


def dim_reduction(
    obj: xr.Dataset | xr.DataArray,
    spec: dict[str, str | dict],
    name: str = "",
) -> xr.Dataset | xr.DataArray:
    """Apply per-dimension reductions/selections to an xarray object.

    Parameters
    ----------
    obj : xr.Dataset | xr.DataArray
        Data to reduce.
    spec : dict[str, str | dict]
        Mapping of dim name → reduction spec. Each value is either:
        - a string method name (``"mean"``, ``"min"``, ``"max"``)
        - a dict with ``method`` key plus a ``value`` key for isel/sel:
          ``{"method": "isel", "value": 0}``
          ``{"method": "sel", "value": 5.0}``
          ``{"method": "mean"}``
    name : str
        Identifier for history recording (e.g. dataset name or variable name).

    Returns
    -------
    xr.Dataset | xr.DataArray
        The object with the specified dimensions reduced/selected.
    """
    for dim, dim_spec in spec.items():
        if dim not in obj.dims:
            continue
        method = (
            dim_spec if isinstance(dim_spec, str) else dim_spec.get("method", "mean")
        )
        value = None if isinstance(dim_spec, str) else dim_spec.get("value")
        if method == "isel":
            idx = value if value is not None else 0
            obj = obj.isel({dim: idx})
            _record(obj, f"{name} selected {dim}={idx} via isel")
        elif method == "sel":
            obj = obj.sel({dim: value})
            _record(obj, f"{name} selected {dim}={value} via sel")
        else:
            func = ReductionMethodEnum(method).func
            obj = obj.reduce(func, dim)
            _record(obj, f"{name} reduced {dim!r} with {method}")
    return obj


# TODO: make this into accessors

# Arithmetic allowed inside a var-level `operation:` expression. Deliberately
# tiny: binary/unary arithmetic on the variable `x` and numeric constants.
# No attribute access, calls or names other than `x`, so a config string can't
# execute arbitrary code.
_ALLOWED_BINOPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.Pow: _op.pow,
    ast.Mod: _op.mod,
}
_ALLOWED_UNARYOPS = {ast.UAdd: _op.pos, ast.USub: _op.neg}


def apply_operation(operation: str, variables: dict[str, xr.DataArray]) -> xr.DataArray:
    """apply_operation Evaluate a small arithmetic "operation" over variables.

    Two uses:
    - unit conversions pint can't express like operations over the data with constants (+273 for example)
    - composing a new variable from others

    "operation" is an arithmetic expression whose named vars are looked up in
    variables (which carries the variable's own data under "x" plus the
    canonical names of the available base variables). As a shorthand, a leading
    binary operator implies x on the left: "*3" means "x * 3". Also **, /, and others available

    Parameters
    ----------
    operation : str
        Arithmetic expression (see above).
    variables : dict[str, xr.DataArray]
        Names available to the expression mapped to their data.

    Returns
    -------
    xr.DataArray
        The evaluated variable.

    Raises
    ------
    ValueError
        If the expression references a name not in variables, or contains
        anything other than arithmetic and numeric constants.
    """
    expr = operation.strip()
    # Leading-operator shorthand: "*3" -> "x*3". `**` starts with `*` too,
    # so "**2" -> "x**2" falls out for free.
    if expr[:1] in {"*", "/", "+", "-"}:
        expr = "x" + expr

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
            return _ALLOWED_UNARYOPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
            raise ValueError(
                f"Operation {operation!r} references unknown variable "
                f"{node.id!r}; available: {sorted(variables)}."
            )
        raise ValueError(
            f"Unsupported operation {operation!r}: only arithmetic on declared variables and numeric constants is allowed."
        )

    result = _eval(ast.parse(expr, mode="eval"))
    _record(result, f"computed: {operation}")
    return result


def normalize_vars(
    vars: dict[str, dict] | list[str] | None,
) -> dict[str, dict] | None:
    """normalize_vars Coerce the user-supplied ``vars`` into the canonical
    dict-or-None shape the rest of the pipeline expects.

    - a dict returned unchanged (today's full form, units optional);
    - a plain list[str] of file-native names — expanded to an identity
      mapping with null units, e.g. ``["PM10"] -> {"PM10": {"name": "PM10",
      "unit": None, "operation": None}}``.
    - None (omitted) — returned as ``None`` so the readers keep every
      variable under its file-native name.

    Parameters
    ----------
    vars : dict[str, dict] | list[str] | None
        The raw vars declaration.

    Returns
    -------
    dict[str, dict] | None
        var dict mapping (cannonical names), or ``None`` when nothing was declared.
    """
    if isinstance(vars, list):
        return {name: {"name": name, "unit": None, "operation": None} for name in vars}
    return vars


def variable_aggregation(ds: xr.Dataset, aggregation_dict: dict) -> xr.Dataset:
    """variable_aggregation Creates new variable from variable aggregation.

    Parameters
    ----------
    ds : xr.Dataset
        Dataset to perform aggregations.
    aggregation_dict : dict
        Aggregation dictionary. Maps new variable names a mapping of variable to ponderation weight.

    Returns
    -------
    xr.Dataset
        Dataset with the aggregated variables included.
    """
    # key: new variable
    # value: dict with dict(old variable : ponderations to sum)
    new_vars = dict()

    for new_var, ponderations in aggregation_dict.items():
        xa = None
        for name_var, ponderation in ponderations.items():
            if xa is None:
                xa = ds[name_var].copy() * ponderation
            else:
                xa += ds[name_var] * ponderation

        new_vars[new_var] = xa

    return ds.assign(new_vars)


def time_resampling(
    ds: xr.Dataset | xr.DataArray,
    timestep: str | None = None,
    time_interval: str | None = None,
    reduction_method: ReductionMethodEnum = ReductionMethodEnum.mean,
) -> xr.Dataset | xr.DataArray:
    """time_resampling Implements time resampling and alignment.

    Parameters
    ----------
    ds : xr.Dataset | xr.DataArray
        Dataset to be processed.
    timestep : str | None, optional
        Timestep in which to resample the dataset. If None no resampling happens, by default None
    time_interval : str | None, optional
        Time interval to filter the dataset. If None no selection happens, by default None
    reduction_method : ReductionMethodEnum, optional
        Reduction method for the resampling, by default ReductionMethodEnum.mean

    Returns
    -------
    xr.Dataset | xr.DataArray
        Resampled and aligned dataset.
    """
    if time_interval is not None:
        start, end = manage_time_interval(time_interval)
        ds = ds.sel({"time": slice(start, end)})
        _record(ds, f"selected time interval {start} to {end}")
    if timestep is not None:
        ds = getattr(ds.resample(time=timestep), reduction_method.value)()
        _record(ds, f"resampled time to {timestep} ({reduction_method.value})")
    return ds


def change_unit(
    xa: xr.DataArray, src_unit: str | None, dst_unit: str | None
) -> xr.DataArray:
    """change_unit Unit conversion method for datasets.

    Parameters
    ----------
    xa : xr.DataArray
        Data to convert to other unit.
    src_unit : str
        Unit of the source data.
    dst_unit : str
        Destination unit for the data.

    Returns
    -------
    xr.DataArray
        Data in the destination measure unit.
    """
    if src_unit is None or dst_unit is None:
        logging.info(
            f"Source unit or destination unit wasn't provided.\nLeaving {xa.name} in the provided unit. This will reflect in graphs."
        )
        return xa
    if src_unit == dst_unit:
        return xa  # No sense on performing any operations if it is already in the desired unit.

    xa_coords = list(xa.coords.keys())
    var_name = xa.name
    xa = xa.reset_coords(drop=False)
    xa[var_name] = xa[var_name].pint.quantify(src_unit)
    xa[var_name] = xa[var_name].pint.to(dst_unit)
    xa[var_name] = xa[var_name].pint.dequantify()
    xa = xa.set_coords(xa_coords)
    xa = xa[var_name]
    _record(xa, f"converted {var_name} from {src_unit} to {dst_unit}")
    return xa
