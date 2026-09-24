"""Security token helpers."""

from jobcome.utils.security_tokens import generate_token, hash_token


def test_hash_token_is_stable() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abcd")


def test_generate_token_unique() -> None:
    a = generate_token()
    b = generate_token()
    assert a != b
    assert len(a) >= 32
