from app.pii import mask


def test_masks_email_and_phone():
    text, found = mask("Call me at 054-763-1234 or write to dana.levi@orbit.com please")
    assert "dana.levi@orbit.com" not in text and "054-763-1234" not in text
    assert "[EMAIL]" in text and "[PHONE]" in text
    assert found == ["email", "phone"]


def test_masks_card_and_national_id():
    text, found = mask("My card 4580 1234 5678 9012 was charged, ID 123456782")
    assert "4580" not in text and "123456782" not in text
    assert set(found) == {"credit_card", "national_id"}


def test_masks_iban():
    text, found = mask("New account: IL62 0108 0000 0009 9999 999")
    assert "IL62" not in text
    assert "iban" in found


def test_leaves_normal_numbers_alone():
    original = "I have 8 vacation days, my salary was $800 lower in October 2026, room 3"
    text, found = mask(original)
    assert text == original
    assert found == []
