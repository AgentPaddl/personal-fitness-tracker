from request_id import sanitize_request_id


def test_well_formed_request_id_is_returned_unchanged():
    assert sanitize_request_id("well-formed-id-123") == "well-formed-id-123"


def test_none_request_id_is_replaced_with_generated_uuid():
    generated = sanitize_request_id(None)
    assert generated
    assert generated != "None"


def test_empty_request_id_is_replaced_with_generated_uuid():
    generated = sanitize_request_id("")
    assert generated


def test_malicious_request_id_is_replaced_with_generated_uuid():
    malicious = "not/safe; rm -rf /\n" + "x" * 200
    generated = sanitize_request_id(malicious)

    assert generated != malicious
    import re

    assert re.match(r"^[A-Za-z0-9-]{1,64}$", generated)


def test_overlong_request_id_is_replaced_with_generated_uuid():
    overlong = "a" * 65
    generated = sanitize_request_id(overlong)

    assert generated != overlong
