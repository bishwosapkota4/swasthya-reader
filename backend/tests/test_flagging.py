from backend.app.flagging import flag_test, parse_range


def test_plain_range_flags_low_normal_and_high():
    assert flag_test({"value": "9", "reference_range": "10 - 20"})["status"] == "low"
    assert flag_test({"value": "15", "reference_range": "10 - 20"})["status"] == "normal"
    assert flag_test({"value": "21", "reference_range": "10 - 20"})["status"] == "high"


def test_single_sided_ranges_are_supported():
    assert flag_test({"value": "180", "reference_range": "<200"})["status"] == "normal"
    assert flag_test({"value": "201", "reference_range": "<200"})["status"] == "high"
    assert flag_test({"value": "40", "reference_range": ">=40"})["status"] == "normal"
    assert flag_test({"value": "39", "reference_range": ">=40"})["status"] == "low"
    assert flag_test({"value": "100", "reference_range": "Up to 100"})["status"] == "normal"


def test_comma_formatted_numbers_and_small_values_are_numeric():
    assert parse_range("4,00,000 - 5,00,000") == (400000.0, 500000.0)
    assert flag_test({"value": "4,50,000", "reference_range": "4,00,000 - 5,00,000"})["status"] == "normal"
    assert flag_test({"value": "0.005", "reference_range": "<0.01"})["status"] == "normal"
    assert flag_test({"value": "0.02", "reference_range": "<0.01"})["status"] == "high"


def test_qualitative_and_dash_values_are_unknown():
    assert flag_test({"value": "Negative", "reference_range": "Negative"})["status"] == "unknown"
    assert flag_test({"value": "-", "reference_range": "10 - 20"})["status"] == "unknown"


def test_labeled_multi_band_range_is_unknown():
    test = {
        "name": "Total cholesterol",
        "value": "180",
        "reference_range": "Desirable: <200, Borderline: 200-239, High: >=240",
    }
    assert flag_test(test)["status"] == "unknown"
    assert flag_test(test)["status"] != "low"


def test_sex_specific_ranges_use_matching_band():
    reference_range = "M: 13 - 17, F: 12 - 16"
    assert flag_test({"value": "13", "reference_range": reference_range}, "M")["status"] == "normal"
    assert flag_test({"value": "12", "reference_range": reference_range}, "F")["status"] == "normal"
    assert flag_test({"value": "12", "reference_range": reference_range}, "M")["status"] == "low"
    assert flag_test({"value": "17", "reference_range": reference_range}, "F")["status"] == "high"
    assert flag_test({"value": "13", "reference_range": reference_range})["status"] == "unknown"
