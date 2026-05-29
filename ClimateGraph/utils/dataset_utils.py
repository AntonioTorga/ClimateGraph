import ast
import operator as _op

import pint_xarray  # noqa: F401  — registers the `.pint` accessor on xarray DataArrays
import xarray as xr

from .general_utils import ReductionMethodEnum, manage_time_interval

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


def apply_operation(xa: xr.DataArray, operation: str) -> xr.DataArray:
    """apply_operation Apply a scalar arithmetic operation to a variable.

    Meant for unit conversions that pint can't express — e.g. mass/volume
    (``ug/m**3``) to a mixing ratio (``ppb``), which is a multiply by a
    constant factor for a given temperature and pressure.

    ``operation`` is a small arithmetic expression in the variable ``x``,
    e.g. ``"x * 0.8"`` or ``"x / 48 * 24.45"``. As a shorthand, a leading
    binary operator implies ``x`` on the left: ``"*3"`` means ``"x * 3"``,
    ``"/48"`` means ``"x / 48"``, ``"**2"`` means ``"x ** 2"``. Only
    arithmetic on ``x`` and numeric constants is permitted.

    Parameters
    ----------
    xa : xr.DataArray
        Variable to transform.
    operation : str
        Arithmetic expression (see above).

    Returns
    -------
    xr.DataArray
        The transformed variable. Name and coordinates are preserved.

    Raises
    ------
    ValueError
        If the expression contains anything other than arithmetic on ``x``
        and numeric constants.
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
        if isinstance(node, ast.Name) and node.id == "x":
            return xa
        raise ValueError(
            f"Unsupported operation {operation!r}: only arithmetic on `x` "
            "and numeric constants is allowed."
        )

    return _eval(ast.parse(expr, mode="eval"))


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
    if timestep is not None:
        ds = getattr(ds.resample(time=timestep), reduction_method.value)()
    return ds


def change_unit(xa: xr.DataArray, src_unit: str, dst_unit: str) -> xr.DataArray:
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
    if src_unit == dst_unit:
        return xa  # No sense on performing any operations if it is already in the desired unit.

    xa_coords = list(xa.coords.keys())
    var_name = xa.name
    xa = xa.reset_coords(drop=False)
    xa[var_name] = xa[var_name].pint.quantify(src_unit)
    xa[var_name] = xa[var_name].pint.to(dst_unit)
    xa[var_name] = xa[var_name].pint.dequantify()
    xa = xa.set_coords(xa_coords)
    return xa[var_name]
