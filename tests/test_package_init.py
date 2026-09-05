"""Package-init behavior for HA and standalone tooling imports."""

from __future__ import annotations

import builtins
import importlib
import sys

import pytest


def test_package_allows_api_import_when_homeassistant_missing() -> None:
    """Stand-alone tooling can import api/parser without Home Assistant installed."""
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name == "homeassistant" or name.startswith("homeassistant."):
            raise ModuleNotFoundError(name, name=name.split(".", 1)[0])
        return real_import(name, globals, locals, fromlist, level)

    for key in list(sys.modules):
        if key == "homeassistant" or key.startswith(
            ("homeassistant.", "custom_components.eversource_rates")
        ):
            del sys.modules[key]

    builtins.__import__ = guarded
    try:
        api = importlib.import_module("custom_components.eversource_rates.api")
        parser = importlib.import_module("custom_components.eversource_rates.parser")
        assert hasattr(api, "EversourceClient")
        assert hasattr(parser, "parse_supply_html")
    finally:
        builtins.__import__ = real_import
        for key in list(sys.modules):
            if key.startswith("custom_components.eversource_rates"):
                del sys.modules[key]
        importlib.import_module("custom_components.eversource_rates")


def test_package_init_reraises_unrelated_module_not_found() -> None:
    """Unrelated missing modules during HA import are not silently swallowed."""
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name == "homeassistant.config_entries":
            raise ModuleNotFoundError("some_unrelated_dep", name="some_unrelated_dep")
        return real_import(name, globals, locals, fromlist, level)

    for key in list(sys.modules):
        if key.startswith("custom_components.eversource_rates"):
            del sys.modules[key]

    builtins.__import__ = guarded
    try:
        with pytest.raises(ModuleNotFoundError, match="some_unrelated_dep"):
            importlib.import_module("custom_components.eversource_rates")
    finally:
        builtins.__import__ = real_import
        for key in list(sys.modules):
            if key.startswith("custom_components.eversource_rates"):
                del sys.modules[key]
        importlib.import_module("custom_components.eversource_rates")
