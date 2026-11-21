#!/usr/bin/env node
// 占位:春望的音频与字幕。macOS 自带 `say` 的中文声音合成 → ffmpeg 转 m4a;字幕时间轴按真实时长按字数分配。
// 清楚标注:占位,不可上线。TTS 读古诗韵律不可信(architecture §2.3),系统语音的商用授权未核实。
// 需要 macOS `say`、ffmpeg、ffprobe;缺任何一个就报错退出(不静默生成空文件)。
import { mkdtempSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { tasksOf, fresh, put, delivery, run } from './_common.mjs';
import { ffprobeAudio } from '../lib/checks.mjs';
import { vtt } from '../lib/vtt.mjs';

const tasks = tasksOf('chun-wang');
const tmp = mkdtempSync(join(tmpdir(), 'qj-audio-'));
const NARRATOR = 'Tingting', DUFU = 'Grandpa (中文（中国大陆）)';
const EVID = ['未核实:macOS 系统语音的商用许可;占位不可上线'];
const swvers = run('sw_vers', ['-productVersion']).stdout.trim();

function synth(text, voice, outName, { rate = 170, sampleRate = 22050 } = {}) {
  const aiff = join(tmp, outName + '.aiff'), m4a = join(tmp, outName + '.m4a');
  run('say', ['-v', voice, '-r', String(rate), '-o', aiff, text]);
  run('ffmpeg', ['-v', 'error', '-y', '-i', aiff, '-ar', String(sampleRate), '-ac', '1', '-c:a', 'aac', '-b:a', '64k', m4a]);
  return { path: m4a, info: ffprobeAudio(m4a) };
}

const subtitleOf = (id) => Object.values(tasks).find((t) => t.companion_of === id && t.type === 'subtitle');

// ---- 音色档案 ----
{
  const id = 'voice-dufu-1'; fresh(id);
  const s = synth('我是杜甫的占位声音。这只是一个占位音色,不可上线。', DUFU, id);
  put(id, 'sample.m4a', readFileSync(s.path));
  put(id, 'voice.json', JSON.stringify({ schema_version: '1.0', voice_id: id, provider: 'Apple macOS say(系统自带语音)', model: DUFU, version: `macOS ${swvers}`, params: { rate_wpm: 170 },
    language: 'zh-CN', license_scope: '占位:系统语音的商用授权未核实,不可上线', cloning_allowed: false, source_speaker_consent: 'n/a', sample: 'sample.m4a', placeholder: true }, null, 2) + '\n');
  delivery(id, { generator: 'tools/gen/gen-chun-wang-audio.mjs', origin: '自生成占位(macOS say 合成)', evidence: EVID });
}

// ---- 诵读示范 + 字幕 ----
{
  const id = 'a-recite-demo', t = tasks[id]; fresh(id);
  let rate = 150, s;
  for (; rate >= 90; rate -= 15) { s = synth(t.brief.script_text, DUFU, id, { rate, sampleRate: 44100 }); if (s.info.durationMs >= 10500) break; }
  if (s.info.durationMs < 10500) throw new Error(`${id}: 放慢到 ${rate} 仍不足 10.5 秒(${s.info.durationMs}ms)`);
  put(id, 'recite.m4a', readFileSync(s.path)); put(id, 'recite.txt', t.brief.script_text + '\n');
  delivery(id, { generator: 'tools/gen/gen-chun-wang-audio.mjs', origin: '自生成占位(macOS say 朗读,韵律不可信)', evidence: EVID, extraNotes: '不是真人诵读。' });
  const sub = subtitleOf(id); fresh(sub.task_id);
  put(sub.task_id, 'captions.vtt', vtt(sub.brief.script_text, s.info.durationMs));
  delivery(sub.task_id, { generator: 'tools/gen/gen-chun-wang-audio.mjs', origin: '由诗句全文派生,时间轴按占位音频时长分配' });
}

// ---- 旁白 / 杜甫台词 + 字幕 ----
for (const t of Object.values(tasks).filter((x) => x.type === 'narration')) {
  const id = t.task_id; fresh(id);
  const voice = (t.depends_on || []).includes('voice-dufu-1') ? DUFU : NARRATOR; // 演绎台词用角色音色,旁白用旁白音色
  const s = synth(t.brief.script_text, voice, id);
  put(id, 'narration.m4a', readFileSync(s.path)); put(id, 'narration.txt', t.brief.script_text + '\n');
  delivery(id, { generator: 'tools/gen/gen-chun-wang-audio.mjs', origin: '自生成占位(macOS say 合成)', evidence: EVID });
  const sub = subtitleOf(id); fresh(sub.task_id);
  put(sub.task_id, 'captions.vtt', vtt(sub.brief.script_text, s.info.durationMs));
  delivery(sub.task_id, { generator: 'tools/gen/gen-chun-wang-audio.mjs', origin: '由 bundle 台词派生,时间轴按占位音频时长分配' });
}

// ---- 音效:鸟鸣(几声短促啁啾,合成)----
{
  const id = 'a-sfx-birds'; fresh(id);
  const out = join(tmp, id + '.m4a');
  const g1 = 'lt(mod(t,2),0.25)*sin(PI*mod(t,2)/0.25)', g2 = 'between(mod(t,2),0.45,0.62)*sin(PI*(mod(t,2)-0.45)/0.17)';
  run('ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', `aevalsrc='0.22*sin(2*PI*(3000+1200*sin(2*PI*9*t))*t)*(${g1}+0.6*${g2})':d=6:s=44100`, '-ac', '1', '-c:a', 'aac', '-b:a', '48k', out]);
  put(id, 'sfx.m4a', readFileSync(out));
  delivery(id, { generator: 'tools/gen/gen-chun-wang-audio.mjs', origin: '自生成占位(ffmpeg 合成的几声短促啁啾)', evidence: ['无第三方素材'] });
}
console.log('wrote audio/subtitle placeholders into inbox/');
