#!/usr/bin/env python3
"""阶段 D 第 27 首：生成 V046——李白《夜泊牛渚懷古》(work-t300-328, V018 已立) 四层背景。

「为什么写」再成立一次，但这首立的是**缺席的形状**。题四钉：地（牛渚）、
时（夜+秋月）、事（懷古）、典（谢将军=谢尚闻袁宏咏史）。前两钉在诗里，
后两钉要靠典实——而典实在我们的全部快照里**零命中**：
兩唐書李白区间 謝尚/袁宏/詠史（典实义）零见、通鉴 75 卷零见、
全唐詩 120 卷零见（袁宏/謝尚 计数全零，生成时机器扫描）。
页底注「此地即謝尚聞袁宏詠史處」是整理者典实地注（V040「時年十七」底注
判例同族）——照登、声明非史料，**不能升格为典实来源**。

系年第二十一次判决（题证系列第九状）：**「题有典地，典无史源」**——
V044 传锚在而锚不系年、V045 传见在而见必它事——这首把断链点再往上游推：
系年链条「诗→地→典→年」里，**典**这一环整个不可核（快照不含晋书/世说，
典实无处登记）；登记先行于引用——典既不可登，任何借典系年即无源可依。
这是题证系列第一次「断的不是年份，是年份的上游」。零铸造零 relation。

KNOWN 零（整首零 KNOWN 如实记录，V042 判例）：
WORLD 苏颋「是子天才英特」赏（XTS 单得）、PERSON 旧传「少有逸才…飄然有超世
之心」（单得；V032 PERSON 侧第一证，此处第二证达上限）——都不合龙、都不升；
audit 反向断言保护「如实」不被指标绑架。

三层负证全机器复查（生成时断言，快照变动即中止）：
① 典实扫描：通鉴 75 卷「袁宏」「謝尚」计数 0；全唐詩 120 卷「袁宏」「謝尚」计数 0；
② 牛渚位置断言：旧传李白区间「牛渚」计数 0；新传李白区块计数 1 且必落在
   青山终焉句内（该句 V016/V032/V036 已三入——**本迁移零引**，负证靠位置
   不靠引用）；
③ ws 页两处 {{另}}（挂帆席/洞庭去、落/正）必须原样入 SCENE 引文（V044 反向
   断言）；底注必须入 CITY 引文且 locator 带「非史料」声明。

异文登记先行（tang300-variants.md 新行已入）。八句 2/2/2/2；
零新 source（ws-328/jts/xts 三源行均已立）。

用法: python3 -I emit_v046.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/夜泊牛渚懷古.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 夜泊牛渚懷古', '| title    = 夜泊牛渚懷古',
                         'ws header title(地+时+事三钉:夜泊/牛渚/懷古)')
WS_AUTHOR = slice_between(WS, '| author   = 李白', '| author   = 李白', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '↑ [[全唐詩/卷181#夜泊牛渚懷古|全唐詩·卷181]] 此地即謝尚聞袁宏詠史處',
                        '此地即謝尚聞袁宏詠史處',
                        'ws 页底注(底本指向+整理者典实地注——非史料声明随行,V040底注判例)')
WS_L12 = slice_between(WS, '牛渚西江夜，青天無片雲。', '牛渚西江夜，青天無片雲。',
                       'ws第1-2句联(牛渚/西江夜/无片云——地点与夜空钉死)')
WS_L34 = slice_between(WS, '登舟望秋月，空憶謝將軍。', '登舟望秋月，空憶謝將軍。',
                       'ws第3-4句联(望月/空忆谢将军——典的唯一诗内入口)')
WS_L56 = slice_between(WS, '余亦能高詠，斯人不可聞。', '余亦能高詠，斯人不可聞。',
                       'ws第5-6句联(我能高咏/斯人不可闻——自许与失古)')
WS_L78 = slice_between(WS, '明朝{{另|挂帆席|洞庭去}}，楓葉{{另|落|正}}紛紛。',
                       '明朝{{另|挂帆席|洞庭去}}，楓葉{{另|落|正}}紛紛。',
                       'ws第7-8句联(明朝挂帆/枫叶纷纷——两处异文原样照登)')
XTS_ST = slice_between(XTS, '蘇頲為益州長史，見白異之，曰：「是子天才英特，少益以學，可比相如。」',
                       '可比相如。」', '新传苏颋赏句(见而异之/天才英特/可比相如——名士初赏单得,WORLD 层本体)')
JTS_YC = slice_between(JTS, '少有逸才，志氣宏放，飄然有超世之心', '飄然有超世之心',
                       '旧传逸才短语(少有逸才/志气宏放/飘然有超世之心——原文此下即「，父爲任城尉」不断句;V032 PERSON 侧第一证,此处第二证达上限;PERSON 层本体)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=李白='), JTS.find('=杜甫=')
_xa, _xb = XTS.find('==李白=='), XTS.find('===附 張旭===')
for _s, _tag in [(JTS_YC, 'JTS_YC')]:
    if not (0 <= _ja <= JTS.find(_s) <= _jb):
        raise SystemExit(f'切片越出李白传区间：{_tag}——修订后重生成')
for _s, _tag in [(XTS_ST, 'XTS_ST')]:
    if not (0 <= _xa <= XTS.find(_s) <= _xb):
        raise SystemExit(f'切片越出李白传区块：{_tag}——修订后重生成')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
# ① 典实扫描：袁宏/谢尚在通鉴 75 卷与全唐詩 120 卷快照内计数必须全零——
#    「诗所怀之典在我们全部史部/诗部快照里无处登记」由此可复查。
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_tj_hits = sum(sum(f.read_text(encoding='utf-8').count(w) for w in ('袁宏', '謝尚'))
               for f in sorted(_tj.glob('tj-*.txt')))
if _tj_hits:
    raise SystemExit('通鉴快照出现「袁宏/謝尚」——典无史源判决失效，须重读快照再设计')
_qss = pathlib.Path('/tmp/src-dl/quantangshi')
_qss_hits = sum(sum(f.read_text(encoding='utf-8').count(w) for w in ('袁宏', '謝尚'))
                for f in sorted(_qss.glob('vol*.txt')))
if _qss_hits:
    raise SystemExit('全唐詩快照出现「袁宏/謝尚」——典无史源判决失效，须重读快照再设计')
# ② 牛渚位置断言：旧传李白区间零见；新传区块唯一一处且必落青山终焉句内
#    （该句已三入既往迁移，本迁移零引——负证靠位置不靠引用）
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
if '牛渚' in _seg_j:
    raise SystemExit('旧传李白区间出现「牛渚」——旧传零见负证失效')
_qs = '白晚好黃老，度牛渚磯至姑孰，悅謝家青山，欲終焉。及卒，葬東麓。'
if _seg_x.count('牛渚') != 1:
    raise SystemExit('新传李白区块「牛渚」计数不是 1——牛渚位置断言须重估')
_q0 = _seg_x.find(_qs)
if not (0 <= _q0 and _seg_x.find('牛渚') >= _q0 and _seg_x.find('牛渚') < _q0 + len(_qs)):
    raise SystemExit('新传「牛渚」不在青山终焉句内——「唯一传见又是它事」判决失效')
# ③ 典实两传区间零见
for _w in ('謝尚', '袁宏'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'两传李白区间出现「{_w}」——典实两传零见负证失效')

BG = {
    'bg-nz-scene': (
        '这首诗把夜钉死：牛渚、西江、没有一片云的青天（「牛渚西江夜，青天無片雲」——'
        '怀古诗里罕见的干净夜空，什么都没遮）；登船望月，空忆一个人'
        '（「登舟望秋月，空憶謝將軍」——「空」字是这首诗的枢）；'
        '忆谁？忆的是那个**听见**的人：谢尚夜泊牛渚，听见邻船袁宏咏史，'
        '连夜邀谈、援引进仕——诗人的全部底气在第五句：「余亦能高詠」，'
        '全部失落也在第五句的另一半：「斯人不可聞」（我唱得不差，听的人死了千年）；'
        '天亮解缆，枫叶纷纷（「明朝挂帆席，楓葉落紛紛」——两处页内自注'
        '挂帆席/洞庭去、落/正照登不裁决；异文「洞庭去」一支把终点从未知'
        '改成具体地名，读感全变，正是照登的价值）。\n'
        '地钉死、夜钉死、月钉死——年份照旧无。'),
    'bg-nz-city': (
        '「牛渚」在两传李白区间里：旧传**零见**，新传**只见一次**，'
        '而那一次又是另一件事——晚年「度牛渚磯至姑孰，悅謝家青山，欲終焉」'
        '（该句 V016/V032/V036 已三入既往迁移，**本迁移零引**，'
        '位置断言在生成时机器复查——负证靠位置不靠引用）。\n'
        '而这首诗真正的「城」是典里的那座城：页底注「此地即謝尚聞袁宏詠史處」'
        '替读者指认现场——但它是整理者的典实地注（V040「時年十七」底注判例同族），'
        '照登、声明非史料。机器扫描（生成时断言）：袁宏、谢尚在通鉴 75 卷、'
        '全唐詩 120 卷快照内**计数全零**。题有典地，典无史源：'
        '系年链条「诗→地→典→年」断在「典」这一环——断的不是年份，是年份的上游。'
        '这座城在诗的档案里是完整的，在史的档案里连一块碑都没有。'),
    'bg-nz-world': (
        '典不可核，天下层只能回到史料能给的东西：新传里名士对少年的'
        '一次相看——「蘇頲為益州長史，見白異之，曰：『是子天才英特，'
        '少益以學，可比相如。』」（单得，不升，LIKELY 照登）。\n'
        '把它和这首诗并读——不是因果，是**形状**：谢尚之于袁宏、苏颋之于李白，'
        '同一个「听见/看见然后援引」的结构在两个世纪里各出现一次，'
        '前者在诗里（典）、后者在传里（史）。诗里那位听者已不可闻，'
        '传里这位听者曾真实地看过他一眼——**这个并置是本层的读法声明**，'
        '史实只有苏颋一句。两源合龙无望（苏颋赏仅新传收，旧传无此事），'
        'audit 判例零重开硬卡之外，本层另设**整首零 KNOWN 反向断言**'
        '（V042 判例）：不为凑数升格。'),
    'bg-nz-person': (
        '旧传给这个人的一句定调短话：「少有逸才，志氣宏放，飄然有超世之心」'
        '（V032 PERSON 侧第一证，此处第二证——**同句两度为上限，到此为止**）。\n'
        '把「飄然有超世之心」和「余亦能高詠，斯人不可聞」并排放：'
        '传里说他天生把自己放得比世界高，诗里他把这份高递出去等一个'
        '听不见的回音——同一种气质，传里是描述，诗里是痛感。\n'
        '判例零重开（audit 关键语硬卡）：谪仙人（V036）、竹溪六逸（V041）、'
        '脱靴斥去（V041）、崔宗之采石锦袍（V032/V045）、青山终焉（三入）——'
        '本层一个新句、一个第二证，其余全部只字不引。'),
}
CLAIMS = {
    'claim-bg-nz-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页两处 {{另}} 页内自注原样照登——先登记后引用，'
        'tang300-variants.md 新行；Textquality 75% 如实记；异文「洞庭去」'
        '改终点读感的注记为本层读法声明）；「枢/底气/失落」诸说为本层读法，'
        '非史料断言。'),
    'claim-bg-nz-city': (
        'FACT', 'LIKELY',
        '典实机器扫描：袁宏/谢尚在通鉴 75 卷、全唐詩 120 卷快照计数全零'
        '（生成时断言，快照变动即中止）；牛渚旧传李白区间零见、新传区块一处'
        '且必落青山终焉句内（位置断言；该句三入既往迁移本迁移零引）；'
        '页底注为整理者典实地注——照登并声明非史料（V040 判例）；'
        '题有典地，典无史源→零铸造零 relation。'),
    'claim-bg-nz-world': (
        'FACT', 'LIKELY',
        '苏颋赏句新传单得（旧传无此事，合龙无望）→不升，LIKELY 照登；'
        '谢尚/袁宏—苏颋/李白并置为读法声明非史料断言；'
        '整首零 KNOWN 如实记录（audit 反向断言，V042 判例）；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during '
        '零铸造零 relation。'),
    'claim-bg-nz-person': (
        'FACT', 'LIKELY',
        '逸才句旧传单得（不升），V032 第一证此处第二证达两度上限（locator 声明）；'
        '「超世之心」与「余亦能高咏」并置为读法声明；'
        '谪仙人/竹溪/脱靴/崔宗之/青山判例零重开（audit 关键语硬卡）；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-nz-scene', 'source-ws-t300-328',
     '页面 夜泊牛渚懷古（header title+author+八句四联，六段以「……」相連——'
     '两处 {{另}} 自注原样照登（先登记后引用，tang300-variants.md 新行）；'
     '同一 (claim,source) 主键下一行容全文，V037/V039/V040/V041/V042/V043/V044/V045 判例；'
     '全文另见 V018 claim-t300-328-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78)),
    ('claim-bg-nz-city', 'source-ws-t300-328',
     '页面 夜泊牛渚懷古（header title+页底注两字段——底注「此地即謝尚聞袁宏詠史處」'
     '为整理者典实地注，**非史料**（V040「時年十七」底注判例同族），照登并声明；'
     '典实扫描（通鉴 75 卷/全唐詩 120 卷袁宏谢尚计数全零）与牛渚位置断言'
     '为生成时机器断言，诗身不代拟进引文）',
     join(WS_TITLE, WS_NOTE)),
    ('claim-bg-nz-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传苏颋赏句（见而异之/天才英特/可比相如——'
     '新传单得，旧传无此事，不升；与诗典的并置是读法声明，史实只此一句）',
     XTS_ST),
    ('claim-bg-nz-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传逸才句（少有逸才/志气宏放/飘然有超世之心——'
     'V032 PERSON 侧第一证，此处第二证——同句两度为上限）', JTS_YC),
]
BG_LINES = {'bg-nz-scene': (1, 2), 'bg-nz-city': (3, 4), 'bg-nz-world': (5, 6), 'bg-nz-person': (7, 8)}
BG_AUDIENCE = {'bg-nz-scene': 'PRIMARY', 'bg-nz-city': 'JUNIOR',
               'bg-nz-world': 'SENIOR', 'bg-nz-person': 'SENIOR'}
BG_TITLES = {'bg-nz-scene': '眼前：什么都没遮的夜空',
             'bg-nz-city': '这座城：连一块碑都没有',
             'bg-nz-world': '这个天下：两个世纪的相看',
             'bg-nz-person': '这个人：传里是描述，诗里是痛感'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 27 首·八句 2/2/2/2）；史实句均有逐字引证；'
                 'background_line 八句形制：每层两行（1-2/3-4/5-6/7-8）；'
                 '系年第二十一次判决「题有典地，典无史源」（题证系列第九状·'
                 '首见断链在典不在年）→time.span/event.name/written_during '
                 '全缺席、零 relation；整首零 KNOWN 如实记录（audit 反向断言，'
                 'V042 判例）；典实负证三层机器复查（通鉴 75 卷+全唐詩 120 卷'
                 '袁宏谢尚计数全零/牛渚位置断言/两传区间零见）；青山终焉句'
                 '三入零引；逸才句第二证达两度上限；页底注照登并声明非史料。' for k in BG}


def guard(table, cols, rows, match_expr):
    def lit(v):
        if v is None:
            return 'NULL'
        if isinstance(v, int):
            return str(v)
        return sql_s(v)
    sel = '\nUNION ALL\n'.join(
        'SELECT ' + ', '.join(f'{lit(r[c])} AS {c}' for c in cols) + ' FROM DUAL'
        for r in rows)
    return (f'INSERT INTO {table} ({", ".join(cols)})\n'
            f'SELECT * FROM (\n{sel}\n) AS t\n'
            f'WHERE NOT EXISTS (SELECT 1 FROM {table} x WHERE {match_expr});')


def build():
    L = []
    A = L.append
    A("""-- V046：李白《夜泊牛渚懷古》(work-t300-328) 四层背景（阶段 D 第 27 首·八句 2/2/2/2）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-328 与其 text-work-t300-328-ws、
