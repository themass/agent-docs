from agentkit.common.ids import new_id

def test_new_id_prefix():
    v = new_id("trc")
    assert v.startswith("trc_")
