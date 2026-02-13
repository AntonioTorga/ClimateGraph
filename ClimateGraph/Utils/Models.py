from pydantic import BaseModel, ConfigDict
from typing import Dict, List, Optional, Union, Any

class AnalysisModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    timestep: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    results_path: Optional[str] = None

class VarModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str
    unit: Optional[str] = None

class DataModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    files: Optional[Union[str, List[str]]] = None
    file: Optional[str] = None
    type: str
    subtype: Optional[str] = None
    vars: Dict[str, VarModel]

class PlotModel(BaseModel):
    model_config = ConfigDict(extra='allow')
    type: str
    over: Optional[str] = None
    under: Optional[str] = None
    vars: List[str]
    title: Optional[Any] = None

class ConfigModel(BaseModel):
    analysis: Optional[AnalysisModel] = None
    data: Dict[str, DataModel]
    plots: Dict[str, PlotModel]

    def get_figures(self):
        return self.plots

    def get_data(self):
        return self.data
