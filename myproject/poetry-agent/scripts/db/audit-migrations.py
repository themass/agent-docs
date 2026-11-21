#!/usr/bin/env python3
# 迁移文件静态审计（只读，不连库）。V015「庚子/763」干支笔误就是这样漏进去的——
# 干支与公元年的配对、账本连续性、id 唯一性、引用先于定义、回滚对应性，全部机器判。
#
# 用法：
#   python3 -I scripts/db/audit-migrations.py                # 审计默认迁移目录
#   python3 -I scripts/db/audit-migrations.py <迁移目录>     # 目录含 V0*.sql 与 recovery/*_rollback.sql
# 退出码 0 = 全绿；1 = 有问题（逐条打印）。这是发布前门禁的替补：项目规矩是无 FOREIGN KEY
# （V001 头注），引用完整性全靠这类静态扫描 + 每代生成器自带的 audit。
import pathlib
import re
import sys

G = '甲乙丙丁戊己庚辛壬癸'
Z = '子丑寅卯辰巳午未申酉戌亥'
CN = {'〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def ganzhi(y):
    return G[(y - 4) % 10] + Z[(y - 4) % 12]


def cn_year3(s):
    """'七六三' → 763。只认三位逐位串读；认不了的返回 None（宁可漏检不误报，交人工）。"""
    if len(s) == 3 and all(c in CN for c in s):
        return CN[s[0]] * 100 + CN[s[1]] * 10 + CN[s[2]]
    return None


def ver_no(name):
    return int(name.split('__')[0][1:])


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else '/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
    files = sorted(root.glob('V0*.sql'), key=lambda p: ver_no(p.name))
    if not files:
        print(f'目录里没有 V0*.sql：{root}')
        return 1
    texts = {f.name: f.read_text(encoding='utf-8') for f in files}
    bad = []

    # 1) 同表同 id 只许插一次（跨全部迁移）。三个实测口径：
    #    a. 只有单列 id 主键的表参与本检查——poetry_citation 主键是 (claim_id,source_id)、
    #       poetry_claim_selection 是 (subject_id,property_key)、poetry_review_log 的 id 是 AUTO_INCREMENT，
    #       按第一列取值会把合法的不同行误报成 id 冲突。
    #    b. 跨迁移复用同一 id 是登记过的合法形状：守卫式 INSERT 在第二次执行时整行跳过，
    #       V015 头注「安史之乱沿用 V004 的行」、V016 头注「杜甫沿用 V002 的行，不删不重建」。
    #       除此之外同 (表,id) 见于两个迁移即冲突。
    #    c. 插入三形：'id' AS id、行首 SELECT 'id',、行首 VALUES 元组 ('id',。
    ID_PK_TABLES = {'poetry_content', 'poetry_dynasty', 'poetry_period', 'poetry_place',
                    'poetry_person', 'poetry_event', 'poetry_experience', 'poetry_work',
                    'poetry_source', 'poetry_claim', 'poetry_relation', 'poetry_text_version',
                    'poetry_background', 'poetry_annotation', 'poetry_textbook',
                    'poetry_coverage', 'poetry_theme'}
    ALLOWED_REUSE = {('poetry_content', 'event-anshi-rebellion'),   # V004 草稿 → V015 沿用（头注）
                     ('poetry_content', 'person-du-fu'),            # V002 草稿 → V016 沿用（头注）
                     ('poetry_person', 'person-du-fu')}             # 同上，person 表那一行
    per = {}
    for f in files:
        cur = None
        for m in re.finditer(r"(?m)INSERT INTO (poetry_\w+)"
                             r"|SELECT '([a-z0-9][a-z0-9_.-]{3,})' AS id\b"
                             r"|^(?:SELECT )?\(?'([a-z0-9][a-z0-9_.-]{3,})'",
                             texts[f.name]):
            if m.group(1):
                cur = m.group(1)
            elif cur in ID_PK_TABLES:
                # 用文件名集合而非列表：一行会同时命中两种形状，不能算冲突
                per.setdefault((cur, m.group(2) or m.group(3)), set()).add(f.name)
    for k, v in sorted(per.items()):
        if len(v) > 1 and k not in ALLOWED_REUSE:
            bad.append(f'id 冲突：{k[0]} {k[1]} 见于 {sorted(v)}')

    # 2) 版本账本连续（三种写法都要认：VALUES 行内、DUAL 守卫、三行 WHERE version_no=N）
    vers = set()
    for t in texts.values():
        for m in re.finditer(r"VALUES \((\d+), '(?:[^']|'')*'\)", t):
            vers.add(int(m.group(1)))
        for m in re.finditer(r"SELECT (\d+), '(?:[^']|'')*'\s*\n?FROM DUAL WHERE NOT EXISTS", t):
            vers.add(int(m.group(1)))
        for m in re.finditer(r"WHERE version_no\s*=\s*(\d+)\s*\)\s*;", t):
            vers.add(int(m.group(1)))
    if vers:
        missing = [v for v in range(1, max(vers) + 1) if v not in vers]
        if missing:
            bad.append(f'poetry_schema_version 缺号: {missing}')

    # 3) source 引用先于定义（定义两形：行首 SELECT 'id'… 与行首 ('id', …) 多行元组列表。
    #    两个实测坑：逗号后空格不统一（V014/V015 无空格、V002/V004 有空格）；
    #    交替式里的括号会吃掉行首字面 `(` 后再要求 `(`，永假——所以用可选式，实测
    #    `(?m)^(?:SELECT )?\(?'(source-[a-z0-9-]+)'` 在 V004 命中 3、V014 命中 3、V015 命中 2）
    defs = {}
    for f in files:
        for m in re.finditer(r"(?m)^(?:SELECT )?\(?'(source-[a-z0-9-]+)'", texts[f.name]):
            defs.setdefault(m.group(1), ver_no(f.name))
    for f in files:
        n = ver_no(f.name)
        for sid in set(re.findall(r"'(source-[a-z0-9-]+)'", texts[f.name])):
            if sid not in defs:
                bad.append(f'{f.name}: 引用 {sid} 从未定义（若确实存在，扩本脚本的定义形正则并附例）')
            elif defs[sid] > n:
                bad.append(f'{f.name}: 引用 {sid} 后于定义 V{defs[sid]:03d}')

    # 4) 干支↔公元配对（阿拉伯数字与三位汉字两种纪年）
    for f in files:
        for m in re.finditer(rf'[（(]([{G}][{Z}])，公元(\d{{3,4}}|[零〇一二三四五六七八九]{{3}})年[）)]',
                             texts[f.name]):
            gz, ys = m.group(1), m.group(2)
            y = int(ys) if ys.isdigit() else cn_year3(ys)
            if y is not None and gz != ganzhi(y):
                bad.append(f'{f.name}: 「{m.group(0)}」干支应为 {ganzhi(y)}')

    # 5) 回滚文件删的每个 id 必须能对应本迁移插入的行（UPDATE 型迁移没有纯 DELETE，跳过）
    for f in files:
        n = ver_no(f.name)
        rb = root / 'recovery' / f'V{n:03d}_rollback.sql'
        if not rb.exists():
            continue
        rbt = rb.read_text(encoding='utf-8')
        if 'UPDATE ' in rbt:
            continue  # V019 型：回滚走恢复旧值路径，由生成器对旧文件字面量断言
        dels = set()
        for m in re.finditer(r"DELETE FROM poetry_\w+ WHERE \w+ IN \((.*?)\);", rbt, re.S):
            dels |= set(re.findall(r"'([a-z0-9_-]+)'", m.group(1)))
        # 插入形状两形：'id' AS id（守卫式）与行首 'id',/ ('id',（V014 式无别名列表）；
        # 括号写成可选，理由同上（交替式里的括号会吃掉行首 `(` 后再要求 `(`，永假）
        ins = set(re.findall(r"SELECT '([a-z0-9_-]+)' AS id", texts[f.name]))
        ins |= set(re.findall(r"(?m)^(?:SELECT )?\(?'([a-z0-9][a-z0-9_.-]{3,})'", texts[f.name]))
        extra = {d for d in dels if d not in ins and d != 'dynasty-tang'}
        if extra:
            bad.append(f'{f.name}: 回滚删除了本迁移没插过的 id: {sorted(extra)}')

    # 6) 字面量里反斜杠一律不许（sql_s 规矩；MySQL 默认反斜杠转义会吞字）
    for f in files:
        if re.search(r"'(?:[^'\\]|'')*\\", texts[f.name]):
            bad.append(f'{f.name}: SQL 字面量里有反斜杠')

    if bad:
        print(f'AUDIT FAIL ({len(bad)} 项):')
        for b in bad:
            print(' -', b)
        return 1
    print(f'全绿：{len(files)} 个迁移、{len(per)} 个 (表,id) 对、账本至 V{max(vers)}、'
          f'{len(defs)} 个 source 定义')
    return 0


if __name__ == '__main__':
    sys.exit(main())
