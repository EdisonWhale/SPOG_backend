from copy import deepcopy
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, create_model, field_validator

from app.models.base.CustomBaseModel import CustomBaseModel

BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


def partial_model(
    model: Type[BaseModelT],
    *optional_fields,
    name: Optional[str] = None,
    exclude_fields: Optional[tuple] = None,
) -> Type[BaseModelT]:
    """Generate a derived pydantic model from ``model``.

    Two transformations are supported and can be combined:

    - ``optional_fields``: field names that are made optional while preserving
      their validators/constraints. By default the derived model still
      **inherits** every other field from ``model``.
    - ``exclude_fields``: field names that are completely **removed** from the
      derived model (not merely optional). Used for request bodies that must
      not expose server-controlled fields such as ``author`` or ``id``; a
      client cannot set a field that does not exist on the model.

    When ``exclude_fields`` is given the model can no longer simply inherit from
    ``model`` (inheritance cannot drop a parent field). The derived model is
    rebuilt field-by-field on top of ``CustomBaseModel`` (so camelCase aliasing
    and the ``to_dict`` helpers are preserved) with the excluded fields left
    out, while every kept field's definition, constraints and
    ``field_validator``s are carried over.

    Parameters
    ----------
    model: Type[BaseModelT]
        The base Pydantic model to derive from.
    *optional_fields: str
        Field names to make optional.
    name: Optional[str], default=None
        Custom name for the generated model.
    exclude_fields: Optional[tuple], default=None
        Field names to remove entirely from the generated model.
    """
    optional_fields_set = set(optional_fields)
    exclude_set = set(exclude_fields or ())

    model_name = (
        name
        or f'Partial{model.__name__}{"".join(field.capitalize() for field in optional_fields)}'
    )

    # --- Path 1: no exclusions -> keep the original inherit-based behaviour. ---
    if not exclude_set:
        field_definitions = {}
        for field_name, field_info in model.model_fields.items():
            if field_name in optional_fields_set:
                # Fields with a default_factory are already optional; inherit them.
                if field_info.default_factory is not None:
                    continue
                optional_type = Optional[field_info.annotation]
                new_field = deepcopy(field_info)
                new_field.default = None
                field_definitions[field_name] = (optional_type, new_field)

        return create_model(
            model_name,
            __base__=model,
            __module__=model.__module__,
            **field_definitions,
        )

    # --- Path 2: exclusions -> rebuild without inheriting the dropped fields. ---
    field_definitions = {}
    for field_name, field_info in model.model_fields.items():
        if field_name in exclude_set:
            # Drop completely: do not re-declare on the derived model.
            continue

        new_field = deepcopy(field_info)
        if field_name in optional_fields_set and field_info.default_factory is None:
            annotation = Optional[field_info.annotation]
            new_field.default = None
        else:
            annotation = field_info.annotation
        field_definitions[field_name] = (annotation, new_field)

    # Carry over field_validators, re-wrapping each with ``field_validator`` so
    # the rebuilt model registers them. Validators are rescoped to the fields
    # that survive the exclusion; a validator that only targets excluded fields
    # is dropped (it would otherwise reference a field that no longer exists).
    validators = {}
    for dec_name, decorator in model.__pydantic_decorators__.field_validators.items():
        kept_targets = [f for f in decorator.info.fields if f not in exclude_set]
        if not kept_targets:
            continue
        # ``decorator.func`` is a bound classmethod (bound to the source model
        # as ``cls``). Take its underlying ``(cls, value)`` function and re-wrap
        # it as a fresh classmethod so it rebinds to the derived model.
        raw = getattr(decorator.func, "__func__", decorator.func)
        validators[dec_name] = field_validator(
            *kept_targets,
            mode=decorator.info.mode,
            check_fields=bool(decorator.info.check_fields),
        )(classmethod(raw))

    return create_model(
        model_name,
        __base__=CustomBaseModel,
        __module__=model.__module__,
        __validators__=validators or None,
        **field_definitions,
    )
