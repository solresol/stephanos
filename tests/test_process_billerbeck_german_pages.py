from process_billerbeck_german_pages import strip_nul_characters, validate_payload


def test_strip_nul_characters_from_nested_ocr_text():
    payload = {
        "status": "entries_present",
        "notes": "page\x00note",
        "entries": [
            {
                "lemma": "Πανδοσία",
                "german_text": "Kolonie aus Boiotien; \x00Fortsetzung",
            }
        ],
    }

    cleaned = strip_nul_characters(payload)

    assert cleaned["notes"] == "pagenote"
    assert cleaned["entries"][0]["german_text"] == "Kolonie aus Boiotien; Fortsetzung"
    validate_payload(cleaned, "billg_v1_337.jpg")
