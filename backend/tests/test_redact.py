from PIL import Image

from redact import (black_out, find_pii, normalize_digits, redact_lines, redact_text, verhoeff_check_digit,
                    verhoeff_valid)


def make_aadhaar(prefix11: str) -> str:
    return prefix11 + verhoeff_check_digit(prefix11)


def test_verhoeff_known_values():
    # Classic Verhoeff examples: 236 -> check digit 3; 12345 -> 1
    assert verhoeff_check_digit("236") == "3"
    assert verhoeff_valid("2363")
    assert verhoeff_check_digit("12345") == "1"
    assert verhoeff_valid("123451")
    assert not verhoeff_valid("123452")


def test_valid_aadhaar_redacted_any_format():
    a = make_aadhaar("23456789012")
    for s in (a, f"{a[:4]} {a[4:8]} {a[8:]}", f"{a[:4]}-{a[4:8]}-{a[8:]}"):
        out, m = redact_text(f"Borrower ID {s} is attached")
        assert "[AADHAAR]" in out and a[-4:] not in out, s
        assert m[0].checksum_ok


def test_bad_checksum_ungrouped_no_keyword_is_kept():
    a = make_aadhaar("23456789012")
    wrong = a[:-1] + str((int(a[-1]) + 1) % 10)
    out, _ = redact_text(f"Account no {wrong}")
    assert wrong in out


def test_bad_checksum_but_keyword_or_grouped_still_redacted():
    a = make_aadhaar("34567890123")
    wrong = a[:-1] + str((int(a[-1]) + 1) % 10)
    assert "[AADHAAR]" in redact_text(f"Aadhaar: {wrong}")[0]
    assert "[AADHAAR]" in redact_text(f"আধার {wrong}")[0]
    assert "[AADHAAR]" in redact_text(f"ID {wrong[:4]} {wrong[4:8]} {wrong[8:]}")[0]


def test_bengali_and_devanagari_digits():
    a = make_aadhaar("45678901234")
    bn = a.translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))
    hi = a.translate(str.maketrans("0123456789", "०१२३४५६७८९"))
    assert normalize_digits(bn) == a
    assert "[AADHAAR]" in redact_text(f"নম্বর {bn}")[0]
    assert "[AADHAAR]" in redact_text(f"संख्या {hi}")[0]


def test_masked_aadhaar():
    assert "[AADHAAR]" in redact_text("Aadhaar XXXX XXXX 4321")[0]


def test_pan_phone_email():
    out, m = redact_text("PAN ABCPE1234F, call +91 98765 43210 or 9876543210, mail a.b@x.in")
    assert out.count("[PHONE]") == 2
    assert "[PAN]" in out and "[EMAIL]" in out
    assert "98765" not in out


def test_ocr_mangled_phone_near_keyword():
    # 11 digits (OCR added one): strict pattern fails, keyword fallback still hides it.
    assert "[PHONE]" in redact_text("ফোন. ৯৮৪৮০০১৮৪৫১")[0]
    assert "[PHONE]" in redact_text("Mobile: 98480 018451")[0]


def test_ocr_mangled_aadhaar_near_keyword():
    out = redact_text("Aadhaar: 2781 61584 9592, Mobile: +91 71034 13164")[0]
    assert out == "Aadhaar: [AADHAAR], Mobile: [PHONE]", out
    out = redact_text("आधार: 6627 0482 847 मोबाइल: 7252880957")[0]
    assert "[AADHAAR]" in out and "[PHONE]" in out and "847" not in out


def test_amounts_and_dates_not_redacted():
    text = "Loan of Rs 1,00,000 at 24% on 15-08-2026, 12 installments of Rs 9,456"
    out, m = redact_text(text)
    assert out == text and m == []


def test_redact_lines_spanning_words_and_boxes():
    a = make_aadhaar("56789012345")
    words = [{"text": "Aadhaar:", "box": [0, 0, 50, 10]},
             {"text": a[:4], "box": [60, 0, 30, 10]},
             {"text": a[4:8], "box": [100, 0, 30, 10]},
             {"text": a[8:], "box": [140, 0, 30, 10]},
             {"text": "Ph", "box": [180, 0, 15, 10]},
             {"text": "9876543210", "box": [200, 0, 60, 10]}]
    lines, boxes = redact_lines([{"id": 0, "words": words}])
    assert lines[0]["text"] == "Aadhaar: [AADHAAR] Ph [PHONE]"
    assert len(boxes) == 4
    img = black_out(Image.new("RGB", (300, 20), "white"), boxes)
    assert img.getpixel((110, 5)) == (0, 0, 0)
    assert img.getpixel((25, 5)) == (255, 255, 255)


def test_find_pii_offsets_are_on_original():
    text = "ফোন ৯৮৭৬৫৪৩২১০"
    m = find_pii(text)
    assert m and text[m[0].start:m[0].end] == "৯৮৭৬৫৪৩২১০"
