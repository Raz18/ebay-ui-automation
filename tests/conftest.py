"""Test-level fixtures — data loading helpers."""

from __future__ import annotations

import os

from utils.data_loader import DataLoader


# --- Data helpers ---

def load_search_data():
    """Load search scenarios for parametrize (called at collection time)."""
    return DataLoader.load("data/search_data.json")


def load_credentials():
    """Load credentials with env-var override."""
    data = DataLoader.load("data/credentials.yaml")
    creds = data[0]
    return {
        "username": os.getenv("EBAY_USERNAME", creds.get("username", "")),
        "password": os.getenv("EBAY_PASSWORD", creds.get("password", "")),
    }
