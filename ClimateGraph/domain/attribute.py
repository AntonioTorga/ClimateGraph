# from ClimateGraph.Domain import Domain
# from ..Data.Data import Data


# class AttributeDomain(Domain):
#     # In lack of a better term, attribute refers to a coord or variable name. And then value
#     # would be a value that the attribute takes, and we would filter an incoming dataset
#     # keeping the data points that have said value for that attribute.
#     def __init__(self, name: str, attribute, value):
#         super().__init__(name)
#         self.attribute = attribute
#         self.value = value

#     def apply(self, data: Data) -> Data:
#         obj = data.get_obj()
#         obj.sel({self.attribute: self.value})
#         # TODO: should i create a copy here? i think so, but how? is making a temp var enough?
#         # if i do that, am i duplicating more data than needed? Should i defer this computing to
#         # when the original Data has been computed? Or does xarray take care of caching that?
#         pass
