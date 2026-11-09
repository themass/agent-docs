"""T0-1: build create_deerflow_agent with NO DeerFlow config file and run one streamed turn."""
import asyncio, os, sys, traceback
sys.path.insert(0, "/tmp/spike")
from fake_openai import serve
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from deerflow.agents.factory import create_deerflow_agent
from deerflow.agents.features import RuntimeFeatures

srv = serve(18080)
os.environ.pop("DEER_FLOW_CONFIG_PATH", None)
model = ChatOpenAI(model="fake-chat", base_url="http://127.0.0.1:18080/v1", api_key="sk-test", streaming=True)
features = RuntimeFeatures(sandbox=False, memory=False, summarization=False, subagent=False,
                           loop_detection=True, token_budget=True, vision=False, auto_title=False)
try:
    graph = create_deerflow_agent(model, tools=[], system_prompt="你是测试助手。", features=features, name="spike")
    print("BUILD OK")
except Exception as e:
    print("BUILD FAILED:", type(e).__name__, e); traceback.print_exc(); sys.exit(1)

async def run():
    chunks = []
    try:
        async for item in graph.astream({"messages": [HumanMessage(content="你好")]}, stream_mode="messages"):
            msg, meta = item
            chunks.append((type(msg).__name__, getattr(msg, "content", None), meta.get("langgraph_node")))
    except Exception as e:
        print("STREAM FAILED:", type(e).__name__, e); traceback.print_exc(); return
    print("STREAM OK, events:", len(chunks))
    for c in chunks[:6]: print("  ", c)
    print("requests sent to fake:", len(srv.requests))
    print("system message sent:", srv.requests[0]["messages"][0]["content"][:40] if srv.requests else None)
asyncio.run(run())