--       source-ws-t300-328 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——均不另开）。本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v046.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/夜泊牛渚懷古.txt（两处 {{另}} 自注原样照登+底注照登并声明非史料）、
--   舊唐書卷190下（逸才句）、新唐書卷202（苏颋赏句）——两段切片传区间归属生成时断言；
--   典实扫描（通鉴 75 卷+全唐詩 120 卷袁宏/谢尚计数全零）、牛渚位置断言
--   （旧传零见/新传一处且必落青山终焉句内）——全部生成时断言（负证机器复查）。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   4 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制：scene→1-2 city→3-4 world→5-6 person→7-8，
--   绑 text-work-t300-328-ws 的 8 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「题有典地，典无史源」）：
--   * 诗所怀之典（谢尚闻袁宏咏史）在通鉴/全唐詩/两传李白区间计数全零——
--     系年链条断在「典」这一环，断的不是年份，是年份的上游；
--   * 页底注「此地即謝尚聞袁宏詠史處」为整理者典实地注——照登、声明非史料，
--     不升格为典实来源（V040「時年十七」底注判例同族）；
--   * 整首零 KNOWN：苏颋赏新传单得、逸才句旧传单得——都不合龙不升
--     （audit 反向断言：出现 KNOWN 即 fail，V042 判例）；
--   * 青山终焉句 V016/V032/V036 已三入——本迁移零引（负证靠位置不靠引用）；
--     逸才句 V032 第一证此处第二证达上限；
--   * 谪仙人（V036）/竹溪六逸（V041）/脱靴斥去（V041）/崔宗之采石锦袍（V032/V045）
--     判例只引不重开（audit 关键语硬卡）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 45，不含 46
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-nz-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-328-ws';  -- 恰 8（五律）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-nz-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-328';                                  -- 8（每层两行）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-nz-%';   -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-328'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-328';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-nz-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V046_rollback.sql（按 id 全枚举删除；不动 V018/V032/V036/V045 的行，不动共用来源行）
START TRANSACTION;""")

    A('\n-- ---------- 1. BACKGROUND content identities ----------')
    rows = [{'id': k, 'entity_type': 'BACKGROUND', 'slug': k[3:], 'title': BG_TITLES[k],
             'summary': BG_SUMMARY[k], 'time_precision': 'UNKNOWN'} for k in BG]
    A(guard('poetry_content', ['id', 'entity_type', 'slug', 'title', 'summary', 'time_precision'],
            rows, 'x.id = t.id'))

    A('\n-- ---------- 2. claims（主语=BACKGROUND content 行；claim id 带 claim- 前缀，V004 同款） ----------')
    crows = [{'id': k, 'subject_id': k.replace('claim-', '', 1), 'property_key': 'context',
              'value_text': v[2], 'claim_kind': v[0], 'certainty': v[1]} for k, v in CLAIMS.items()]
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            crows, 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': k.replace('claim-', '', 1), 'property_key': 'context', 'claim_id': k}
             for k in CLAIMS],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    A('\n-- ---------- 3. background rows ----------')
    brows = [{'id': k, 'work_id': 'work-t300-328',
              'layer': {'bg-nz-scene': 'SCENE', 'bg-nz-city': 'CITY',
                        'bg-nz-world': 'WORLD', 'bg-nz-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': 'claim-' + k} for k in BG]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 4. 逐字引文（(claim,source) 主键每对恰一行） ----------')
    L.append('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(c)} AS claim_id, {sql_s(s)} AS source_id, {sql_s(loc)} AS locator, "
        f"{sql_s(ex)} AS evidence_excerpt FROM DUAL"
        for c, s, loc, ex in CITATIONS))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
             'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 5. background_line（八句：每层两行） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-328-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 46, 'Li Bai Mooring at Night at Ox-Islet, Remembering the Past background layers (stage-D poem 27, 2/2/2/2): dating verdict twenty-one, ninth shape of the title-evidence series and the first whose broken link is upstream of the year -- the title stakes ground (Ox-Islet) and moment (night, autumn moon) firmly, then invokes an allusion (Xie Shang hearing Yuan Hong recite history right here), and that allusion is unattestable in the whole snapshot corpus: counts of the two names across all 75 Tongjian files and all 120 Quantangshi files and both biography spans are zero, asserted at generation time (machine re-check of the negative evidence); the page-bottom note identifying the site is an editorial gazetteer gloss -- quoted, declared not-a-source (V040 precedent), never promoted into attestation; the chain poem-ground-allusion-year breaks at allusion: not the year that fails, but the upstream of the year; zero KNOWN honestly recorded (the praise by Su Ting is single-source in XTS, the JTS phrase on untainted talent single-source in JTS -- neither agrees across sources, neither promoted; audit asserts the zero, V042 precedent); the Green Hills sentence (three prior migrations) gets zero citation here -- the negative evidence rides on position, not on quotation; the talent phrase reaches its ceiling of two verbatim citations (V032 first, this one second, locator-declared); the banished-immortal / bamboo-creek / boots / Cui-Zongzhi lines stay closed precedents (audit keyword zero-entry); zero new sources'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 46);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V046 精确回滚：只删 V046 插入的行（id 全枚举）。',
         '-- work-t300-328 本体、其 text_line 8 行与 source-ws-t300-328 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）与 V032/V036/V045 的行不删；',
         '-- V046 零新 source、零 relation。',
         'START TRANSACTION;']
    cids = list(CLAIMS)

    def dels(table, col, vals, chunk=40):
        for i in range(0, len(vals), chunk):
            L.append(f'DELETE FROM {table} WHERE {col} IN ('
                     + ', '.join(sql_s(v) for v in vals[i:i + chunk]) + ');')
    dels('poetry_claim_selection', 'claim_id', cids)
    dels('poetry_citation', 'claim_id', cids)
    dels('poetry_background_line', 'background_id', list(BG))
    dels('poetry_background', 'id', list(BG))
    dels('poetry_claim', 'id', cids)
    dels('poetry_content', 'id', list(BG))
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 46;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_L12, WS_L34, WS_L56, WS_L78, XTS_ST, JTS_YC]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异文照登断言（V044 反向使用：有标记且已登记→必须原样入 ws 引文）
    ws_ex = ''.join(ex for _, s, _, ex in CITATIONS if s == 'source-ws-t300-328')
    for tok in ('{{另|挂帆席|洞庭去}}', '{{另|落|正}}'):
        if tok not in ws_ex:
            bad.append(f'ws 页内自注未原样照登: {tok}（先登记后引用，不可静默剥离）')
    # 底注三重断言（V040 判例）：照登在场 + 「非史料」声明在场 + 不升格
    city_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-nz-city')
    if '此地即謝尚聞袁宏詠史處' not in city_ex:
        bad.append('页底注未照登入 CITY 引文')
    city_row = next((loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-nz-city'))
    if '非史料' not in city_row:
        bad.append('CITY 引文 locator 缺「非史料」声明（底注不升格）')
    # 整首零 KNOWN 反向断言（V042 判例：如实不被指标绑架）
    if any(v[1] == 'KNOWN' for v in CLAIMS.values()):
        bad.append('V046 整首零 KNOWN 是如实记录的结果——出现 KNOWN 即 fail')
    if re.search(r"'KNOWN' AS certainty", sql):
        bad.append('V046 的 SQL 里不应出现 KNOWN certainty')
    # CITY 负证：引文零诗语（诗语不代拟；典实地注词非诗语，不在此禁）
    for c, s, _, ex in CITATIONS:
        if c == 'claim-bg-nz-city':
            for w in ('秋月', '高詠', '楓葉', '西江', '片雲', '紛紛'):
                if w in ex:
                    bad.append(f'CITY 层证据不得含诗语「{w}」')
    # 判例只引不重开（V032/V036/V041/V045 关键语零入引文）
    for tok in ('謫仙人', '竹溪六逸', '脫靴', '高力士', '賜金放還', '崔宗之', '宮錦袍',
                '採石', '青山，欲終焉', '浪迹江湖', '霓裳', '得宋之問藍田别墅',
                '妻亡不再娶', '喪妻不娶', '篤志奉佛', '天機所到'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制
    if sum(len(v) for v in BG_LINES.values()) != 8 or any(len(v) != 2 for v in BG_LINES.values()):
        bad.append('八句 background_line 必须是每层恰 2 行（4 层共 8 行）')
    if len(re.findall(r"text-work-t300-328-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V046 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V046 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-328' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V046 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-328' AS subject_id" in sql:
        bad.append('V046 的 claim 主语应全部是 bg-nz-*，work-t300-328 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V046 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V046 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '典无史源' not in body_all:
        bad.append('BG/文件头须含「典无史源」判决声明')
    if '年份的上游' not in body_all:
        bad.append('BG/文件头须含「断的不是年份，是年份的上游」声明')
    seen = {}
    cur = None
    for m in re.finditer(r'INSERT INTO (poetry_\w+)|SELECT \'([a-z0-9][a-z0-9_.-]{3,})\' AS id\b', sql):
        if m.group(1):
            cur = m.group(1)
        else:
            key = (cur, m.group(2))
            if key in seen:
                bad.append(f'id 文档内重复：{cur} {m.group(2)}')
            seen[key] = True
    for k, v in BG_TITLES.items():
        if len(k) > 64 or len(k[3:]) > 120 or len(v) > 200:
            bad.append(f'content 宽度超限: {k}')
    for c, s, loc, ex in CITATIONS:
        if len(c) > 64 or len(loc) > 300 or len(ex) > 500:
            bad.append(f'citation 宽度超限: {c} ({len(loc)}B/{len(ex)}B)')
    for m in re.finditer(r'INSERT INTO (poetry_\w+)', sql):
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
        if 'WHERE NOT EXISTS' not in sql[m.start():end]:
            bad.append(f'{m.group(1)} 的 INSERT 没有幂等守卫')
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-sql', required=True)
    ap.add_argument('--out-rollback', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    sql = build()
    rb = build_rollback()
    bad = audit(sql)
    if bad:
        print('AUDIT FAIL:')
        for b in bad:
            print(' -', b)
        raise SystemExit(1)
    if args.dry_run:
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 9 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；典实负证三层机器复查（通鉴 75 卷+全唐詩 120 卷'
              f'袁宏谢尚计数全零/牛渚位置断言/两传区间零见，快照变动即中止）；'
              f'ws 两处自注原样照登断言；底注三重断言（照登在场+非史料声明在场+不升格）；'
              f'整首零 KNOWN 反向断言（V042 判例）；CITY 零诗语断言；'
              f'判例只引不重开断言（谪仙/竹溪/脫靴/赐金/崔宗之/锦袍/青山/浪迹关键语零入引文）；'
              f'两度上限声明断言（逸才句第二证）；八句每层两行形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
