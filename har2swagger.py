"""
function: convert har to swagger
author: hugo
"""

import json
import yaml
import argparse

from collections import abc, OrderedDict
from urllib.parse import urlparse

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from yaml.representer import SafeRepresenter

_mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG


def dict_representer(dumper, data):
    return dumper.represent_dict(data.items())


def dict_constructor(loader, node):
    return OrderedDict(loader.construct_pairs(node))


Dumper.add_representer(OrderedDict, dict_representer)
Loader.add_constructor(_mapping_tag, dict_constructor)
Dumper.add_representer(str, SafeRepresenter.represent_str)


SUPPORT_MIME_TYPES = [
    "application/json",
    # "application/xml"
]


class YAMLSchemaDecoder(json.JSONDecoder):
    def decode(self, obj):
        val = super(YAMLSchemaDecoder, self).decode(obj)
        return self.parse_schema(val)
    
    def parse_schema(self, val):
        if isinstance(val, abc.Mapping):
            return dict(
                type="object",
                properties={k: self.parse_schema(v) for k, v in val.items()}
            )
        elif isinstance(val, abc.MutableSequence):
            if len(val) == 0:
                items = {}
            else:
                items = self.parse_schema(val[0])
            return dict(
                type="array",
                items=items
            )
        elif isinstance(val, int):
            return dict(
                type="integer",
                description="",
                example=val
            )
        elif isinstance(val, float):
            return dict(
                type="number",
                description="",
                example=val
            )
        elif isinstance(val, str):
            return dict(
                type="string",
                description="",
                example=val
            )
        elif isinstance(val, bool):
            return dict(
                type="boolean",
                desciption="",
                example=val
            )
        elif isinstance(val, type(None)):
            return dict(
                type="string",
                # nullable=True,
                # desciption="",
                example=val
            )
        else:
            raise ValueError("Not support type: %s, value: %s" % (type(val), val))


class FrozenJSON:
    """A read-only façade for navigating a JSON-like object using attribute notation"""
    def __init__(self, mapping):
        self.__data = dict(mapping)

    def __getattr__(self, name):
        if hasattr(self.__data, name):
            return getattr(self.__data, name)
        else:
            return FrozenJSON.build(self.__data[name])

    @classmethod
    def build(cls, obj):
        if isinstance(obj, abc.Mapping):
            return cls(obj)
        elif isinstance(obj, abc.MutableSequence):
            return [cls.build(item) for item in obj]
        else:
            return obj

def input(path):

    with open(path, "rb") as f:
        source = FrozenJSON(json.load(f))
        entries = source.log.entries
        valid_entries = [e for e in entries if e.response.content.mimeType in SUPPORT_MIME_TYPES]
    return valid_entries


def parse_request(request):
    """Parse request data from an API"""
    method = request.method.lower()
    path = urlparse(request.url).path
    parameters = []
    for query in request.queryString:
        parameters.append({
            "in": "query",
            "name": query.name,
            "type": "integer" if query.value.isdigit() else "string",
            # "example": query.value
            "description": "",
            "required": True
        })
    return dict(path=path, method=method, parameters=parameters)
    


def parse_response(response):
    """Parse response data from an API"""
    status = response.status
    consumes = [response.content.mimeType]
    schema = json.loads(response.content.text, cls=YAMLSchemaDecoder)
    return dict(status=status, consumes=consumes, schema=schema)


def parse(entries):
    """parse data from har file"""
    paths = OrderedDict()
    for entry in entries:
        req = parse_request(entry.request)
        res = parse_response(entry.response)
        paths[req["path"]] = {
            req["method"]: OrderedDict(
                tags=["API Tag"],
                summary="API Summary",
                description="API Description",
                consumes=res["consumes"],
                parameters=req["parameters"],
                responses={
                    res["status"]: {
                        "description": "",
                        "schema": res["schema"]
                    }
                }
            )
        }
    return paths
    
        

def output(path, data):
    with open(path, "w") as f:
        yaml.dump(data, f, Dumper=Dumper, default_flow_style=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='convert har to swagger')
    parser.add_argument('-i', type=str, required=True, help='input har file')
    parser.add_argument('-o', type=str, default="swagger.yaml",
                        help='output swagger file(yaml format), default swagger.yaml')

    args = parser.parse_args()
    paths = parse(input(args.i))
    swagger = OrderedDict(
        swagger="2.0",
        info=dict(
            description="API Document",
            version="1.0.0.0",
            title="API",
            contact=dict(email="hugoxia@126.com")
        ),
        host="127.0.0.1:80",
        tags=[dict(name="API Tag", description="API Description")],
        # schemas=["https", "http"],
        paths=paths
    )
    output(args.o, swagger)