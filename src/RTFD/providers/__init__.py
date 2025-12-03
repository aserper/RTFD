"""
Provider auto-discovery and registration.

This module automatically loads all providers from the providers/ directory
and makes them available for tool registration.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Dict, Type

from .base import BaseProvider, ProviderMetadata

# Registry of discovered providers
_provider_classes: Dict[str, Type[BaseProvider]] = {}


def discover_providers() -> Dict[str, Type[BaseProvider]]:
    """
    Auto-discover provider classes from the providers directory.

    Scans all .py files (except __init__.py and base.py) for classes
    that inherit from BaseProvider.

    Returns:
        Dict mapping provider names to provider classes
    """
    if _provider_classes:  # Return cached results
        return _provider_classes

    providers_dir = Path(__file__).parent

    for py_file in providers_dir.glob("*.py"):
        # Skip special files
        if py_file.name in ("__init__.py", "base.py"):
            continue

        # Import module using the current package name
        module_name = f"{__package__}.{py_file.stem}"
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            # Log warning but don't crash - defensive loading
            sys.stderr.write(f"Warning: Failed to import provider module {module_name}: {e}\n")
            continue

        # Find BaseProvider subclasses
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseProvider)
                and obj is not BaseProvider
                and obj.__module__ == module_name  # Defined in this module
            ):
                # Instantiate temporarily to get metadata
                try:
                    # Use a dummy http_client_factory for metadata extraction
                    temp_instance = obj(lambda: None)
                    metadata = temp_instance.get_metadata()
                    _provider_classes[metadata.name] = obj
                except Exception as e:
                    sys.stderr.write(f"Warning: Failed to load provider {name}: {e}\n")

    return _provider_classes


def get_provider_metadata_all() -> list[ProviderMetadata]:
    """Get metadata for all discovered providers."""
    providers = discover_providers()
    metadata_list = []

    for provider_class in providers.values():
        try:
            temp_instance = provider_class(lambda: None)
            metadata_list.append(temp_instance.get_metadata())
        except Exception:
            pass  # Skip providers that fail to instantiate

    return metadata_list
