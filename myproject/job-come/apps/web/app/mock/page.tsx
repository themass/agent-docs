"use client";

import Link from "next/link";
import { useState } from "react";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { createMockSession } from "@/lib/api/coach";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function MockPage() {
  const { context } = useAuth();
  const profileId = context?.active_profile_id ?? null;
  const [mockSessionId, setMockSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onStart() {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    try {
      const session = await createMockSession({ profile_id: profileId, mode: "target" });
      setMockSessionId(session.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  const isUser = context?.actor === "user";

  return (
    <AgentWorkbench
      pageKey="mock-interview"
      title="模拟面试"
      subtitle="左侧管理模拟面会话，右侧 Agent 实时陪练"
      profileId={profileId}
      skillHint="coach-mock"
      kind="coach"
      disabled={!isUser}
      placeholder="回答面试官问题，或请求下一题…"
    >
      <div className="space-y-6">
        {!isUser ? (
          <p className="text-sm text-amber-700">请登录后开启模拟面试会话。</p>
        ) : !profileId ? (
          <p className="text-sm text-neutral-600">
            请先{" "}
            <Link href="/resume-agent" className="underline">
              上传简历
            </Link>
            。
          </p>
        ) : (
          <>
            <section className="rounded-lg border border-neutral-200 bg-neutral-50 p-4">
              <h2 className="text-sm font-medium text-neutral-800">模拟面会话</h2>
              <p className="mt-1 text-xs text-neutral-500">
                创建结构化模拟面记录，便于后续在辅导 Agent 中归档真题。
              </p>
              <button
                type="button"
                onClick={() => void onStart()}
                disabled={busy}
                className="mt-3 rounded bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {busy ? "创建中…" : "新建模拟面会话"}
              </button>
              {mockSessionId ? (
                <p className="mt-3 text-sm text-green-700">
                  会话已创建：<code className="text-xs">{mockSessionId}</code>
                </p>
              ) : null}
              {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
            </section>

            <section className="rounded-lg border border-dashed border-neutral-200 p-4 text-sm text-neutral-600">
              <p className="font-medium text-neutral-800">对话面试</p>
              <p className="mt-2">
                在右侧 Agent 面板开始语音或文字答题。可附加岗位 JD 截图，Agent 将结合档案给出追问与评分建议。
              </p>
            </section>
          </>
        )}
      </div>
    </AgentWorkbench>
  );
}
