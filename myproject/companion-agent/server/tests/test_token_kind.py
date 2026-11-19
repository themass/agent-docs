"""agent token 必须在 JWT 顶层带 LiveKit 的 kind=agent。

剧本房手机端只消费 ``Participant.Kind.AGENT`` 的数据，而 kind 是 SFU 从
token claim 里读出来、再通过 ParticipantInfo 下发的。identity 前缀
（``agent:``）只是我们的命名约定，SFU 不看它——漏了这个 claim，agent
在客户端眼里就是个 STANDARD 参与者，推送全被手机端过滤掉。
"""

import pytest

from companion.service.room.livekit_tokens import TokenMinter, decode_jwt

SECRET = "test-only-secret"
API_KEY = "test-api-key"


@pytest.fixture
def minter():
    return TokenMinter(api_key=API_KEY, api_secret=SECRET, ttl_sec=60)


def test_agent_token_jwt_carries_agent_kind(minter):
    minted = minter.agent_token("a1", "script-demo")
    claims = decode_jwt(minted.token, SECRET)
    assert claims.get("kind") == "agent"


def test_user_token_jwt_does_not_force_agent_kind(minter):
    """用户 token 不能带 kind，否则 SFU 会把真人当成 agent。"""
    minted = minter.user_token("u1", "script-demo")
    claims = decode_jwt(minted.token, SECRET)
    assert "kind" not in claims


def test_agent_kind_does_not_disturb_the_video_grant(minter):
    """kind 是顶层 claim，不能混进 video grant 里替换掉房间权限。"""
    claims = decode_jwt(minter.agent_token("a1", "script-demo").token, SECRET)
    assert claims["video"]["room"] == "script-demo"
    assert claims["video"]["roomJoin"] is True
    assert "kind" not in claims["video"]
