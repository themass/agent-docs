"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { logQuestion, saveInterview, listInterviews, type InterviewSummary } from "@/lib/api/coach";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function InterviewsPage() {
  const { context } = useAuth();
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [date, setDate] = useState("");
  const [stems, setStems] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  // Keep completed question writes on retry; an archive failure must not duplicate them.
  const [savedQuestions, setSavedQuestions] = useState<Record<string, string>>({});
  const profileId = context?.active_profile_id;
  const [history, setHistory] = useState<InterviewSummary[]>([]);
  const [historyError, setHistoryError] = useState("");
  useEffect(() => {
    setHistory([]); setHistoryError("");
    if (!profileId) return;
    let active = true;
    listInterviews(profileId).then(r => { if (active) setHistory(r.interviews); })
      .catch(e => { if (active) setHistoryError(e instanceof Error ? e.message : "读取失败"); });
    return () => { active = false; };
  }, [profileId]);
  async function save() {
    if (!profileId || busy) return;
    setBusy(true); setMessage("");
    const done = { ...savedQuestions };
    try {
      const lines = [...new Set(stems.split("\n").map(x => x.trim()).filter(Boolean))];
      if (lines.some(x => x.length < 4 || x.length > 4000)) throw new Error("每个题干需为 4–4000 字");
      const ids: string[] = [];
      for (const stem of lines) {
        const key = JSON.stringify([profileId, company, role, stem]);
        if (!done[key]) {
          const q = await logQuestion(profileId, { stem, source: "real", company, role_title: role });
          done[key] = q.id; setSavedQuestions({ ...done });
        }
        ids.push(done[key]);
      }
      await saveInterview(profileId, { company, role_title: role, interview_date: date, notes, question_ids: ids });
      setMessage("面试已归档，题目已进入个人题库。可以去题库再次练习。");
      setStems(""); setNotes(""); setSavedQuestions({});
      // Archive is already committed; a refresh failure must not invite a duplicate save.
      try {
        setHistory((await listInterviews(profileId)).interviews);
        setHistoryError("");
      } catch {
        setHistoryError("面试已保存，但历史刷新失败。请刷新页面查看，不必再次归档。");
      }
    } catch (e) { setMessage(e instanceof Error ? e.message : "保存失败，请重试"); }
    finally { setBusy(false); }
  }
  if (context?.actor !== "user") return <p>请先登录再归档真实面试。</p>;
  if (!profileId) return <p>请先创建并确认个人档案。</p>;
  const input = "mt-1 w-full rounded border border-slate-300 px-3 py-2";
  return <div className="mx-auto max-w-2xl space-y-4">
    <h1 className="text-2xl font-semibold">真实面试归档</h1>
    <p className="text-sm text-slate-600">面试后记录自己的经历与问题。V1 不监听会议、不提供实时作答提示；请勿上传无授权的他人个人信息或公司机密。</p>
    <label className="block">公司<input className={input} value={company} onChange={e => setCompany(e.target.value)} /></label>
    <label className="block">岗位<input className={input} value={role} onChange={e => setRole(e.target.value)} /></label>
    <label className="block">面试日期<input type="date" className={input} value={date} onChange={e => setDate(e.target.value)} /></label>
    <label className="block">问题（一行一道，可选）<textarea rows={5} className={input} value={stems} onChange={e => setStems(e.target.value)} /></label>
    <label className="block">复盘笔记<textarea rows={4} className={input} value={notes} onChange={e => setNotes(e.target.value)} /></label>
    <button disabled={busy || !company.trim() || !role.trim() || !date} onClick={() => void save()} className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50">{busy ? "保存中…" : "归档并保存题目"}</button>
    {message ? <p role="status">{message}</p> : null}
    <section className="space-y-3 border-t pt-4"><h2 className="font-semibold">已归档面试（最近 50 条）</h2>
      {historyError ? <p role="alert">{historyError}</p> : null}
      {history.map(r => <article key={r.id} className="rounded border p-3">
        <h3>{r.interview_date} · {r.company} · {r.role_title}</h3>
        <p className="whitespace-pre-wrap text-sm">{r.notes}</p>
        <div className="flex flex-wrap gap-3">{r.question_ids.map((id, i) => <Link className="text-brand-700 underline" key={id} href={`/bank/${encodeURIComponent(id)}`}>题目 {i + 1}</Link>)}</div>
      </article>)}
      {!history.length && !historyError ? <p>暂无归档。</p> : null}
    </section>
    <p><Link href="/bank" className="text-brand-700 underline">查看个人题库并再练</Link></p>
  </div>;
}
