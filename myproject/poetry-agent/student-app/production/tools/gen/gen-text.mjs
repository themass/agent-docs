// 通用占位:L0 文字卡。用法: node tools/gen/gen-text.mjs <poem>
// 为任务类型 text-card 且 placeholder_plan.strategy=generated-text 的任务写 card.txt。文字取自任务单 brief.script_text。
// 与 gen-chun-wang-text.mjs 行为相同(后者是《春望》的历史副本,保留以免改动已登记的输出)。
import { tasksOf, fresh, put, delivery } from './_common.mjs';

const poem = process.argv[2];
if (!poem) { console.error('usage: node tools/gen/gen-text.mjs <poem>'); process.exit(2); }
const tasks = tasksOf(poem);
const ids = Object.values(tasks).filter((t) => t.type === 'text-card' && t.placeholder_plan.strategy === 'generated-text').map((t) => t.task_id);
for (const id of ids) {
  const text = tasks[id].brief.script_text;
  if (!text) throw new Error(`${id}: 任务单没有 script_text(文字卡必须有脚本)`);
  fresh(id);
  put(id, 'card.txt', text + '\n');
  delivery(id, { generator: 'tools/gen/gen-text.mjs', origin: '由任务单脚本文本派生(底座/剧本已有文字,未新增史实)' });
  console.log('wrote inbox/' + id);
}
