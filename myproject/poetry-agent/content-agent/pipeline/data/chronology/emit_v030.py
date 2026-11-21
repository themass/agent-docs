#!/usr/bin/env python3
"""V030：纯修复迁移——text-work-t300-291-ws（韋應物《東郊》）poetry_text_line 形状修复。

V018 对 291 落 poetry_text_line 时把 line_seq 7 误并四句为一行
（'微雨靄芳原，春鳩鳴何處？樂幽心屢止，遵事跡猶遽。'），12 句只落 9 行。
全库扫描此形状仅 234、291 两例；234 已在 V029 修复，本迁移修 291。

**前置（顺序不可反）**：ws 诗页有两对页内异文 {{另|斯|期}}/{{另|真|直}}，
已先登记于 corpus/tang300-variants.md（2026-11-20 行「東郊 291」）——先登记后修形。
新行正文取页内首读（斯/真），与 V018 既定路线一致，不引入任何正文改动：
本迁移只改分行形状（9 行→12 行），12 句逐字对折叠后（{{另|首|次}}→首）的 ws <poem> 块。

新行值**不从手抄**：生成器直接解析 ws 快照 <poem> 块 + 折叠 {{另}} 标记机械切分；
回滚旧行值**也不从手抄**：直接解析 V018 SQL 里 291-ws 的 9 行原文。两侧都是机器核对。

grep 实测：全库只有 V018__tang300_ws_verified.sql 与 recovery/V018_rollback.sql 引用
text-work-t300-291-ws——删 9 插 12 安全，不触碰任何其他迁移/回滚的行。

用法: python3 -I emit_v030.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import sql_s  # noqa: E402  SQL 字面量转义——单一来源

MIG = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
WS = pathlib.Path('/tmp/src-dl/ws-poems/東郊.txt').read_text(encoding='utf-8')
V018 = (MIG / 'V018__tang300_ws_verified.sql').read_text(encoding='utf-8')

# ---------- 新 12 行：从 ws 快照机械切分（折叠 {{另|首|次}}→首） ----------
poem = WS[WS.index('<poem>') + len('<poem>'): WS.index('</poem>')]
folded = re.sub(r'\{\{另\|([^|}]+)\|[^}]*\}\}', r'\1', poem)
full = ''.join(line.strip() for line in folded.splitlines() if line.strip())
# 五言古排：每句以 ，。？ 收尾——按标点切，标点跟在句尾
parts = re.findall(r'[^，。？]+[，。？]', full)
if ''.join(parts) != full:
    raise SystemExit(f'标点切分不闭合: {full}')
if len(parts) != 12:
    raise SystemExit(f'《東郊》应 12 句，机械切分得 {len(parts)} 句')
LINES_NEW = {i + 1: p for i, p in enumerate(parts)}

# ---------- 旧 9 行：从 V018 SQL 原文机械解析（不手抄） ----------
old = re.findall(
    r"SELECT 'text-work-t300-291-ws' AS version_id, (\d+) AS line_seq, '([^']*)' AS content", V018)
if len(old) != 9:
    raise SystemExit(f'V018 里 291-ws 应 9 行，解析得 {len(old)} 行')
LINES_OLD = {int(n): t for n, t in old}
# 形状断言：旧值恰是「前 6 新行 + 第 7 行并四句 + 末 2 行」——证明本次只动 line_seq 7
assert [LINES_OLD[n] for n in range(1, 7)] == [LINES_NEW[n] for n in range(1, 7)], '前 6 行应原样'
assert LINES_OLD[7] == LINES_NEW[7] + LINES_NEW[8] + LINES_NEW[9] + LINES_NEW[10], '并句形状不符'
assert [LINES_OLD[n] for n in (8, 9)] == [LINES_NEW[11], LINES_NEW[12]], '末 2 行应原样'


def lines_insert(rows):
    head = 'INSERT INTO poetry_text_line (version_id, line_seq, content)\nSELECT * FROM ('
    body = '\nUNION ALL\n'.join(
        f"SELECT 'text-work-t300-291-ws' AS version_id, {n} AS line_seq, "
        f"{sql_s(t)} AS content FROM DUAL"
        for n, t in sorted(rows.items()))
    return (head + '\n' + body +
            '\n) AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_text_line x '
            'WHERE x.version_id = t.version_id AND x.line_seq = t.line_seq);')


def build():
    return f"""-- V030：纯修复迁移——text-work-t300-291-ws（韋應物《東郊》）9 行并句 → 12 行。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V018 已执行；且《東郊》两对页内异文 {{另|斯|期}}/{{另|真|直}} 已先登记于
