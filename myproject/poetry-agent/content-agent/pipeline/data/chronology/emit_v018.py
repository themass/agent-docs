#!/usr/bin/env python3
"""V018：三百首里「本地选本正文 × 维基文库诗页逐字复核（底本非三百首）」的 94 首入库。

入库资格（与 content-agent/.../corpus/tang300_ws_poems.py 的判定一一对应）：
  WP_RAW_EXACT / WP_FOLD_EXACT          —— 页面自述底本《全唐詩》，逐字/折叠异体后一致；
  WP_XBOOK_RAW_EXACT / WP_XBOOK_FOLD_EXACT —— 页面自述底本是异源他书（文苑英華等），同上。
排除项就是复核脚本存在的原因，不在这里重新讨论：
  WP_CIRCULAR（页面自称抄自《唐詩三百首》——与选本同源，循环论证）、
  WP_UNSOURCED_EXACT（一致但页面未声明底本）、WP_VARIANT / WP_MISS（正文不一致）。
本地御定/poet.tang 的「双证」按已查明的事实只是同仓库多转录，**不构成本迁移的入库依据**，
只作 claim 里的旁注来源引用（source 行仍 PENDING，等 verify-sources.sh 人工翻）。

诚实边界（写进每行数据本身，而不是只写在注释里）：
  - 全部 DRAFT / PENDING：迁移不宣称任何一条已人工核验；
  - WP_FOLD_* 存的是**选本文**（异体折叠只是判定手段，不代表折叠后的写法对），
    差异字符对已登记在 tang300-ws-poems-proof.md，claim 的 value_text 里写明；
  - WP_XBOOK_* 的 label 注明「他书底本」——那是跨书比对，不是《全唐詩》同书异转录；
  - 组诗同题（王維《送別》两条）靠选本序号定 id，不靠题名；
  - 作者行 attribution='PENDING'：正文旁有两个转录署名一致，但作者归属的最终判定要人来下。

id 规则：work = work-t300-<选本序号:03d>（选本自身的编号，稳定、免造拼音）；
text_version = text-<work>-ws；claim = claim-t300-<n>-text / -author；
source = source-ws-t300-<n>（n 为该页首次出现的选本序号，同页多首共用一行）。
作者 id 沿用现有 person-tang-* 语义命名，映射表手写（环境无 pypinyin，机器转写=编造元数据）。

正文行拆分：选本一段常是一联（「春眠不覺曉，處處聞啼鳥。」）。
一段内含恰好一个读点且两半都 ≤32 字时拆成两行（五言 5+5、七言 7+7 及长短句），
读点多于一个（序、并序）或不符时整段作一行——宁可粗，不猜断句。行保留原标点。

用法: python3 -I emit_v018.py \
    --out-sql ../../../../../testserverV/vvv-poetry/src/main/resources/db/poetry/V018__tang300_ws_verified.sql \
    --out-rollback ../../../../../testserverV/vvv-poetry/src/main/resources/db/poetry/recovery/V018_rollback.sql
"""
import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
CORPUS = HERE.parent / 'corpus'
SEL_PATH = pathlib.Path('/Users/gqli/work/xuexi/chinese-poetry/全唐诗/唐诗三百首.json')

VERDICTS = ('WP_RAW_EXACT', 'WP_FOLD_EXACT', 'WP_XBOOK_RAW_EXACT', 'WP_XBOOK_FOLD_EXACT')

