from enum import Enum
from collections.abc import Collection
from datetime import datetime, timezone
from typing import Tuple, Dict

from pydantic import BaseModel
from firebase_admin.firestore import firestore


def is_non_string_collection(value) -> bool:
    """
    Check if a value is a collection but not a string.
    
    Strings are technically collections in Python, but we want to exclude them
    for Firestore update operations.
    
    Args:
        value: The value to check
        
    Returns:
        True if value is a collection (list, tuple, set, dict, etc.) but not a string
    """
    return isinstance(value, Collection) and not isinstance(value, str)

def get_firestore_update_dicts(update_model: BaseModel) -> Tuple[Dict, Dict]:
    """
    Given an `update_model` that is intended to provide optional updates
    for a similar model persisted in Firestore, return a `(updates_added, updates_removed)`
    tuple of dictionaries.

    `updates_added` contains updates for non-array properties and array operations involving
    `firestore.ArrayUnion`

    `updates_removed` contains updates for array operations involving `firestore.ArrayRemove`

    It is assumed that properties in `update_model` following the convention of
    `added_propertyName` and `removed_propertyName` are in relation to a `propertyName` property
    in the actual Firestore document being updated.
    """
    field_updates_added = {}
    field_updates_removed = {}
    updates = update_model.model_dump(exclude_unset=True, by_alias=False)

    for updated_key, updated_value in updates.items():
        # check if it's a Pydantic BaseModel first before checking is_collection
        if isinstance(updated_value, BaseModel):
            field_updates_added[updated_key] = updated_value.model_dump(exclude_none=True)
            continue

        is_collection = is_non_string_collection(updated_value)
        
        # hanlde array additions (added_*)
        if updated_key.startswith("added_") and is_collection:
            property_name = updated_key.split("added_", 1)[1]
            values_list = list(updated_value)
            # Convert enum instances to their values
            values_list = [v.value if isinstance(v, Enum) else v for v in values_list]
            field_updates_added[property_name] = firestore.ArrayUnion(values_list)
        
        # Handle array removals (removed_*)
        elif updated_key.startswith("removed_") and is_collection:
            property_name = updated_key.split("removed_", 1)[1]
            values_list = list(updated_value)
            # Convert enum instances to their values
            values_list = [v.value if isinstance(v, Enum) else v for v in values_list]
            field_updates_removed[property_name] = firestore.ArrayRemove(values_list)
        
        # Handle non-collection values (strings, ints, bools, enums, etc.)
        elif updated_value is not None and not is_collection:
            if isinstance(updated_value, Enum):
                field_updates_added[updated_key] = updated_value.value
            else:
                field_updates_added[updated_key] = updated_value
        
        # Handle collections (list, tuple, set, dict) that don't start with added_/removed_
        # (e.g., replacing an entire array field)
        elif is_collection and not updated_key.startswith("added_") and not updated_key.startswith("removed_"):
            # Handle plain dicts
            if isinstance(updated_value, dict):
                field_updates_added[updated_key] = updated_value
            else:
                #Handle lists, tuples, sets
                values_list = list(updated_value)
                values_list = [v.value if isinstance(v, Enum) else v for v in values_list]
                field_updates_added[updated_key] = values_list
    
    # Always add timestamp
    field_updates_added['updated_utc'] = datetime.now(timezone.utc)

    return field_updates_added, field_updates_removed
