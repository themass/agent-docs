// 通用占位:音频与字幕。用法: node tools/gen/gen-audio.mjs <poem>
// - recitation(诵读示范):朗读 brief.script_text,时长不足时放慢直到达到任务单 entry 约束的最小时长。
// - narration(旁白/台词):按 depends_on 决定音色(含 voice 时用 vars.reader_voice,否则 vars.narrator_voice)。
// - 每个音频的 companion_of 字幕任务:按真实时长分配 WebVTT 时间轴,文字与脚本逐字一致。
// 音色与语速只来自 demand.vars,不写死某一首诗。TTS 韵律不可信,全部标注占位。
// 需要 macOS say、ffmpeg、ffprobe;缺任何一个明确报错。
import { mkdtempSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { tasksOf, fresh, put, delivery, run, ROOT } from './_common.mjs';
import { ffprobeAudio } from '../lib/checks.mjs';
import { vtt } from '../lib/vtt.mjs';
import { readJson } from '../lib/registry.mjs';
import { join as pj } from 'node:path';

const poem = process.argv[2];
if (!poem) { console.error('usage: node tools/gen/gen-audio.mjs <poem>'); process.exit(2); }
const demand = readJson(pj(ROOT, 'tasks', poem, 'demand.json'));
const vars = demand.vars || {};
const need = (k) => { if (!vars[k]) throw new Error(`demand.vars.${k} 未设置(音色必须由任务单指定,不写死)`); return vars[k]; };
const tasks = tasksOf(poem);
const tmp = mkdtempSync(join(tmpdir(), 'qj-audio-'));
const EVID = ['未核实:macOS 系统语音的商用许可;占位不可上线'];

function synth(text, voice, outName, { rate = 170, sampleRate = 22050 } = {}) {
  const aiff = join(tmp, outName + '.aiff'), m4a = join(tmp, outName + '.m4a');
  run('say', ['-v', voice, '-r', String(rate), '-o', aiff, text]);
  run('ffmpeg', ['-v', 'error', '-y', '-i', aiff, '-ar', String(sampleRate), '-ac', '1', '-c:a', 'aac', '-b:a', '64k', m4a]);
  return { path: m4a, info: ffprobeAudio(m4a) };
}
const subtitleOf = (id) => Object.values(tasks).find((t) => t.companion_of === id && t.type === 'subtitle');
const minMs = (t) => t.deliverables.find((d) => d.role === 'entry')?.constraints?.min_duration_ms ?? 0;

const VOICE_OF = (t) => ((t.depends_on || []).some((d) => d.startsWith('voice-')) ? need('reader_voice') : need('narrator_voice'));

for (const t of Object.values(tasks).filter((x) => x.type === 'recitation' || x.type === 'narration')) {
  const id = t.task_id, entry = t.type === 'recitation' ? 'recite.m4a' : 'narration.m4a';
  fresh(id);
  let s, rate = 170;
  if (t.type === 'recitation') {
    // 短诗时长可能不足:降速直到达到下限(下限来自任务单 entry 约束)
    for (rate = 150; rate >= 90; rate -= 15) { s = synth(t.brief.script_text, VOICE_OF(t), id, { rate, sampleRate: 44100 }); if (s.info.durationMs >= minMs(t)) break; }
    if (s.info.durationMs < minMs(t)) throw new Error(`${id}: 放慢到 ${rate} 仍不足 ${minMs(t)}ms(${s.info.durationMs}ms)`);
  } else s = synth(t.brief.script_text, VOICE_OF(t), id);
  put(id, entry, readFileSync(s.path));
  put(id, t.type === 'recitation' ? 'recite.txt' : 'narration.txt', t.brief.script_text + '\n');
  delivery(id, { generator: 'tools/gen/gen-audio.mjs', origin: `自生成占位(macOS say 合成${t.type === 'recitation' ? ',朗读韵律不可信' : ''})`, evidence: EVID });
  const sub = subtitleOf(id);
  if (sub) {
    fresh(sub.task_id);
    put(sub.task_id, 'captions.vtt', vtt(sub.brief.script_text, s.info.durationMs));
    delivery(sub.task_id, { generator: 'tools/gen/gen-audio.mjs', origin: '由脚本文本派生,时间轴按占位音频时长分配' });
  }
  console.log(`wrote inbox/${id}${sub ? ` + ${sub.task_id}` : ''}`);
}
