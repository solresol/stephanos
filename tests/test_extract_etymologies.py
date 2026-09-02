import pytest

from extract_etymologies import validate_etymologies


def test_validate_etymologies_accepts_complete_result():
    result = [{
        "greek_text": "ἀπὸ τοῦ βασιλέως",
        "english_translation": "from the king",
        "category": "EPONYM_PERSON",
    }]

    assert validate_etymologies(result) is result


def test_validate_etymologies_rejects_missing_translation_before_insert():
    result = [{
        "greek_text": "ἀπὸ τοῦ βασιλέως",
        "category": "EPONYM_PERSON",
    }]

    with pytest.raises(
        ValueError,
        match="etymology 0 has missing or empty fields: english_translation",
    ):
        validate_etymologies(result)


def test_validate_etymologies_rejects_invalid_category():
    result = [{
        "greek_text": "ἀπὸ τοῦ βασιλέως",
        "english_translation": "from the king",
        "category": "OTHER",
    }]

    with pytest.raises(ValueError, match="etymology 0 has invalid category: OTHER"):
        validate_etymologies(result)
