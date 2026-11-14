"""token 铸造：claims、grant、签名与有效期。"""

import time

import pytest

from companion.service.room.livekit_tokens import AGENT_IDENTITY_PREFIX, USER_IDENTITY_PREFIX, InvalidSignature, InvalidToken, MissingCredentials, TokenExpired, TokenMinter, agent_identity, decode_jwt, encode_jwt, user_identity

SECRET = "test-only-secret"
API_KEY = "test-api-key"


@pytest.fixture
def minter():
    return TokenMinter(api_key=API_KEY, api_secret=SECRET, ttl_sec=600)


def test_user_token_has_expected_claims_and_grant(minter):
    minted = minter.user_token("u1", "companion-abc")
    claims = decode_jwt(minted.token, SECRET)

    assert claims["iss"] == API_KEY
    assert claims["sub"] == "user:u1"
    assert claims["sub"].startswith(USER_IDENTITY_PREFIX)
    assert claims["nbf"] <= claims["exp"]
    assert claims["video"] == {
        "room": "companion-abc",
        "roomJoin": True,
        "canPublish": True,
        "canSubscribe": True,
        "canPublishData": True,
    }


def test_the_user_can_publish_data_because_text_chat_goes_over_data_streams(minter):
    """陪伴页的文字走 LiveKit 数据流，不是 HTTP。

    给 False 的后果特别隐蔽：界面上消息正常发出、显示在自己的气泡里，
    服务端却一个字节都收不到，agent 一句话不回，两边日志都干净——
    数据流发布在服务端被静默拒绝。
    """
    claims = decode_jwt(minter.user_token("u1", "companion-abc").token, SECRET)
    assert claims["video"]["canPublishData"] is True


def test_agent_token_can_publish_data(minter):
    claims = decode_jwt(minter.agent_token("a1", "companion-abc").token, SECRET)
    assert claims["sub"] == agent_identity("a1")
    assert claims["sub"].startswith(AGENT_IDENTITY_PREFIX)
    assert claims["video"]["canPublish"] is True
    assert claims["video"]["canPublishData"] is True


def test_expiry_is_ttl_from_issue_time(minter):
    now = 1_700_000_000.0
    minted = minter.user_token("u1", "companion-abc", now=now)
    claims = decode_jwt(minted.token, SECRET, now=now)
    assert claims["exp"] == int(now) + 600
    assert claims["nbf"] == int(now)


def test_wrong_secret_fails_verification(minter):
    token = minter.user_token("u1", "companion-abc").token
    with pytest.raises(InvalidSignature):
        decode_jwt(token, "not-the-secret")


def test_tampered_payload_fails_verification(minter):
    token = minter.user_token("u1", "companion-abc").token
    header, _, signature = token.split(".")
    forged = encode_jwt({"iss": API_KEY, "sub": "user:someone-else", "exp": 9_999_999_999}, SECRET)
    _, forged_body, _ = forged.split(".")
    with pytest.raises(InvalidSignature):
        decode_jwt(f"{header}.{forged_body}.{signature}", SECRET)


def test_expired_token_is_rejected(minter):
    token = minter.user_token("u1", "companion-abc", now=1_700_000_000.0).token
    with pytest.raises(TokenExpired):
        decode_jwt(token, SECRET, now=time.time() + 10_000)


def test_token_before_nbf_is_rejected(minter):
    token = minter.user_token("u1", "companion-abc", now=1_700_000_000.0).token
    with pytest.raises(InvalidToken):
        decode_jwt(token, SECRET, now=1_600_000_000.0)


def test_malformed_token_is_rejected():
    for bad in ["", "abc", "a.b.c", "a.b"]:
        with pytest.raises(InvalidToken):
            decode_jwt(bad, SECRET)


def test_missing_credentials_raise_rather_than_mint():
    with pytest.raises(MissingCredentials):
        TokenMinter(api_key="", api_secret="").user_token("u1", "companion-abc")
    with pytest.raises(MissingCredentials):
        encode_jwt({"exp": 1}, "")


def test_non_positive_ttl_is_rejected():
    with pytest.raises(ValueError):
        TokenMinter(api_key=API_KEY, api_secret=SECRET, ttl_sec=0)


def test_jwt_segments_are_base64url_without_padding(minter):
    token = minter.user_token("u1", "companion-abc").token
    assert len(token.split(".")) == 3
    assert "=" not in token
    assert "+" not in token and "/" not in token


def test_identity_helpers():
    assert user_identity("42") == "user:42"
    assert agent_identity("x") == "agent:x"
