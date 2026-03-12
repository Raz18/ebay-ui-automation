"""Data loader for test parametrization — supports JSON, YAML."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from utils.logger import get_logger


logger = get_logger(__name__)

# Resolve project root once (parent of utils/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class DataLoader:
    """Load test data from JSON, YAML, or CSV files.

    All paths are resolved relative to the project root.
    """

    @staticmethod
    def load(filepath: str) -> Any:
        """Load test data from a file, auto-detecting format by extension."""
        path = _PROJECT_ROOT / filepath
        if not path.exists():
            raise FileNotFoundError(
                f"Data file not found: {path} "
                f"(resolved from '{filepath}' relative to {_PROJECT_ROOT})"
            )

        suffix = path.suffix.lower()
        logger.info("Loading data from %s (format: %s)", path, suffix)

        if suffix == ".json":
            data = DataLoader._load_json(path)
        elif suffix in (".yaml", ".yml"):
            data = DataLoader._load_yaml(path)
        else:
            raise ValueError(
                f"Unsupported file format '{suffix}'. "
                f"Supported: .json, .yaml, .yml"
            )

        DataLoader._validate(data, filepath)
        logger.info("Loaded %d test scenarios from %s", len(data), filepath)
        return data

    @staticmethod
    def _load_json(path: Path) -> Any:
        """Load data from a JSON file."""
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_yaml(path: Path) -> list[dict[str, Any]]:
        """Load data from a YAML file."""
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # YAML may return a single dict — wrap it in a list for consistency
        if isinstance(data, dict):
            return [data]
        return data

    @staticmethod
    def _validate(data: Any, filepath: str) -> None:
        """Validate that loaded data is not empty."""
        if not data:
            raise ValueError(f"Data from '{filepath}' is empty")
        if isinstance(data, list) and not all(isinstance(item, dict) for item in data):
            raise ValueError(
                f"All items in the list from '{filepath}' must be dictionaries"
            )
