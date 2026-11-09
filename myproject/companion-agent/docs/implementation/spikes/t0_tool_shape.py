"""T0-3: event shapes for stream_mode='messages' when the model calls a tool."""
import asyncio, json, os, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from deerflow.agents.factory import create_deerflow_agent
from deerflow.agents.features import RuntimeFeatures

def sse(obj): return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode()

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_POST(self):
        req=json.loads(self.rfile.read(int(self.headers.get("content-length",0))))
        has_tool_result = any(m.get("role")=="tool" for m in req["messages"])
        self.send_response(200); self.send_header("content-type","text/event-stream"); self.end_headers()
        base={"id":"x","object":"chat.completion.chunk","created":int(time.time()),"model":"fake"}
        if not has_tool_result:
            # first call: stream a tool call split across chunks
            self.wfile.write(sse({**base,"choices":[{"index":0,"delta":{"role":"assistant","content":""}}]}))
            self.wfile.write(sse({**base,"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"lookup","arguments":""}}]}}]}))
            self.wfile.write(sse({**base,"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"q\":\"甲\"}"}}]}}]}))
            self.wfile.write(sse({**base,"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}))
        else:
            for ch in "查到了。":
                self.wfile.write(sse({**base,"choices":[{"index":0,"delta":{"content":ch}}]}))
            self.wfile.write(sse({**base,"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}))
        self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()

srv=ThreadingHTTPServer(("127.0.0.1",18081),H); threading.Thread(target=srv.serve_forever,daemon=True).start()

@tool
def lookup(q: str) -> str:
    """Look something up."""
    return f"result for {q}"

model=ChatOpenAI(model="fake",base_url="http://127.0.0.1:18081/v1",api_key="sk-test",streaming=True)
features=RuntimeFeatures(sandbox=False,memory=False,summarization=False,subagent=False,loop_detection=True,token_budget=False,vision=False,auto_title=False)
graph=create_deerflow_agent(model,tools=[lookup],system_prompt="test",features=features,name="spike")

async def run():
    seen=[]
    async for msg,meta in graph.astream({"messages":[HumanMessage(content="TOOL please")]},stream_mode="messages"):
        kind=type(msg).__name__
        info={"kind":kind,"node":meta.get("langgraph_node")}
        if kind=="AIMessageChunk":
            info["content"]=msg.content
            info["tool_call_chunks"]=[{"name":c.get("name"),"args":c.get("args"),"id":c.get("id"),"index":c.get("index")} for c in (msg.tool_call_chunks or [])]
        elif kind=="ToolMessage":
            info["name"]=msg.name; info["content"]=msg.content; info["tool_call_id"]=msg.tool_call_id
        seen.append(info)
    for s in seen:
        print(json.dumps(s, ensure_ascii=False))
    print("distinct kinds:", sorted({s['kind'] for s in seen}))
    print("tool messages:", sum(1 for s in seen if s['kind']=='ToolMessage'))
asyncio.run(run())
