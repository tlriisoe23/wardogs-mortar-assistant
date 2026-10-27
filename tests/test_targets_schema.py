import json
import os

def test_targets_json_schema():
    targets_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'targets.json')
    assert os.path.exists(targets_file), "data/targets.json must exist"

    with open(targets_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert isinstance(data, list), "Root should be a list"

    valid_categories = {"sniper_tower", "fob_haven", "chokepoint", "spawn_funnel"}
    seen_ids = set()

    for i, item in enumerate(data):
        assert isinstance(item, dict), f"Item at index {i} should be a dictionary"

        # Required keys and their types
        assert "id" in item, f"Missing 'id' at index {i}"
        assert isinstance(item["id"], str), f"'id' should be string at index {i}"

        assert item["id"] not in seen_ids, f"Duplicate 'id' found: {item['id']}"
        seen_ids.add(item["id"])

        assert "map" in item, f"Missing 'map' in {item['id']}"
        assert isinstance(item["map"], str), f"'map' should be string in {item['id']}"

        assert "name" in item, f"Missing 'name' in {item['id']}"
        assert isinstance(item["name"], str), f"'name' should be string in {item['id']}"

        assert "category" in item, f"Missing 'category' in {item['id']}"
        assert item["category"] in valid_categories, f"Invalid category: {item['category']} in {item['id']}"

        assert "x" in item, f"Missing 'x' in {item['id']}"
        assert type(item["x"]) in (int, float), f"'x' should be number in {item['id']}"

        assert "y" in item, f"Missing 'y' in {item['id']}"
        assert type(item["y"]) in (int, float), f"'y' should be number in {item['id']}"

        assert "notes" in item, f"Missing 'notes' in {item['id']}"
        assert isinstance(item["notes"], str), f"'notes' should be string in {item['id']}"

        assert "voice_triggers" in item, f"Missing 'voice_triggers' in {item['id']}"
        assert isinstance(item["voice_triggers"], list), f"'voice_triggers' should be list in {item['id']}"
        for trigger in item["voice_triggers"]:
            assert isinstance(trigger, str), f"Voice triggers must be strings in {item['id']}"
