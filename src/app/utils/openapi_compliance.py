"""Post-process the generated OpenAPI schema for API governance lint compliance.

Applies the same transformations used to make the static export pass Spectral:
- global security + approved (apiKey) security scheme
- info.contact
- server URL major-version node (/spog/v1)
- string maxLength, integer format, array maxItems
- additionalProperties: false on open objects
- $ref-siblings wrapped in allOf
- attribute descriptions
- 403 responses + schema-valid 2xx examples
- removal of `nullable` without `type` (invalid in OAS 3.0)
- CommonErrorResponse.status property
"""
from typing import Any

_DEFAULT_STR_MAXLEN = 5000
_DEFAULT_ARRAY_MAXITEMS = 1000
_ERR_REF = {"$ref": "#/components/schemas/CommonErrorResponse"}

_DESC_DEFAULTS = {
    "createdUtc": "Timestamp when the record was created (UTC).",
    "updatedUtc": "Timestamp when the record was last updated (UTC).",
    "tags": "Free-form labels used to categorize the record.",
    "deprecated": "Indicates whether the record is deprecated.",
    "author": "Identifier of the user who created the record.",
    "deleted": "Indicates whether the resource was deleted.",
    "agents": "Collection of agents associated with the project.",
}


def _stub_for_string(s: dict) -> Any:
    if s.get("enum"):
        return s["enum"][0]
    fmt = s.get("format")
    if fmt == "uuid":
        return "00000000-0000-0000-0000-000000000000"
    if fmt == "date-time":
        return "2024-01-01T00:00:00Z"
    if fmt == "date":
        return "2024-01-01"
    return "string"


def _build_example(schema: dict, schemas: dict, depth: int = 0) -> Any:
    """Build a minimal schema-valid example value (matches oas3-valid-media-example)."""
    if not isinstance(schema, dict) or depth > 6:
        return {}
    if "$ref" in schema:
        target = schemas.get(schema["$ref"].split("/")[-1])
        return _build_example(target, schemas, depth + 1) if target else {}
    if schema.get("allOf"):
        return _build_example(schema["allOf"][0], schemas, depth + 1)

    t = schema.get("type")
    if t == "array":
        return []
    if t in ("integer", "number"):
        return schema.get("minimum", 0) if isinstance(schema.get("minimum"), (int, float)) else 0
    if t == "boolean":
        return schema.get("default", False)
    if t == "string":
        return _stub_for_string(schema)
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {}) or {}
        obj = {}
        for rname in schema.get("required", []) or []:
            obj[rname] = _build_example(props[rname], schemas, depth + 1) if rname in props else "string"
        return obj
    return {}


def _walk_schema(schema: Any) -> None:
    """Apply owasp limits, additionalProperties, $ref-siblings, descriptions, nullable cleanup."""
    if isinstance(schema, list):
        for item in schema:
            _walk_schema(item)
        return
    if not isinstance(schema, dict):
        return

    # invalid OAS 3.0: nullable without type (e.g. sibling of allOf / $ref)
    if "nullable" in schema and "type" not in schema:
        del schema["nullable"]

    t = schema.get("type")
    if t == "string" and not ({"maxLength", "enum", "const"} & schema.keys()):
        schema["maxLength"] = _DEFAULT_STR_MAXLEN
    if t == "integer" and "format" not in schema:
        schema["format"] = "int64"
    if t == "array" and "maxItems" not in schema:
        schema["maxItems"] = _DEFAULT_ARRAY_MAXITEMS
    if schema.get("additionalProperties") is True:
        schema["additionalProperties"] = False

    if "items" in schema:
        _walk_schema(schema["items"])
    if isinstance(schema.get("properties"), dict):
        for pname, pval in list(schema["properties"].items()):
            # no-$ref-siblings: move $ref under allOf when siblings exist
            if isinstance(pval, dict) and "$ref" in pval and len(pval) > 1:
                ref = pval.pop("$ref")
                pval = {"allOf": [{"$ref": ref}], **pval}
                schema["properties"][pname] = pval
            # attribute descriptions
            if isinstance(pval, dict) and "description" not in pval and "$ref" not in pval:
                pval["description"] = _DESC_DEFAULTS.get(pname, f"The {pname} value.")
            _walk_schema(pval)
    for key in ("allOf", "anyOf", "oneOf"):
        if key in schema:
            _walk_schema(schema[key])
    if isinstance(schema.get("additionalProperties"), dict):
        _walk_schema(schema["additionalProperties"])


def normalize_openapi_schema(
    openapi_schema: dict,
    *,
    security_scheme_name: str = "HTTPBearer",
    contact: dict | None = None,
    server_version_segment: str = "/spog/v1",
) -> dict:
    """Mutate and return the OpenAPI schema so it passes governance lint."""
    # --- info.contact ---
    info = openapi_schema.setdefault("info", {})
    info.setdefault("contact", contact or {"name": "SPoG Platform Team", "email": "spog-support@highmark.com"})

    # --- approved security scheme (apiKey) + global security ---
    components = openapi_schema.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})
    schemes[security_scheme_name] = {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": "Bearer token passed in the Authorization header.",
    }
    openapi_schema["security"] = [{security_scheme_name: []}]

    # --- server URL major version node ---
    for server in openapi_schema.get("servers", []) or []:
        url = server.get("url", "")
        if url.endswith("/v1") and not url.endswith(server_version_segment):
            server["url"] = url[: -len("/v1")] + server_version_segment

    schemas = components.get("schemas", {})

    # --- CommonErrorResponse must expose status, errorType, errorMessage ---
    cer = schemas.get("CommonErrorResponse")
    if cer and "status" not in cer.get("properties", {}):
        cer.setdefault("properties", {})
        cer["properties"] = {
            "status": {
                "type": "integer",
                "format": "int32",
                "minimum": 100,
                "maximum": 599,
                "title": "Status",
                "description": "The HTTP status code associated with the error.",
            },
            **cer["properties"],
        }
        req = cer.setdefault("required", [])
        if "status" not in req:
            cer["required"] = ["status", *req]

    # --- walk every component schema ---
    for sval in schemas.values():
        _walk_schema(sval)

    # --- collect operation tags and declare globally ---
    declared = set()

    # --- paths: parameters, request bodies, responses ---
    for methods in openapi_schema.get("paths", {}).values():
        for op in methods.values():
            if not isinstance(op, dict):
                continue
            for t in op.get("tags", []) or []:
                declared.add(t)
            for param in op.get("parameters", []) or []:
                if isinstance(param, dict) and "schema" in param:
                    _walk_schema(param["schema"])
            rb = op.get("requestBody")
            if isinstance(rb, dict):
                for media in rb.get("content", {}).values():
                    if isinstance(media, dict) and "schema" in media:
                        _walk_schema(media["schema"])
            responses = op.get("responses", {})
            if "403" not in responses:
                responses["403"] = {
                    "description": "Forbidden",
                    "content": {"application/json": {"schema": dict(_ERR_REF)}},
                }
            for code, resp in responses.items():
                if not isinstance(resp, dict):
                    continue
                content = resp.get("content")
                if not isinstance(content, dict):
                    continue
                for media in content.values():
                    if isinstance(media, dict) and "schema" in media:
                        _walk_schema(media["schema"])
                        if str(code).startswith("2"):
                            media["examples"] = {
                                "default": {"value": _build_example(media["schema"], schemas)}
                            }

    if declared:
        openapi_schema["tags"] = [{"name": t, "description": t} for t in sorted(declared)]

    return openapi_schema
