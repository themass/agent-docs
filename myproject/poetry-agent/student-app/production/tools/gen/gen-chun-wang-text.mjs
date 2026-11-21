#!/usr/bin/env node
// 占位:春望的 L0 文字卡(降级终点)。文字取自任务单 brief.script_text(来自 bundle 或 demand),不另写。
// 已由里程碑 1 登记的 a-dufu-text 不在这里生成。
import { tasksOf, fresh, put, delivery } from './_common.mjs';

const tasks = tasksOf('chun-wang');
const ids = Object.values(tasks).filter((t) => t.type === 'text-card' && t.placeholder_plan.strategy === 'generated-text').map((t) => t.task_id);
for (const id of ids) {
  const text = tasks[id].brief.script_text;
  if (!text) throw new Error(`${id}: 任务单没有 script_text`);
  fresh(id);
  put(id, 'card.txt', text + '\n');
  delivery(id, { generator: 'tools/gen/gen-chun-wang-text.mjs', origin: '由任务单脚本文本派生(底座/剧本已有文字,未新增史实)' });
  console.log('wrote inbox/' + id);
}
