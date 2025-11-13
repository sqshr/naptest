"""
Code to read ./config/paths json file and support module command concatinattion

AKA my seclists isnt saved in /repos 
"""
import json
import os
from collections import ChainMap

# Support for legacy keys whilst moving modules over to new system.
LEGACY_KEYS = ("DIR", "HOST", "IP", "PORT", "PROTO")

class SafeDict(dict):
    # if key missing set to key and not freak out
    def missing_key(self, lookup_key):
        return "{" + lookup_key + "}"

    # required by format_map, delegates to snake_case helper
    def __missing__(self, lookup_key):
        return self.missing_key(lookup_key)


def normalise_keys(value):
    # recursively sets keys to lowercase. janky but works for now
    if isinstance(value, dict):
        result = {}
        for original_key, original_value in value.items():
            result[original_key.lower()] = normalise_keys(original_value)
        return result
    if isinstance(value, list):
        return [normalise_keys(item) for item in value]
    return value


def get_nested(mapping_dict, dotted_key):
    # fallback dotted lookup (not usually needed thanks to AttrDict)
    parts = dotted_key.lower().split(".")
    try:
        current = mapping_dict
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return "{" + dotted_key + "}"
        return current
    except Exception:
        return "{" + dotted_key + "}"


class AttrDict:
    def __init__(self, source_dict):
        self._source_dict = source_dict or {}

    def get_attribute(self, attr_name):
        # case-insensitive access to inner dict keys
        lookup = attr_name.lower()
        value = self._source_dict.get(lookup)
        if isinstance(value, dict):
            return AttrDict(value)
        if value is None:
            return "{" + attr_name + "}"
        return value

    # required for attribute-style lookup in format strings
    def __getattr__(self, attr_name):
        return self.get_attribute(attr_name)

    def __repr__(self):
        return f"AttrDict({self._source_dict!r})"


class NestedFormatter(dict):
    # format_map helper: look in maps, return AttrDict for dicts so .attr works
    def __init__(self, *maps):
        self._chain_maps = ChainMap(*maps)

    def missing_key(self, key):
        # direct lookup first
        for mapping in self._chain_maps.maps:
            if isinstance(mapping, dict) and key in mapping:
                value = mapping[key]
                if isinstance(value, dict):
                    return AttrDict(value)
                return value
        # fallback dotted lookup
        for mapping in self._chain_maps.maps:
            if isinstance(mapping, dict):
                value = get_nested(mapping, key)
                if not (isinstance(value, str) and value.startswith("{") and value.endswith("}")):
                    return value
        return "{" + key + "}"

    # default to missing_key
    def __missing__(self, key):
        return self.missing_key(key)


def load_paths_json(filename="paths.json"):
    base_path = os.path.dirname(os.path.realpath(__file__))
    root_path = os.path.realpath(os.path.join(base_path, ".."))
    file_path = os.path.realpath(os.path.join(root_path, "config", "paths.json"))

    with open(file_path, "r") as file:
        json_data = json.load(file)

    # support wrapper { "vars": { ... } }
    if isinstance(json_data, dict) and "vars" in json_data:
        json_data = json_data["vars"]

    return normalise_keys(json_data) if isinstance(json_data, dict) else {}


def render_cmd(template: str, builtins_map: dict, paths_map: dict) -> str:
    # render command template
    for legacy_key in LEGACY_KEYS:
        template = template.replace(legacy_key, "{" + legacy_key + "}")
    formatter = NestedFormatter(builtins_map or {}, paths_map or {})
    # pass the NestedFormatter directly so attribute lookup works /// This is messy
    return template.format_map(formatter)
