"""
Course authoring — thin wrappers over native Studio/CMS APIs. CMS PROCESS ONLY:
every call here touches the modulestore, which is writable only in the CMS.
Served under /api/mcp/cms/. A User object is required for the access checks.

Content hierarchy: course > chapter > sequential > vertical > component.
Everything created lands on the DRAFT branch; publish to expose to learners.
"""
from opaque_keys.edx.keys import CourseKey, UsageKey

# --- outline / xblock CRUD ---

def read_outline(user, course_id):
    """Full draft tree. Native: modulestore().get_course + create_xblock_info."""
    from cms.djangoapps.contentstore.xblock_storage_handlers.view_handlers import create_xblock_info
    from xmodule.modulestore.django import modulestore
    course = modulestore().get_course(CourseKey.from_string(course_id), depth=None)
    if course is None:
        return None
    return create_xblock_info(course, include_child_info=True, course_outline=False)


def create_block(user, parent_locator, category, display_name=None, boilerplate=None):
    """Native: xblock_storage_handlers.create_xblock.create_xblock."""
    from cms.djangoapps.contentstore.xblock_storage_handlers.create_xblock import create_xblock
    block = create_xblock(parent_locator=parent_locator, user=user, category=category,
                          display_name=display_name, boilerplate=boilerplate)
    return {"locator": str(block.location), "category": category,
            "display_name": block.display_name}


def create_block_tree(user, parent_locator, nodes):
    """Create a whole subtree in one call. `nodes` is a list of:
        {"category": "chapter", "display_name": "...", "data"?: "...",
         "metadata"?: {...}, "children"?: [ ...same shape... ]}
    Returns the created tree with locators. Leaf `data`/`metadata` are applied via
    _save_xblock after creation. Draft only — publish separately."""
    created = []
    for node in nodes or []:
        block = create_block(user, parent_locator, node["category"],
                             node.get("display_name"), node.get("boilerplate"))
        loc = block["locator"]
        if node.get("data") or node.get("metadata") or node.get("fields"):
            update_block(user, loc, data=node.get("data"),
                        metadata=node.get("metadata"), fields=node.get("fields"))
        child = node.get("children")
        block["children"] = create_block_tree(user, loc, child)["created"] if child else []
        created.append(block)
    return {"parent_locator": parent_locator, "created": created}


def update_block(user, locator, data=None, metadata=None, fields=None, publish=None):
    """Native: view_handlers._save_xblock. publish ∈ None|'make_public'|'republish'|
    'discard_changes'."""
    from cms.djangoapps.contentstore.xblock_storage_handlers.view_handlers import _save_xblock
    from xmodule.modulestore.django import modulestore
    xblock = modulestore().get_item(UsageKey.from_string(locator))
    _save_xblock(user, xblock, data=data, metadata=metadata, fields=fields,
                 publish=publish)
    return {"locator": locator, "saved": True, "publish": publish}


def publish_block(user, locator):
    """Native: modulestore().publish(location, user_id)."""
    from xmodule.modulestore.django import modulestore
    key = UsageKey.from_string(locator)
    modulestore().publish(key, user.id)
    return {"published": str(key)}


def delete_block(user, locator):
    """Native: view_handlers._delete_item(usage_key, user)."""
    from cms.djangoapps.contentstore.xblock_storage_handlers.view_handlers import _delete_item
    key = UsageKey.from_string(locator)
    _delete_item(key, user)
    return {"deleted": str(locator)}


# --- settings / details / grading ---

def update_course_settings(user, course_id, details=None, grading=None, advanced=None):
    """Apply schedule/pacing (details), grading policy, and/or advanced settings.
    Native: CourseDetails / CourseGradingModel / CourseMetadata update_from_json."""
    key = CourseKey.from_string(course_id)
    result = {}
    if details:
        from openedx.core.djangoapps.models.course_details import CourseDetails
        CourseDetails.update_from_json(key, details, user)
        result["details"] = "updated"
    if grading:
        from cms.djangoapps.models.settings.course_grading import CourseGradingModel
        CourseGradingModel.update_from_json(key, grading, user)
        result["grading"] = "updated"
    if advanced:
        from cms.djangoapps.models.settings.course_metadata import CourseMetadata
        from xmodule.modulestore.django import modulestore
        block = modulestore().get_course(key)
        _, errors = CourseMetadata.validate_and_update_from_json(block, advanced, user)
        result["advanced"] = "updated" if not errors else {"errors": errors}
    return {"course_id": str(key), **result}
