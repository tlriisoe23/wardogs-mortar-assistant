import json
import os
import pytest

def test_targets_json_schema():
    targets_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'targets.json')
    assert os.path.exists(targets_file), "data/targets.json must exist"

    with open(targets_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert isinstance(data, list), "Root should be a list"

    valid_categories = {"sniper_tower", "fob_haven", "chokepoint", "spawn_funnel"}

    for item in data:
        assert isinstance(item, dict), "Each target should be a dictionary"

        # Required keys and their types
        assert "id" in item and isinstance(item["id"], str)
        assert "map" in item and isinstance(item["map"], str)
        assert "name" in item and isinstance(item["name"], str)

        assert "category" in item, "Missing 'category'"
        assert item["category"] in valid_categories, f"Invalid category: {item['category']}"

        assert "x" in item and isinstance(item["x"], (int, float))
        assert "y" in item and isinstance(item["y"], (int, float))

        assert "notes" in item and isinstance(item["notes"], str)

        assert "voice_triggers" in item and isinstance(item["voice_triggers"], list)
        for trigger in item["voice_triggers"]:
            assert isinstance(trigger, str), "Voice triggers must be strings"