# 作者 → 现有/新增 person id。手写，不猜拼音。左列是选本的繁体署名（原文照录）。
PERSON = {
    '王維': 'person-tang-wang-wei',        # V016 已有
    '杜甫': 'person-du-fu',                # V002/V016 已有
    '李白': 'person-tang-li-bai',          # V016 已有
    '孟浩然': 'person-tang-meng-haoran',   # V016 已有
    '李商隱': 'person-tang-li-shangyin',   # V016 已有
    '王昌齡': 'person-tang-wang-changling',# V016 已有
    '崔顥': 'person-tang-cui-hao',         # V016 已有（cui-hao 拼法沿用）
    '劉長卿': 'person-tang-liu-changqing',
    '韋應物': 'person-tang-wei-yingwu',
    '李頎': 'person-tang-li-qi',
    '岑參': 'person-tang-cen-shen',
    '元稹': 'person-tang-yuan-zhen',
    '李益': 'person-tang-li-yi',
    '祖詠': 'person-tang-zu-yong',
    '錢起': 'person-tang-qian-qi',
    '陳子昂': 'person-tang-chen-ziang',
    '金昌緒': 'person-tang-jin-changxu',
    '王灣': 'person-tang-wang-wan',
    '張旭': 'person-tang-zhang-xu',
    '王翰': 'person-tang-wang-han',
    '盧綸': 'person-tang-lu-lun',
    '丘爲': 'person-tang-qiu-wei',
    '綦毋潛': 'person-tang-qi-wu-qian',
    '常建': 'person-tang-chang-jian',
    '秦韜玉': 'person-tang-qin-taoyu',
    '張九齡': 'person-tang-zhang-jiuling',
    '宋之問': 'person-tang-song-zhiwen',
    '高適': 'person-tang-gao-shi',
    '韓翃': 'person-tang-han-hong',
    '皇甫冉': 'person-tang-huangfu-ran',
    '劉方平': 'person-tang-liu-fangping',
    '王之渙': 'person-tang-wang-zhihuan',
    '劉眘虛': 'person-tang-liu-shenxu',
    # 卷路线（tang300_verify_wikisource）新增 31 首带来的作者。署名照选本原样：
    # 西鄙人/不詳 是选本与《全唐詩》页面共有的**传统署名**（锚 `==西鄙人===` 可证），
    # 不是考定的真名——attribution 一律 PENDING，判定权在人。
    '張祜': 'person-tang-zhang-hu',
    '杜牧': 'person-tang-du-mu',
    '溫庭筠': 'person-tang-wen-tingyun',
    '韋莊': 'person-tang-wei-zhuang',
    '王建': 'person-tang-wang-jian',
    '馬戴': 'person-tang-ma-dai',
    '朱慶餘': 'person-tang-zhu-qingyu',
    '西鄙人': 'person-tang-xibi-ren',      # 传统署名「唐朝西边边境的人」，非人名
    '不詳': 'person-tang-anon',            # 选本原样署名；不编造成「佚名」
    # 快照续抓后新增（卷348 等）：
    '鄭畋': 'person-tang-zheng-tian',
}
# 已存在的 person 不再插 person/content 行（id 已占用）
EXISTING = {'person-tang-wang-wei', 'person-du-fu', 'person-tang-li-bai',
            'person-tang-meng-haoran', 'person-tang-li-shangyin',
            'person-tang-wang-changling', 'person-tang-cui-hao'}
# 已存在的 source 行（V011 为《春望》建的卷224来源）。本迁移可以**引用**它，
# 但不插它、回滚也绝不删它——不是本文件所有。
EXISTING_SOURCES = {'source-quantangshi-224'}
# 选本序号 → 已存在的 work id。《春望》在 V002 就是 work-chun-wang（V004/V017 都挂在它上面）——
# 同一首诗绝不能有第二个 work 行：产品会显示两首春望，证据还会各自漂移。
# 对这种诗：正文版本/断言/引证照常挂到**既有 id** 上；content/work/work_author 行一律不造。
EXISTING_WORKS = {208: 'work-chun-wang'}

GENRE = {  # 选本 tags 里的体式标签 → genre（VARCHAR(32) 按字符数，安全）
    '五言律诗': '五言律詩', '七言律诗': '七言律詩', '五言绝句': '五言絕句',
    '七言绝句': '七言絕句', '五言古诗': '五言古詩', '七言古诗': '七言古詩',
    '乐府': '樂府',
}


def sql_str(s):
    """同 emit_v014–017：默认 sql_mode 下转义；audit() 断言全文件零反斜杠。"""
    if s is None:
        return "NULL"
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def lit(v):
    """行值字面量：int 裸写（line_seq 这类），None→NULL，其余走 sql_str。"""
    return str(v) if isinstance(v, int) else sql_str(v)


def guard_insert(cols, table, rows, where):
    """UNION SELECT + WHERE NOT EXISTS：可重复执行（与 V015–017 同规）。"""
    body = '\nUNION ALL\n'.join(
        'SELECT ' + ', '.join(f'{lit(v)} AS {c}' for c, v in r.items()) for r in rows)
    return (f'INSERT INTO {table} ({", ".join(cols)})\n'
            f'SELECT * FROM (\n{body}\n) AS t WHERE NOT EXISTS (SELECT 1 FROM {table} x WHERE {where});')