--   corpus/tang300-variants.md（「東郊 291」行，2026-11-20）——先登记后修形，顺序不可反。
--
-- 缺陷：V018 对 291 落 poetry_text_line 时 line_seq 7 误并四句为一行
--   （'微雨靄芳原，春鳩鳴何處？樂幽心屢止，遵事跡猶遽。'），12 句只落 9 行。
--   全库此形状仅 234、291 两例；234 已在 V029 修复，本迁移修 291。
--   grep 实测：全库只有 V018 与其回滚引用 text-work-t300-291-ws——删旧插新安全。
--
-- 数据源（机器核对，两侧都不手抄）：新 12 行由 emit_v030.py 对 ws 快照
--   /tmp/src-dl/ws-poems/東郊.txt 的 <poem> 块折叠 {{{{另|首|次}}}}→首 后按标点机械切分；
--   回滚旧 9 行由同一脚本直接解析 V018 SQL 原文。新行正文取页内首读（斯/真），
--   与 V018 既定路线一致——本迁移只改分行形状，不动一个字。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 29，不含 30
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-291-ws';  -- 恰 9（缺陷行）
--   SELECT content FROM poetry_text_line WHERE version_id='text-work-t300-291-ws' AND line_seq=7;
--     -- 恰为上面那行 24 字并句
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-291-ws';  -- 12
--   SELECT content FROM poetry_text_line WHERE version_id='text-work-t300-291-ws'
--     AND line_seq IN (11,12);  -- '終罷斯結廬，' / '慕陶真可庶。'（首读）
-- 回滚: recovery/V030_rollback.sql（删 12 插 9——9 行值逐字解析自 V018 原文；不动 V018 其他行）
START TRANSACTION;

-- ---------- 修复：删缺陷 9 行，重插 12 行（逐字对折叠后的 ws <poem> 块） ----------
DELETE FROM poetry_text_line WHERE version_id = 'text-work-t300-291-ws';

{lines_insert(LINES_NEW)}

-- ---------- 版本账本 ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 30, 'pure repair migration for text-work-t300-291-ws (Wei Yingwu Dong-jiao, qi-jin-gu regulated-style): V018 mis-merged four poem-lines into line_seq 7 so twelve lines landed as nine rows -- the corpus scan in V029 found this shape only for works 234 and 291, and 234 was repaired inside V029; the two page-internal variants of this poem were registered first in corpus/tang300-variants.md as required (register-before-reshape), new rows keep the page first-reading (Si/Zhen) exactly as V018 chose, so the repair changes line shape only, not a single character of the stored text'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 30);
COMMIT;
"""


def build_rollback():
    return f"""-- V030 精确回滚：删 V030 的 12 行，重插 V018 原 9 行（值逐字解析自 V018 SQL 原文，非手抄）。
-- work-t300-291 本体与其 version/source/claim 行都是 V018 的，绝不删。
START TRANSACTION;

DELETE FROM poetry_text_line WHERE version_id = 'text-work-t300-291-ws';

{lines_insert(LINES_OLD)}

DELETE FROM poetry_schema_version WHERE version_no = 30;
COMMIT;
"""


def audit(sql, rb):
    bad = []
    flat = sql.replace("''", "'")
    for n, t in LINES_NEW.items():
        if sql_s(t) not in sql:
            bad.append(f'新行 {n} 未逐字进入 SQL: {t}')
    for n, t in LINES_OLD.items():
        if sql_s(t) not in rb.replace("''", "'"):
            bad.append(f'回滚旧行 {n} 未逐字进入回滚: {t}')
    # 新行首读必须逐字对折叠后的 poem（防折叠规则回归）
    for p in parts:
        if p not in full:
            bad.append(f'新行不在折叠正文内: {p}')
    if '慕陶真可庶。' not in full or '終罷斯結廬，' not in full:
        bad.append('折叠首读应含 斯/真')
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    for m in re.finditer(r'INSERT INTO (poetry_\w+)', sql):
        # 串感知找语句边界（账本描述里有分号，裸 find(';') 会截早——V029 audit 同款扫描）
        i, in_str, end = m.end(), False, len(sql)
        while i < end:
            ch = sql[i]
            if in_str:
                if ch == "'":
                    if i + 1 < end and sql[i + 1] == "'":
                        i += 1
                    else:
                        in_str = False
            elif ch == "'":
                in_str = True
            elif ch == ';':
                end = i
                break
            i += 1
        stmt = sql[m.start():end]
        if 'WHERE NOT EXISTS' not in stmt:
            bad.append(f'{m.group(1)} 的 INSERT 没有幂等守卫')
    if 'INSERT INTO poetry_citation' in sql or 'INSERT INTO poetry_background' in sql:
        bad.append('纯修复迁移不该碰 content/citation/background')
    if '234' in re.sub(r'work-t300-234 已在', '', sql.replace('234 已在 V029 修复', '')):
        pass  # 注释里允许提及 234；行数据里绝不允许
    if 'text-work-t300-234' in sql or 'text-work-t300-234' in rb:
        bad.append('本迁移不得触碰 234（V029 已修）')
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-sql', required=True)
    ap.add_argument('--out-rollback', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    sql, rb = build(), build_rollback()
    bad = audit(sql, rb)
    if bad:
        print('AUDIT FAIL:')
        for b in bad:
            print(' -', b)
        raise SystemExit(1)
    if args.dry_run:
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 新12行机械切分自 ws <poem>（折叠{{{{另}}}}→首），'
              f'旧9行解析自 V018 原文，并句形状断言通过（7=8+9+10+11拼接）')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
