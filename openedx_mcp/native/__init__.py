"""Thin wrappers over native Open edX Python APIs. No third-party stack.

Each module targets one process:
  analytics, enrollment, users, roles  -> LMS (read replica / student models)
  authoring                            -> CMS (modulestore writes)
Imports of platform code are lazy (inside functions) so the package imports
cleanly outside a running platform for unit tests / linting.
"""
