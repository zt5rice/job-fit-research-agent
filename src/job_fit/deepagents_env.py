"""Small import seam for verifying the DeepAgents runtime."""

from __future__ import annotations

import importlib.metadata

from deepagents import create_deep_agent


def deepagents_version() -> str:
    try:
        return importlib.metadata.version("deepagents")
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def deepagents_available() -> bool:
    return callable(create_deep_agent)

