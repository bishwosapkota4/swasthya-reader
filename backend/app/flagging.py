"""Deterministic abnormal-value flagging. The model never decides low/normal/high."""
import re

_NUM = r"(\d+(?:\.\d+)?)"
_SEX_LABEL = re.compile(r"(?:^|[,;])\s*(male|female|m|f)\s*:\s*", re.I)


def _to_float(text: str):
    m = re.search(_NUM, str(text).replace(",", ""))
    return float(m.group(1)) if m else None


def _simple_range(rng: str):
    s = str(rng).replace(",", "").replace("–", "-").replace("—", "-").strip()

    m = re.fullmatch(rf"{_NUM}\s*-\s*{_NUM}", s)
    if m:
        return float(m.group(1)), float(m.group(2))

    m = re.fullmatch(rf"(?:<=|<|up to|upto|less than)\s*{_NUM}", s, re.I)
    if m:
        return None, float(m.group(1))

    m = re.fullmatch(rf"(?:>=|>|more than|greater than)\s*{_NUM}", s, re.I)
    if m:
        return float(m.group(1)), None

    return None


def parse_range(rng: str, sex: str | None = None):
    """Return (low, high) where either may be None, or None if unparseable."""
    if not rng:
        return None

    text = str(rng).strip()
    sex_ranges = list(_SEX_LABEL.finditer(text))
    if sex_ranges:
        normalized_sex = str(sex or "").strip().lower()
        if normalized_sex not in {"m", "male", "f", "female"}:
            return None
        wanted = "male" if normalized_sex in {"m", "male"} else "female"
        for index, match in enumerate(sex_ranges):
            label = match.group(1).lower()
            label = "male" if label in {"m", "male"} else "female"
            if label != wanted:
                continue
            end = sex_ranges[index + 1].start() if index + 1 < len(sex_ranges) else len(text)
            return _simple_range(text[match.end():end].strip(" ,;"))
        return None

    # A colon indicates a label (for example, "Desirable:"). Multiple bands
    # without labels also fail the full match instead of selecting a band.
    if ":" in text:
        return None
    return _simple_range(text)


def flag_test(test: dict, patient_sex: str | None = None) -> dict:
    value = _to_float(test.get("value", ""))
    rng = parse_range(test.get("reference_range", ""), patient_sex)
    status = "unknown"
    if value is not None and rng is not None:
        low, high = rng
        if low is not None and value < low:
            status = "low"
        elif high is not None and value > high:
            status = "high"
        else:
            status = "normal"

    # "far outside" = more than 25% beyond the nearest bound
    severity = "none"
    if status in ("low", "high") and rng is not None:
        low, high = rng
        bound = low if status == "low" else high
        if bound:
            deviation = abs(value - bound) / abs(bound)
            severity = "marked" if deviation > 0.25 else "mild"

    return {**test, "status": status, "severity": severity}


def flag_all(tests: list[dict], patient_sex: str | None = None) -> list[dict]:
    return [flag_test(t, patient_sex) for t in tests]


def needs_doctor_soon(flagged: list[dict]) -> bool:
    return any(t["severity"] == "marked" for t in flagged)
