"""
function: convert har to swagger
author: hugo
"""

import json
import yaml
import argparse
import warnings

from collections import abc, OrderedDict
from urllib.parse import urlparse

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from yaml.representer import SafeRepresenter

_host, _schemas = "0.0.0.0:80", set()
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
            return OrderedDict(
                type="object",
                properties={k: self.parse_schema(v) for k, v in val.items()}
            )
        elif isinstance(val, abc.MutableSequence):
            if len(val) == 0:
                items = {}
            else:
                items = self.parse_schema(val[0])
            return OrderedDict(
                type="array",
                items=items
            )
        elif isinstance(val, int):
            return OrderedDict(
                type="integer",
                description="",
                example=val
            )
        elif isinstance(val, float):
            return OrderedDict(
                type="number",
                description="",
                example=val
            )
        elif isinstance(val, str):
            return OrderedDict(
                type="string",
                description="",
                example=val
            )
        elif isinstance(val, bool):
            return OrderedDict(
                type="boolean",
                desciption="",
                example=val
            )
        elif isinstance(val, type(None)):
            return OrderedDict(
                type="string",
                # nullable=True,
                # desciption="",
                example=val
            )
        else:
            raise ValueError("Not support type: %s, value: %s" % (type(val), val))


yaml_schema_decoder = YAMLSchemaDecoder()


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


def input_file(path):

    with open(path, "rb") as f:
        source = FrozenJSON(json.load(f))
        entries = source.log.entries
        valid_entries = [e for e in entries if e.response.content.mimeType in SUPPORT_MIME_TYPES]
    return valid_entries


def parse_request(request):
    """Parse request data from an API"""
    global _host, _schemas
    method = request.method.lower()
    parse_result = urlparse(request.url)
    _host = parse_result.netloc
    _schemas.add(parse_result.scheme)
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
    if request.bodySize > 0:
        post_data = request.postData
        mime_type = post_data.mimeType.split(";")[0]
        consumes = [mime_type]
        if "json" in mime_type:
            schema = json.loads(post_data.text, cls=YAMLSchemaDecoder)
            parameters.append({
                "in": "body",
                "name": "request-body",
                "description": "",
                "schema": schema
            })
        elif "form" in mime_type:
            for param in post_data.params:
                parameters.append({
                    "in": "formData",
                    "name": param.name,
                    "type": yaml_schema_decoder.parse_schema(param.value)["type"],
                    "description": ""
                })
        else:
            warnings.warn("not support mimetype %s" % mime_type)
    else:
        consumes = []
    return dict(path=parse_result.path, method=method, consumes=consumes, parameters=parameters)
    

def parse_response(response):
    """Parse response data from an API"""
    status = response.status
    produces = [response.content.mimeType]
    schema = json.loads(response.content.text, cls=YAMLSchemaDecoder)
    return dict(status=status, produces=produces, schema=schema)


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
                produces=res["produces"],
                consumes=req["consumes"],
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
    

def output_file(path, data, format):
    with open(path, "w") as f:
        if format == "yaml":
            yaml.dump(data, f, Dumper=Dumper, default_flow_style=False)
        else:
            json.dump(data, f)


def main():
    parser = argparse.ArgumentParser(description='convert har to swagger')
    parser.add_argument('-i', type=str, required=True, help='input har file')
    parser.add_argument('-o', type=str, default="swagger",
                        help='output swagger file, default is swagger')
    parser.add_argument('-f', type=str, default="yaml", choices=["yaml", "json"],
                        help='output format[yaml|json], default is yaml')
    parser.add_argument('--openapi', type=int, default=2, choices=[2, 3],
                        help='OpenAPI Specification[2|3], default is 2')
    args = parser.parse_args()
    if args.openapi == 3:
        raise Exception("Not support OpenAPI 3.0")
    paths = parse(input_file(args.i))
    swagger = OrderedDict(
        swagger="2.0",
        info=dict(
            description="API Document",
            version="1.0.0.0",
            title="API",
            contact=dict(email="api-developer@darker.com")
        ),
        host=_host,
        tags=[dict(name="API Tag", description="API Description")],
        schemas=list(_schemas),
        paths=paths
    )
    if args.o.endswith(".%s" % args.f):
        path = args.o
    else:
        path = "%s.%s" % (args.o, args.f)
    output_file(path, swagger, args.f)


if __name__ == "__main__":
    main()
