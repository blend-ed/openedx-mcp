# coding=utf-8
"""
openedx-mcp: an Open edX plugin that exposes staff/superuser admin operations
as a set of REST facade endpoints for an MCP (Model Context Protocol) server.

Pure Open edX: every operation is implemented against native openedx-platform
Python APIs. No third-party stack (no Hasura, no external identity, no org
multi-tenancy). Authorization is Django's own is_staff / is_superuser.

Installs into BOTH the LMS and the CMS process via the standard Open edX
djangoapp plugin entry points, because course-authoring operations must run in
the CMS (they touch the modulestore) while people/access/analytics run in the LMS.
"""
from setuptools import find_packages, setup

setup(
    name="openedx-mcp",
    version="0.1.1",
    description="Open edX admin operations exposed as an MCP facade for staff/superusers (Ulmo)",
    long_description=__doc__,
    author="Open edX MCP contributors",
    license="AGPL-3.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    python_requires=">=3.11",
    install_requires=[
        "Django>=4.2",
        "djangorestframework",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    entry_points={
        # IMPORTANT: these entry point groups must match edx-platform's.
        # https://github.com/openedx/edx-platform/blob/open-release/ulmo.master/setup.py
        "lms.djangoapp": [
            "openedx_mcp = openedx_mcp.apps:MCPLmsConfig",
        ],
        "cms.djangoapp": [
            "openedx_mcp = openedx_mcp.apps:MCPCmsConfig",
        ],
    },
)
