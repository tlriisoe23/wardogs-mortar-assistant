import pytest

def add_tests_to_file():
    with open("tests/test_mortar_calc.py", "a") as f:
        f.write("\n\ndef test_mortar_calculator_finite_bounds():\n")
        f.write("    from mortar_calc import MortarCalculator\n")
        f.write("    import math\n")
        f.write("    with pytest.raises(ValueError, match=\"finite\"):\n")
        f.write("        MortarCalculator(float('inf'), 0)\n")
        f.write("    calc = MortarCalculator(0, 0)\n")
        f.write("    with pytest.raises(ValueError, match=\"finite\"):\n")
        f.write("        calc.adjust_relative(float('nan'), 0)\n")
        f.write("    with pytest.raises(ValueError, match=\"finite\"):\n")
        f.write("        calc.adjust_missed_shot(0, float('-inf'))\n")
        f.write("    with pytest.raises(ValueError, match=\"finite\"):\n")
        f.write("        calc.adjust_impact_point(float('nan'), float('inf'))\n")

if __name__ == "__main__":
    add_tests_to_file()
