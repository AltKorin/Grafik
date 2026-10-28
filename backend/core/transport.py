"""Bound untrusted JSON before database adapters or recursive domain code see it."""

import math

from django.conf import settings
from django.db import OperationalError, InterfaceError
from rest_framework.exceptions import ParseError, APIException
from rest_framework.parsers import JSONParser

from .domain_errors import DomainError

MAX_JSON_DEPTH = 32
MAX_JSON_VALUES = 50000


def storage_string(value):
    if not isinstance(value, str) or "\x00" in value:
        raise DomainError("Invalid storage text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise DomainError("Invalid storage text") from None
    return value


def bounded_json(value):
    # Iterative traversal also checks unknown metadata and keys. Rejecting only known
    # domain fields would still let JSONB receive invalid strings/nonfinite numbers.
    todo = [(value, 0)]
    count = 0
    while todo:
        item, depth = todo.pop()
        count += 1
        if depth > MAX_JSON_DEPTH or count > MAX_JSON_VALUES:
            raise DomainError("JSON structure exceeds limits")
        if isinstance(item, str):
            storage_string(item)
        elif isinstance(item, dict):
            for key, child in item.items():
                storage_string(key)
                todo.append((child, depth + 1))
        elif isinstance(item, list):
            todo.extend((child, depth + 1) for child in item)
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise DomainError("Invalid JSON number")
        elif item is not None and type(item) not in (bool, int):
            raise DomainError("Invalid JSON value")
    return value


class BoundedJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        # Read a bounded amount even when Content-Length is absent or false.
        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ParseError("Request body exceeds limits")
        import io

        try:
            return bounded_json(
                super().parse(io.BytesIO(raw), media_type, parser_context)
            )
        except (RecursionError, OverflowError):
            raise ParseError("JSON structure exceeds limits") from None
        except DomainError as error:
            raise ParseError(str(error)) from error


class DependencyUnavailable(APIException):
    status_code = 503
    default_detail = "Service dependency unavailable; retry later"
    default_code = "dependency_unavailable"


def exception_handler(error, context):
    from rest_framework.views import exception_handler as drf_exception_handler

    # Database outages fail closed, with an intentional service-unavailable response.
    # Never turn unexpected programming/validation bugs into a false success.
    if isinstance(error, (OperationalError, InterfaceError)):
        error = DependencyUnavailable()
    return drf_exception_handler(error, context)
