// 字幕切分与 WebVTT 生成(纯函数,无副作用,可被测试安全导入)。
/** 按标点切句,每条 ≤ 30 字,标点留在句尾;拼回去与原文逐字一致。 */
export function splitCues(text, max = 30) {
  const parts = text.match(/[^,，。！？；、]+[,，。！？；、]?|[,，。！？；、]/g) || [text];
  const cues = []; let cur = '';
  for (const p of parts) { if ([...(cur + p)].length > max && cur) { cues.push(cur); cur = p; } else cur += p; }
  if (cur) cues.push(cur);
  return cues;
}
const ts = (ms) => { const h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, s = Math.floor(ms / 1000) % 60; return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms % 1000).padStart(3, '0')}`; };
export function vtt(text, durationMs) {
  const cues = splitCues(text); const total = cues.reduce((n, c) => n + [...c].length, 0);
  let t = 0; const out = ['WEBVTT', '', 'NOTE 占位字幕:时间轴按占位音频的实际时长按字数分配,不可上线', ''];
  cues.forEach((c, i) => { const end = i === cues.length - 1 ? durationMs : t + Math.round((durationMs * [...c].length) / total); out.push(`${i + 1}`, `${ts(t)} --> ${ts(end)}`, c, ''); t = end; });
  return out.join('\n');
}
