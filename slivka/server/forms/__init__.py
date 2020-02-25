import inspect

from .form import FormLoader


def auto_schema(cls):
    schema = super(cls, cls).schema
    properties = schema['properties']['value']['properties']
    required = schema['properties']['value']['required']
    properties['type'] = {}
    signature = inspect.signature(cls)
    for param in signature.parameters.values():
        if param.kind == param.VAR_KEYWORD:
            continue
        properties[param.name] = {}
        if param.default == param.empty:
            required.append(param.name)
    cls.schema = schema
    return cls