def split_lines(paras):
    """一联一段 → 两句一行；不可靠时整段保留（见模块 docstring）。"""
    out = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        core = p.rstrip('。！？')
        tail = p[len(core):]
        parts = re.split(r'[，、；]', core)   # 字符类！写 r'，、；' 是找三字连串，永不命中
        if len(parts) == 2 and all(2 <= len(x) <= 32 for x in parts):
            out.append(parts[0] + '，')
            out.append(parts[1] + (tail or '。'))
        else:
            out.append(p)
    return out


def build(doc):
    L = ['-- V018：三百首 94 首——选本正文经维基文库诗页逐字复核（底本《全唐詩》或异源他书）入库。',
         '-- 生成器：poetry-agent-platform/content-agent/pipeline/data/chronology/emit_v018.py',
         '-- 资格判定与逐首明细：corpus/tang300-ws-poems-proof.{json,md}',
         '-- 全部 DRAFT/PENDING；人工核验走 scripts/db/verify-sources.sh --apply，本文件不做核验。',
         "-- 执行前确认连接：",
         "SHOW VARIABLES LIKE 'character_set_client'; -- 须为 utf8mb4（与 V001–V017 同规，本文件族一律不写 SET NAMES，字符集属于连接配置）",
         '',
         '-- ---------- 0. 迁移台账 ----------']
    desc = ('125 Tang-300 poems whose text verbatim-matches Wikisource (poem pages declaring their base text, '
            'or Quan Tangshi volume pages with entry anchors). All rows DRAFT/PENDING')
    assert len(desc) <= 200, f'schema_version 描述超长 {len(desc)}'
    L.append('INSERT INTO poetry_schema_version (version_no, description) VALUES '
             f'(18, {sql_str(desc)}) '
             'ON DUPLICATE KEY UPDATE description = VALUES(description);')

    # ---------- 1. 作者 ----------
    persons = [a for a in doc['authors'] if doc['persons'][a] not in EXISTING]
    if persons:
        L += ['', '-- ---------- 1. 新作者（正文旁两个转录署名一致；生平年份留空，不编） ----------']
        rows = [{'id': doc['persons'][a], 'entity_type': 'PERSON',
                 'slug': doc['persons'][a][len('person-'):], 'title': a,
                 'summary': f'《唐詩三百首》收其詩 {doc["author_poems"][a]} 首；正文复核时维基文库页面署名与选本一致'
                            '（tang300-ws-poems-proof）。生卒年里未核，留空。',
                 'start_year': None, 'end_year': None, 'time_precision': 'UNKNOWN'}
                for a in persons]
        L.append(guard_insert(
            ('id', 'entity_type', 'slug', 'title', 'summary', 'start_year', 'end_year', 'time_precision'),
            'poetry_content', rows, 'x.id = t.id'))
        L.append('')
        L.append(guard_insert(('id', 'dynasty_id'), 'poetry_person',
                              [{'id': doc['persons'][a], 'dynasty_id': 'dynasty-tang'} for a in persons],
                              'x.id = t.id'))
    else:
        L += ['', '-- ---------- 1. 无新作者（全部沿用 V002/V016 已有人物行） ----------']

    # ---------- 2. source（每页一行；同页多首共用；V011 已建的行只引用不重建） ----------
    L += ['', '-- ---------- 2. 来源：逐页定位（诗页 header 自述底本 / 卷页锚点 = 硬证据） ----------']
    rows = []
    for s in doc['sources']:
        if not s.get('new', True):
            continue                       # V011 的行：引用它，不重建、不回滚删
        title = (f"维基文库《唐詩三百首》页面：{s['page']}" if s['route'] == 'ws'
                 else f"《全唐詩》{s['page']}（维基文库录入本）")
        rows.append({'id': s['id'], 'title': title,
                     'author': None,
                     'edition': s['base'] or '页面未声明底本（本迁移只收声明了底本的页面）',
                     'url': f"https://zh.wikisource.org/wiki/{s['page']}",
                     'rights_note': ('维基文库录入本，公有领域古籍。本行由 corpus 下复核脚本逐字定位；'
                                     '录入本本身可能需据扫描版校对，核验状态保持 PENDING。'),
                     'verification_status': 'PENDING'})
    L.append(guard_insert(('id', 'title', 'author', 'edition', 'url', 'rights_note', 'verification_status'),
                          'poetry_source', rows, 'x.id = t.id'))

    # ---------- 3. work ----------
    # preexisting 的诗（春望=work-chun-wang，V002 建、V004/V017 在用）跳过 content/work 行——
    # 同一首诗两个 work 行会让产品展示两首春望、证据各自漂移；它的证据只挂既有 id。
    L += ['', '-- ---------- 3. 作品（id=选本序号；title 照录选本，题名分歧见复核报告，不裁决；既有 work 只挂证据不重建） ----------']
    fresh = [w for w in doc['works'] if not w['preexisting']]
    rows = [{'id': w['work_id'], 'entity_type': 'WORK',
             'slug': w['work_id'][len('work-'):], 'title': w['title'],
             'summary': w['summary'], 'start_year': None, 'end_year': None,
             'time_precision': 'UNKNOWN'} for w in fresh]
    L.append(guard_insert(('id', 'entity_type', 'slug', 'title', 'summary', 'start_year', 'end_year', 'time_precision'),
                          'poetry_content', rows, 'x.id = t.id'))
    L.append('')
    L.append(guard_insert(('id', 'dynasty_id', 'genre'), 'poetry_work',
                          [{'id': w['work_id'], 'dynasty_id': 'dynasty-tang', 'genre': w['genre']}
                           for w in fresh], 'x.id = t.id'))

    # ---------- 4. 作者署名（claim + 双引证 + work_author 行） ----------
    L += ['', '-- ---------- 4. 作者署名：选本与维基文库页面一致（PENDING——判定权在人） ----------']
    rows = []
    for w in doc['works']:
        rows.append({'id': w['claim_author'], 'subject_id': w['work_id'],
                     'property_key': 'author.attribution',
                     'value_text': w['author_text'],
                     'claim_kind': 'FACT', 'certainty': 'LIKELY'})
    L.append(guard_insert(('id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'),
                          'poetry_claim', rows, 'x.id = t.id'))
    L.append('')
    rows = [{'claim_id': w['claim_author'], 'source_id': w['source_id'],
             'locator': w['author_locator'],
             'evidence_excerpt': w['author_excerpt']} for w in doc['works']]
    L.append(guard_insert(('claim_id', 'source_id', 'locator', 'evidence_excerpt'),
                          'poetry_citation', rows,
                          'x.claim_id = t.claim_id AND x.source_id = t.source_id'))
    L.append('')
    rows = [{'work_id': w['work_id'], 'person_id': PERSON[w['author']],
             'attribution': 'PENDING', 'claim_id': w['claim_author']}
            for w in doc['works'] if not w['preexisting']]
    # （既有 work 不补这行：V002 已为 work-chun-wang×person-du-fu 绑过署名，
    #  PK=(work_id,person_id) 下再插只会撞车；新署名断言仍以 claim+citation 存在。）
    L.append(guard_insert(('work_id', 'person_id', 'attribution', 'claim_id'),
                          'poetry_work_author', rows, 'x.work_id = t.work_id AND x.person_id = t.person_id'))

    # ---------- 5. 正文版本 + 行（claim 引本地两份 JSON 作旁证） ----------
    L += ['', '-- ---------- 5. 正文版本：维基文库页面底本；异体折叠只作判定、正文存选本原样 ----------']
    rows = [{'id': w['text_id'], 'work_id': w['work_id'],
             'version_code': w['tier'],
             'label': w['label'], 'script': 'TRADITIONAL',
             'source_id': w['source_id'], 'source_locator': w['locator']} for w in doc['works']]
    L.append(guard_insert(('id', 'work_id', 'version_code', 'label', 'script', 'source_id', 'source_locator'),
                          'poetry_text_version', rows, 'x.id = t.id'))
    L.append('')
    rows = []
    for w in doc['works']:
        for i, line in enumerate(w['lines'], 1):
            rows.append({'version_id': w['text_id'], 'line_seq': i, 'content': line})
    L.append(guard_insert(('version_id', 'line_seq', 'content'), 'poetry_text_line', rows,
                          'x.version_id = t.version_id AND x.line_seq = t.line_seq'))
    L.append('')
    rows = []
    for w in doc['works']:
        rows.append({'id': w['claim_text'], 'subject_id': w['work_id'],
                     'property_key': 'text.body',
                     'value_text': w['text_claim'],
                     'claim_kind': 'FACT', 'certainty': 'KNOWN'})
    L.append(guard_insert(('id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'),
                          'poetry_claim', rows, 'x.id = t.id'))
    L.append('')
    rows = []
    for w in doc['works']:
        rows.append({'claim_id': w['claim_text'], 'source_id': w['source_id'],
                     'locator': w['locator'], 'evidence_excerpt': w['excerpt']})
    L.append(guard_insert(('claim_id', 'source_id', 'locator', 'evidence_excerpt'),
                          'poetry_citation', rows,
                          'x.claim_id = t.claim_id AND x.source_id = t.source_id'))
    L.append('')
    rows = []
    for w in doc['works']:
        rows.append({'subject_id': w['work_id'], 'property_key': 'text.body', 'claim_id': w['claim_text']})
        rows.append({'subject_id': w['work_id'], 'property_key': 'author.attribution',
                     'claim_id': w['claim_author']})
    L.append(guard_insert(('subject_id', 'property_key', 'claim_id'),
                          'poetry_claim_selection', rows,
                          'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    # ---------- 6. 回滚 ----------
    L += ['', '-- ---------- 6. 清理指引 ----------',
          '-- 精确回滚见 recovery/V018_rollback.sql（按本文件的全部 id 反序删除；不删既有 person 行）。']
    return '\n'.join(L) + '\n'


def build_rollback(doc):
    L = ['-- V018 精确回滚：只删 V018 插入的行（id 全枚举，不按前缀通配——前缀可能撞上别人的行）。',
         '-- 不删 poetry_content/poetry_person 里的既有作者行（V002/V016 先占，V018 只补了新的）。']

    def del_by(table, col, vals, chunk=40):
        out = []
        for i in range(0, len(vals), chunk):
            got = ', '.join(sql_str(v) for v in vals[i:i + chunk])
            out.append(f'DELETE FROM {table} WHERE {col} IN ({got});')
        return out
    # work 级三表（work/content/work_author）只删本迁移**真的插过**的行：
    # 《春望》的 work-chun-wang 是 V002 的行，V004/V017 都在用，删了就把已发布场景砸了。
    fresh = [w for w in doc['works'] if not w['preexisting']]
    wids = [w['work_id'] for w in fresh]
    tids = [w['text_id'] for w in doc['works']]     # 文本/断言/引证是 V018 新造的，既有诗也照删
    cids = [w['claim_text'] for w in doc['works']] + [w['claim_author'] for w in doc['works']]
    sids = [s['id'] for s in doc['sources'] if s.get('new', True)]   # V011 的行不归本文件删
    pids = [doc['persons'][a] for a in doc['authors'] if doc['persons'][a] not in EXISTING]
    for table, col, vals in (('poetry_claim_selection', 'claim_id', cids),
                             ('poetry_citation', 'claim_id', cids),
                             ('poetry_claim', 'id', cids),
                             ('poetry_text_line', 'version_id', tids),
                             ('poetry_text_version', 'id', tids),
                             ('poetry_work_author', 'work_id', wids),
                             ('poetry_work', 'id', wids),
                             ('poetry_content', 'id', wids),
                             ('poetry_source', 'id', sids)):
        if vals:
            L += del_by(table, col, vals)
    if pids:
        L += del_by('poetry_content', 'id', pids)
        L += del_by('poetry_person', 'id', pids)
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 18;')
    return '\n'.join(L) + '\n'


def audit(doc, sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里出现反斜杠（sql_mode 相关，需人工确认）')
    # 主键唯一（文档内）
    def dup(vals, what):
        seen = set()
        for v in vals:
            if v in seen:
                bad.append(f'{what} 文档内重复：{v}')
            seen.add(v)
    wids = [w['work_id'] for w in doc['works']]
    dup(wids, 'work_id')
    # 既有 work（work-chun-wang）绝不能出现在本迁移的 **work 级三表** INSERT 里——同一首诗
    # 有两个 work 行是最坏的一种数据缺陷（正文/场景各挂一边）。text_version/claim/citation
    # 挂到既有 work 上是刻意的（证据就该长在真 work 上），不在本检查范围。扫真正的语句体。
    for pid in set(EXISTING_WORKS.values()):
        for m in re.finditer(r"INSERT INTO (poetry_(?:work|work_author|content))\b", sql):
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
            if f"'{pid}'" in sql[m.start():end]:
                bad.append(f'既有 work {pid} 出现在 {m.group(1)} 的 INSERT 里（绝不能造第二个）')
    dup([w['text_id'] for w in doc['works']], 'text_id')
    dup([w['claim_text'] for w in doc['works']], 'claim_text')
    dup([w['claim_author'] for w in doc['works']], 'claim_author')
    dup([s['id'] for s in doc['sources']], 'source_id')
    dup([PERSON[a] for a in doc['authors']], 'person_id')
    dup([(w['work_id'], PERSON[w['author']]) for w in doc['works']], 'work_author PK')
    dup([(w['text_id'], i) for w in doc['works'] for i in range(1, len(w['lines']) + 1)], 'text_line PK')
    dup([(w['work_id'], f"ws-{w['tier']}") for w in doc['works']], 'text_version UK')
    # 宽度（真实 DDL：content slug120/title200, source title300/edition300/url1000,
    # text_version version_code64/label200/source_locator300, text_line500, claim id64/pk64, citation locator300）
    for w in doc['works']:
        checks = [(w['work_id'], 64, 'work_id'), (w['work_id'][5:], 120, 'slug'), (w['title'], 200, 'title'),
                  (w['text_id'], 64, 'text_id'), (w['tier'], 64, 'version_code'),
                  (w['label'], 200, 'label'), (w['locator'], 300, 'source_locator'),
                  (w['claim_text'], 64, 'claim id'), (w['claim_author'], 64, 'claim id'),
                  (w['text_claim'], None, 'claim.value_text TEXT'),
                  (w['excerpt'], 500, 'citation excerpt(文本列,预警)'), (w['summary'], 500, 'content.summary(文本列,预警)')]
        for v, cap, what in checks:
            if cap and len(v) > cap:
                bad.append(f'{what} 超长 {len(v)}>{cap}: {v[:40]}')
        for line in w['lines']:
            if len(line) > 500:
                bad.append(f"poetry_text_line 超长 {len(line)}>500: {line[:30]}")
    for s in doc['sources']:
        if not s.get('new', True):
            continue                       # 引用行不归本文件生成，宽度由 V011 的 audit 管
        title = (f"维基文库《唐詩三百首》页面：{s['page']}" if s['route'] == 'ws'
                 else f"《全唐詩》{s['page']}（维基文库录入本）")
        for v, cap, what in ((s['id'], 64, 'source id'), (title, 300, 'source title'),
                             (s['base'] or '', 300, 'edition'),
                             (f"https://zh.wikisource.org/wiki/{s['page']}", 1000, 'url')):
            if len(v) > cap:
                bad.append(f'{what} 超长 {len(v)}>{cap}: {v[:40]}')
    # 生成文件里每条 INSERT INTO poetry_* 都必须带守卫。
    # 不能拿 `[^;]*;` 截语句：字面量里就有分号时会在语句中间断开，把有守卫的语句误报成没守卫
    # （第一版就栽在自己的台账描述上）。按 SQL 字符串语义扫到真正的语句结尾。
    for m in re.finditer(r'INSERT INTO (poetry_\w+)', sql):
        i, in_str = m.end(), False
        while i < len(sql):
            ch = sql[i]
            if in_str:
                if ch == "'":
                    if i + 1 < len(sql) and sql[i + 1] == "'":
                        i += 1                      # '' 是字面量里的一个引号
                    else:
                        in_str = False
            elif ch == "'":
                in_str = True
            elif ch == ';':
                break
            i += 1
        frag = sql[m.start():i]
        if 'WHERE NOT EXISTS' not in frag and 'ON DUPLICATE KEY' not in frag:
            bad.append(f'{m.group(1)} 的 INSERT 没有幂等守卫')
    return bad


def collect():
    sel = json.loads(SEL_PATH.read_text(encoding='utf-8'))
    ev = {}
    # 路线一：《唐詩三百首》诗页（header 自述底本，最直接的来源证据）
    proof = json.loads((CORPUS / 'tang300-ws-poems-proof.json').read_text(encoding='utf-8'))
    for r in proof:
        if r['verdict'] not in VERDICTS:
            continue
        fold = r['verdict'].endswith('FOLD_EXACT')
        xbook = r['verdict'].startswith('WP_XBOOK')
        ev[r['seq']] = {
            'route': 'ws', 'page': r['ws_page'], 'base': r.get('prov_ref') or '未声明',
            'route_kind': '异源他书，跨书比对' if xbook else '同书异转录',
            'fold': fold, 'xbook': xbook, 'anchor': None, 'fold_note': r.get('detail') or '',
            'page_author': r.get('page_author')}
    # 路线二：《全唐詩》卷页。只收**带锚点**的命中（锚=紧贴正文前的「卷NNN_NN題目作者」或
    # 「===題目===」条目头）；没锚的子串命中回答不了「命中的真是这首吗」，进人工清单不入库。
    vol = json.loads((CORPUS / 'tang300-wikisource-proof.json').read_text(encoding='utf-8'))
    for r in vol:
        if r.get('ws') in ('WS_RAW_EXACT', 'WS_FOLD_EXACT') and r.get('ws_anchor') and r['seq'] not in ev:
            m = re.search(r'卷(\d+)', r['ws_page'])
            ev[r['seq']] = {
                'route': 'vol', 'page': r['ws_page'],
                'base': f"{r['ws_page']}（维基文库《全唐詩》录入本）",
                'route_kind': '同书异转录',
                'fold': r['ws'] == 'WS_FOLD_EXACT', 'xbook': False,
                'anchor': r['ws_anchor'], 'fold_note': r.get('ws_fold_chars') or '',
                'page_author': r['author'] if r['author'] in (r['ws_anchor'] or '') else None}

    works, sources, authors, author_poems = [], [], [], {}
    src_by_page = {}
    for seq in sorted(ev):
        r = ev[seq]
        p = sel[seq - 1]
        n = f'{seq:03d}'
        author = p['author']
        if author not in PERSON:
            raise SystemExit(f'作者表缺 {author}（seq {seq}）——手写映射不许静默漏人')
        if author not in authors:
            authors.append(author)
        author_poems[author] = author_poems.get(author, 0) + 1
        page = r['page']
        if page not in src_by_page:
            if r['route'] == 'ws':
                sid = f'source-ws-t300-{n}'
                src_by_page[page] = {'id': sid, 'page': page, 'base': r['base'], 'route': 'ws'}
            else:
                m = re.search(r'卷(\d+)', page)
                # V011 已为《春望》建过 source-quantangshi-224——同卷直接引用，不再造一行。
                # 「new=False」的行：本迁移引用它，但回滚**不能删它**（不归本文件所有）。
                sid = f'source-quantangshi-{int(m.group(1))}'
                src_by_page[page] = {'id': sid, 'page': page, 'base': r['base'], 'route': 'vol',
                                     'new': sid not in EXISTING_SOURCES}
        src = src_by_page[page]
        fold, xbook = r['fold'], r['xbook']
        base = r['base']
        tier = {'ws': ('ws-xbook' if xbook else 'ws') + ('-fold' if fold else '-raw'),
                'vol': 'vol' + ('-fold' if fold else '-raw')}[r['route']]
        lines = split_lines(p.get('paragraphs') or [])
        excerpt = (lines[0] + ('……' + lines[-1] if len(lines) > 1 else ''))[:180]
        genre = next((GENRE[t] for t in (p.get('tags') or []) if t in GENRE), None)
        # 《春望》(seq 208) 等已有 work 的诗：证据挂到既有 id，不造第二个 work。
        preexisting = seq in EXISTING_WORKS
        work_id = EXISTING_WORKS.get(seq, f'work-t300-{n}')
        ev_src = ('维基文库页面' if r['route'] == 'ws' else '维基文库《全唐詩》卷页')
        summary = (f"《唐詩三百首》第 {seq} 首。正文与{ev_src}逐字一致"
                   + (f"（先折叠登记过的异体字：{r['fold_note'][:60]}）" if fold and r['fold_note']
                      else ('（先折叠登记过的异体字）' if fold else ''))
                   + (f"；底本为他书 {base}，属跨书比对" if xbook else f"；底本 {base}")
                   + ('' if r['route'] == 'ws' else f"；卷页锚点「{r['anchor']}」")
                   + '。判定与异文登记：corpus 下 tang300-ws-poems-proof / tang300-wikisource-proof。')
        label = (ev_src + ('（异体折叠后一致，存选本原样）' if fold else '（逐字一致）')
                 + (f'；底本 {base}' if base != '未声明' else ''))[:200]
        text_claim = ('选本正文与' + ev_src + ('折叠异体字后一致' if fold else '逐字一致'))
        if fold and r['fold_note']:
            text_claim += f"（{r['fold_note'][:60]}）"
        text_claim += f'；底本 {base}（{r["route_kind"]}）'
        if r['route'] == 'vol':
            text_claim += f"；锚点「{r['anchor']}」"
        text_claim += '。本地御定/poet.tang 为同仓库转录，只作旁注，不作本断言的依据。'
        cite_locator = f"页面 {page}" + (f"（锚点 {r['anchor']}）" if r['anchor'] else '')[:280]
        # 作者断言按证据强弱分开写：锚里带署名的是硬证据；分节锚（==題目==）不带署名，
        # 作者归属来自卷的编排体例——弱一档，话要说清楚。
        if r['page_author']:
            author_text = f"署名 {author}：选本与{ev_src}两处转录一致" + \
                          (f"（锚点含署名：「{r['anchor']}」）" if r['anchor'] else '') + '。'
            author_excerpt = r['anchor'] or f"header author={r['page_author']}"
            # 诗页有 header 的 author 字段可指；卷页没有——证据就是锚点本身，locator 照实写。
            author_locator = f"页面 {page}" + ('（header author 字段）' if r['route'] == 'ws'
                                              else f"（锚点 {r['anchor']}）")
        else:
            author_text = (f"署名 {author}：选本所署；{ev_src}按 {r['anchor']} 收录，"
                           '锚点未含署名，作者归属依该卷编排体例——更弱一档。')
            author_excerpt = f"锚点「{r['anchor']}」（不含作者名）"
            author_locator = f"页面 {page}（卷页无 header；归属证据在锚点）"
        works.append({'work_id': work_id, 'title': p['title'], 'author': author,
                      'genre': genre, 'summary': summary, 'tier': tier, 'base': base,
                      'preexisting': preexisting,
                      'text_id': f'text-{work_id}-ws', 'label': label,
                      'source_id': src['id'], 'locator': cite_locator[:300],
                      'page_title': page, 'page_author': r['page_author'],
                      'lines': lines, 'excerpt': excerpt, 'text_claim': text_claim,
                      'author_text': author_text, 'author_excerpt': author_excerpt[:280],
                      'author_locator': author_locator[:300],
                      'claim_text': f'claim-t300-{n}-text', 'claim_author': f'claim-t300-{n}-author'})
    sources = sorted(src_by_page.values(), key=lambda s: s['id'])
    return {'works': works, 'sources': sources, 'authors': authors,
            'persons': PERSON, 'author_poems': author_poems}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-sql', required=True)
    ap.add_argument('--out-rollback', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    doc = collect()
    sql = build(doc)
    rb = build_rollback(doc)
    bad = audit(doc, sql)
    if bad:
        print('AUDIT FAIL:')
        for b in bad:
            print(' -', b)
        sys.exit(1)
    if args.dry_run:
        print(f"dry run: works={len(doc['works'])} sources={len(doc['sources'])} "
              f"authors={len(doc['authors'])} lines={sum(len(w['lines']) for w in doc['works'])} "
              f"sql_bytes={len(sql.encode())}")
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f"wrote {args.out_sql} ({len(sql.encode())} B)")
    print(f"wrote {args.out_rollback} ({len(rb.encode())} B)")
    print(f"works={len(doc['works'])} sources={len(doc['sources'])} "
          f"authors={len(doc['authors'])} new_persons={sum(1 for a in doc['authors'] if PERSON[a] not in EXISTING)} "
          f"lines={sum(len(w['lines']) for w in doc['works'])}")


if __name__ == '__main__':
    main()
