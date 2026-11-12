"""Shared runtime checks for JSON values and typed models."""

from functools import cache
from math import isfinite
from types import UnionType
from typing import Literal, Union, get_args, get_origin, get_type_hints

from corpus.errors import CorpusError


def validate_json(value: object, field: str) -> None:
    if value is None or type(value) in (str, int, bool):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise CorpusError(field, "JSON numbers must be finite")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            validate_json(child, f"{field}[{index}]")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CorpusError(field, "JSON object keys must be strings")
            validate_json(child, f"{field}.{key}")
        return
    raise CorpusError(field, "unsupported JSON value type")


def minimum(value: int | None, minimum: int, field: str) -> None:
    if value is not None and value < minimum:
        raise CorpusError(field, f"expected at least {minimum}")


@cache
def _fields(model: type) -> dict[str, object]:
    return get_type_hints(model)


def validate_type(value: object, annotation: object, field: str) -> None:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        if not any(type(value) is type(v) and value == v for v in args):
            raise CorpusError(field, f"expected one of {args}")
    elif origin in (Union, UnionType):
        _union(value, args, field)
    elif origin in (list, dict):
        _container(value, origin, args, field)
    elif isinstance(annotation, type) and hasattr(
        annotation, "__required_keys__"
    ):
        _record(value, annotation, field)
    elif annotation is not object and type(value) is not annotation:
        raise CorpusError(field, f"expected {annotation}")


def _container(
    value: object, origin: type, args: tuple[object, ...], field: str
) -> None:
    if origin is list:
        if not isinstance(value, list):
            raise CorpusError(field, "expected array")
        for index, item in enumerate(value):
            validate_type(item, args[0], f"{field}[{index}]")
    else:
        if not isinstance(value, dict):
            raise CorpusError(field, "expected object")
        for key, item in value.items():
            validate_type(key, args[0], field)
            validate_type(item, args[1], f"{field}.{key}")


def _union(value: object, choices: tuple[object, ...], field: str) -> None:
    non_null = tuple(item for item in choices if item is not type(None))
    if type(None) in choices and len(non_null) == 1:
        if value is None:
            return
        validate_type(value, non_null[0], field)
        return
    for choice in choices:
        try:
            validate_type(value, choice, field)
        except CorpusError:
            continue
        return
    raise CorpusError(field, "value does not match allowed types")


def _record(value: object, model: type, field: str) -> None:
    if not isinstance(value, dict):
        raise CorpusError(field, "expected object")
    fields = _fields(model)
    for name, annotation in fields.items():
        child = f"{field}.{name}" if field else name
        if name not in value:
            raise CorpusError(child, "required field is missing")
        validate_type(value[name], annotation, child)
    for name in value:
        if name not in fields:
            child = f"{field}.{name}" if field else str(name)
            raise CorpusError(child, "unknown field")
