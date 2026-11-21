#!/usr/bin/env python3
"""阶段 D 第 28 首：生成 V047——李白《下終南山過斛斯山人宿置酒》(work-t300-325, V018 已立) 四层背景。

「为什么写」再成立一次。这首诗的题是一半进档案、一半不进：
**山（終南山）在史里有名，人（斛斯山人）在两传里零见**——

系年第二十二次判决（题证系列第十状）：**「题有山有人，山有传径而人无传名」**——
V044 地有传锚而锚不系年、V045 地有传见而见必它事、V046 题有典地而典无史源——
这首把题拆成山与人两半：山有传径（通鉴 711 卢藏用指终南「此仕宦之疾径」——
终南山在史部的档案是一块仕进招牌），人有诗名无传名（斛斯山人两传李白区间
零见、通鉴唯一「斛斯」是 tj-194 的乐工斛斯正——机器断言排除同姓牵合）。
山归山、人归人，年份照旧无。零铸造零 relation。

KNOWN 零（如实记录，不立反向断言 quota——升与否只看证据）：
WORLD 通鉴疾径段单得（两唐书无此轶，通鉴侧无对翻）→LIKELY；
PERSON 新传「喜縱橫術，擊劍，為任俠，輕財重施」单得（旧传侧是另一笔
「父爲任城尉」家世，两传此段不合龙）→LIKELY。

三层负证机器复查（生成时断言，快照变动即中止）：
① 「斛斯」在两传李白区间计数全零；② 通鉴 75 卷「斛斯」唯一一处、
   且必为「斛斯正」（tj-194 乐工——同姓不同人，位置+字样双断言）；
③ 通鉴年标题位置断言（V034 立规）：疾径段必须落在
   景雲二年（辛亥，公元七一一年）与先天元年（壬子，公元七一二年）两标题之间。

题目跨源异文首见登记（tang300-variants.md 新行已入）：ws 页题「下終南山**遇**
斛斯山人宿置酒」，页底注与全唐詩·卷179 标题作「**過**」——异文在跨源题目层、
页内零标记（V041/V043 的 ws 零标记反向断言照常生效）；CITY 引文把
「遇」题与「過」底注锚点并收——**异文的两支在同一页上各自在场**，登记不裁决。

判例零重开（audit 关键语硬卡）：酒八仙人/竹溪六逸/崔宗之锦袍（V032/V045）/
浪迹江湖/天机画评（V043）/辋川段/鳏居/奉佛。

十四句五古 4/4/3/3 形制（scene 4 行/city 4 行/world 3 行/person 3 行）；
零新 source（ws-325/jts/xts/zizhi-tongjian-events 四源行均已立）。

用法: python3 -I emit_v047.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/下終南山過斛斯山人宿置酒.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
TJ210 = pathlib.Path('/tmp/src-dl/tongjian/tj-210.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 下終南山遇斛斯山人宿置酒', '| title    = 下終南山遇斛斯山人宿置酒',
                         'ws header title(ws 侧作「遇」——跨源题目异文 A 面)')
WS_AUTHOR = slice_between(WS, '| author   = 李白', '| author   = 李白', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '↑ [[全唐詩/卷179#下終南山過斛斯山人宿置酒|全唐詩·卷179]]',
                        '[[全唐詩/卷179#下終南山過斛斯山人宿置酒|全唐詩·卷179]]',
                        'ws 页底注(底本指向锚点作「過」——跨源题目异文 B 面,同页并收)')
WS_L12 = slice_between(WS, '暮從碧山下，山月隨人歸。', '暮從碧山下，山月隨人歸。', 'ws第1联(下山/月随人——归的方向)')
WS_L34 = slice_between(WS, '卻顧所來徑，蒼蒼橫翠微。', '卻顧所來徑，蒼蒼橫翠微。', 'ws第2联(回顾来径/苍翠横亘——山在身后合拢)')
WS_L56 = slice_between(WS, '相攜及田家，童稚開荊扉。', '相攜及田家，童稚開荊扉。', 'ws第3联(携入田家/童开柴门——主人出场法)')
WS_L78 = slice_between(WS, '綠竹入幽徑，青蘿拂行衣。', '綠竹入幽徑，青蘿拂行衣。', 'ws第4联(绿竹幽径/青萝拂衣——庄园的迎接)')
WS_L910 = slice_between(WS, '歡言得所憩，美酒聊共揮。', '歡言得所憩，美酒聊共揮。', 'ws第5联(欢言得憩/美酒共挥——宿与置酒题面兑现)')
WS_L1112 = slice_between(WS, '長歌吟松風，曲盡河星稀。', '長歌吟松風，曲盡河星稀。', 'ws第6联(长歌松风/河星渐稀——夜向深处)')
WS_L1314 = slice_between(WS, '我醉君復樂，陶然共忘機。', '我醉君復樂，陶然共忘機。', 'ws第7联(我醉君乐/陶然忘机——主人身份的诗内定义)')
TJ_JY = slice_between(TJ210, '尚書左丞盧藏用指終南山謂承禎曰：「此中大有佳處，何必天台！」承禎曰：「以愚觀之，此乃仕宦之疾徑耳！」藏用嘗隱終南，則天時征為左拾遺，故承禎言之。',
                      '故承禎言之。', '通鉴711疾径段(卢藏用指终南/司马承祯仕宦疾径/藏用尝隐终南——终南山在史部的仕进档案,WORLD 层本体;单得)')
XTS_RX = slice_between(XTS, '喜縱橫術，擊劍，為任俠，輕財重施。', '輕財重施。',
                       '新传任侠短语(喜纵横术/击剑任侠/轻财重施——游侠底色,与忘机并置的张力素材;PERSON 层本体;单得)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=李白='), JTS.find('=杜甫=')
_xa, _xb = XTS.find('==李白=='), XTS.find('===附 張旭===')
if not (0 <= _xa <= XTS.find(XTS_RX) <= _xb):
    raise SystemExit('切片越出李白传区块：XTS_RX——修订后重生成')

# ---------- 通鉴年标题位置断言（V034 立规） ----------
_H_JY2 = '睿宗玄真大聖大興孝皇帝下景雲二年（辛亥，公元七一一年）'
_H_XT1 = '睿宗玄真大聖大興孝皇帝下先天元年（壬子，公元七一二年）'
for _h in (_H_JY2, _H_XT1):
    if TJ210.count(_h) != 1:
        raise SystemExit(f'通鉴年标题不唯一（{TJ210.count(_h)} 次）：{_h[:20]}——重读快照')
_a, _i, _b = TJ210.find(_H_JY2), TJ210.find(TJ_JY), TJ210.find(_H_XT1)
if not (0 <= _a < _i < _b):
    raise SystemExit('疾径段不在景雲二年→先天元年两标题之间——位置断言失效，判决须重估')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
# ① 斛斯山人无传名：两传李白区间计数全零
if '斛斯' in _seg_j or '斛斯' in _seg_x:
    raise SystemExit('两传李白区间出现「斛斯」——人无传名负证失效，须重读原文再设计')
# ② 通鉴唯一斛斯必为乐工斛斯正（tj-194）——同姓不同人，位置+字样双断言
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_hits = [(f.name, m.start()) for f in sorted(_tj.glob('tj-*.txt'))
         for m in re.finditer('斛斯', f.read_text(encoding='utf-8'))]
if len(_hits) != 1:
    raise SystemExit(f'通鉴快照「斛斯」计数不是 1（实 {len(_hits)}）——同姓牵合防线须重估')
_fn, _fp = _hits[0]
_ft = _tj.joinpath(_fn).read_text(encoding='utf-8')
if _fn != 'tj-194.txt' or _ft[_fp:_fp + 3] != '斛斯正':
    raise SystemExit('通鉴唯一「斛斯」不是 tj-194 的乐工斛斯正——同姓不同人断言失效')

BG = {
    'bg-325-scene': (
        '十四句是一场从山里往下走的完整录像：黄昏从碧山下来，月亮跟着人走'
        '（「暮從碧山下，山月隨人歸」——归途上月光认人）；回头看走过的路，'
        '苍青色已横在山腰（「卻顧所來徑，蒼蒼橫翠微」——山在身后合拢）；'
        '牵着手的引到了田家，孩子来开柴门（「相攜及田家，童稚開荊扉」——'
        '主人没露脸，先出来的是孩子和门）；绿竹引着幽径，藤萝拂着行人的衣裳'
        '（「綠竹入幽徑，青蘿拂行衣」——庄园用植物来迎接）；'
        '欢言间找到了歇处，美酒一杯杯地挥（「歡言得所憩，美酒聊共揮」——'
        '题面的「宿」与「置酒」在此兑现）；长歌合着松风，唱到河上星稀'
        '（「長歌吟松風，曲盡河星稀」——夜向深处）；'
        '我醉了你也高兴，陶然里一起忘了机心（「我醉君復樂，陶然共忘機」——'
        '「忘機」两个字就是这个人的全部档案）。'),
    'bg-325-city': (
        '这座「城」是终南山里一座无名田庄。题一半进档案、一半不进：'
        '山有传径（通鉴 711 年司马承祯语——终南乃「仕宦之疾徑」，'
        '入史部的身份是**仕进招牌**，WORLD 层逐字立证）；'
        '人无传名——「斛斯」在两传李白区间计数全零（生成时断言），'
        '通鉴 75 卷唯一一处「斛斯」是卷 194 的乐工斛斯正（机器断言：'
        '唯一命中必为「斛斯正」——同姓不同人，不许牵合）；'
        '全唐詩里斛斯姓存数人（斛斯融等，衔称俱不合）——谁也认领不了这位山人。\n'
        '题目自身还有一层跨源异文：ws 页题「下終南山**遇**」，'
        '页底注与全唐詩·卷179 标题作「**過**」——两支在同一页上各自在场，'
        '本迁移引文并收，登记不裁决。「遇」是途遇的偶然，「過」是访友的常礼——'
        '读感之差留给读者，史料不代答。'),
    'bg-325-world': (
        '同一座终南山，711 年的史部档案是功名场：通鉴记尚書左丞卢藏用'
        '指着终南山对司马承祯说「此中大有佳處，何必天台」，承祯回了一句'
        '千古的坏话——「**此乃仕宦之疾徑耳**！」通鉴紧跟着补刀：'
        '「藏用嘗隱終南，則天時征為左拾遺，故承禎言之」'
        '（年标题位置断言：此事落在景雲二年与先天元年之间）。'
        '终南山在史部的形状是一块**终南捷径**的招牌。\n'
        '而这首诗是同一个山的另一种形状：黄昏下山、柴门、美酒、忘机——'
        '一个不走捷径的人，去拜访一个不做官的人。**两种形状的并置是'
        '本层的读法声明**：史实只有通鉴一段，它单得（两唐书无此轶）→不升，LIKELY。'
        '盛唐的终南山同时装着这两种人——这条上下文到此为止，'
        '**不给诗系年**：李白下的是哪一年的终南，两传一鉴都不能给。'),
    'bg-325-person': (
        '新传给这个人的底色是刀：「喜縱橫術，擊劍，為任俠，輕財重施」'
        '（单得——旧传李白传此段是另一笔「父爲任城尉，因家焉」的家世，'
        '两传此处不合龙，不升）。\n'
        '把这两句和诗的收句并排放：传里说他轻财好施、任侠尚气，'
        '诗末他说陶然忘机——**游侠的手与忘机的脸**，同一个人两副档案。'
        '这是读法并置，不是史实；史实只有新传一句。斛斯山人不在这句里，'
        '也不在任何传里：诗把主人写成「君」，史把主人留成零——'
        '判例零重开（audit 硬卡）：酒八仙人、竹溪六逸、崔宗之锦袍、'
        '浪迹江湖、天机画评、辋川、鳏居、奉佛，本层一个不引。'),
}
CLAIMS = {
    'claim-bg-325-scene': (
        'FACT', 'LIKELY',
        '十四句全诗本文（ws 页页内零异文标记——另/别/自注三类皆无，audit 反向断言；'
        'Textquality 75% 与零标记并存如实记）；归途录像/主人出场法等为本层读法声明，'
        '非史料断言；题目跨源异文遇/過见 CITY 层。'),
    'claim-bg-325-city': (
        'FACT', 'LIKELY',
        '人无传名：斛斯两传李白区间计数全零+通鉴唯一命中必为乐工斛斯正'
        '（同姓不同人位置字样双断言，生成时复查）；题有山（终南有传径，'
        'WORLD 层立证）有人（斛斯山人无传名）；题目跨源异文遇（ws 题）/過'
        '（ws 底注锚点+全唐詩标题）同页并收登记不裁决（tang300-variants.md 新行）；'
        '山有传径而人无传名→零铸造零 relation。'),
    'claim-bg-325-world': (
        'FACT', 'LIKELY',
        '通鉴 711 终南疾径段单得（两唐书无此轶，合龙无望）→不升；'
        '年标题位置断言（景雲二年→先天元年之间，V034 立规）；'
        '两种终南形状并置为读法声明非史料断言；不给诗系年；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during '
        '零铸造零 relation。'),
    'claim-bg-325-person': (
        'FACT', 'LIKELY',
        '新传任侠短语单得（旧传此段为家世句，两传不合龙）→不升；'
        '游侠手与忘机枪的并置为读法声明；酒八仙人/竹溪六逸/崔宗之锦袍/'
        '浪迹江湖/天机/辋川/鳏居/奉佛判例零重开（audit 关键语硬卡）；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-325-scene', 'source-ws-t300-325',
     '页面 下終南山遇斛斯山人宿置酒（header title+author+十四句七联，九段以「……」相連——'
     '页面零异文标记（Textquality 75% 但另/别/自注三类皆无），无标记即不造标记；'
     '同一 (claim,source) 主键下一行容全文，V037/V039/V040/V041/V042/V043/V044/V045/V046 判例；'
     '全文另见 V018 claim-t300-325-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78, WS_L910, WS_L1112, WS_L1314)),
    ('claim-bg-325-city', 'source-ws-t300-325',
     '页面 下終南山遇斛斯山人宿置酒（header title+页底注两字段并收——'
     '跨源题目异文的两支在同一页各自在场：题面「遇」、底注锚点「過」，'
     '登记不裁决（tang300-variants.md 新行）；人无传名的负证为两传区间+通鉴'
     '斛斯正双断言，生成时机器复查，诗身不代拟进引文）',
     join(WS_TITLE, WS_NOTE)),
    ('claim-bg-325-world', 'source-zizhi-tongjian-events',
     '卷二百一十·睿宗景雲二年条内（卢藏用指终南/司马承祯仕宦疾径/藏用尝隐终南'
     '——年标题位置断言：落在景雲二年（辛亥，七一一年）与先天元年（壬子，'
     '七一二年）之间；单得不升）', TJ_JY),
    ('claim-bg-325-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传任侠短语（喜纵横术/击剑任侠/轻财重施——'
     '新传单得，旧传此段为家世句不合龙；与诗收句的并置是读法声明）', XTS_RX),
]
BG_LINES = {'bg-325-scene': (1, 2, 3, 4), 'bg-325-city': (5, 6, 7, 8),
            'bg-325-world': (9, 10, 11), 'bg-325-person': (12, 13, 14)}
BG_AUDIENCE = {'bg-325-scene': 'PRIMARY', 'bg-325-city': 'JUNIOR',
               'bg-325-world': 'SENIOR', 'bg-325-person': 'SENIOR'}
BG_TITLES = {'bg-325-scene': '眼前：从山里往下走的录像',
             'bg-325-city': '这座城：题的一半进档案',
             'bg-325-world': '这个天下：同一座山的两种形状',
             'bg-325-person': '这个人：游侠的手与忘机的脸'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 28 首·十四句五古 4/4/3/3）；史实句均有逐字引证；'
                 'background_line 十四句形制：scene 4 行 city 4 行 world 3 行 person 3 行；'
                 '系年第二十二次判决「题有山有人，山有传径而人无传名」'
                 '（题证系列第十状）→time.span/event.name/written_during 全缺席、'
                 '零 relation；KNOWN 零（通鉴疾径段单得、新传任侠短语单得——'
                 '都不合龙不升，如实记录）；负证机器复查三层（斛斯两传区间全零/'
                 '通鉴唯一斛斯必为乐工斛斯正/通鉴年标题位置断言）；'
                 '题目跨源异文遇/過同页并收登记不裁决（首见跨源题异登记）。' for k in BG}


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
    A("""-- V047：李白《下終南山過斛斯山人宿置酒》(work-t300-325) 四层背景（阶段 D 第 28 首·十四句五古）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018 已执行（work-t300-325 与其 text-work-t300-325-ws、
--       source-ws-t300-325 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源——均不另开）。
--       本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v047.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/下終南山過斛斯山人宿置酒.txt（页内零标记反向断言；题「遇」/底注「過」并收）、
--   舊唐書卷190下（负证扫描）、新唐書卷202（任侠短语）、通鑑卷210（疾径段）——
--   传区间归属、通鉴年标题位置（景雲二年→先天元年）、斛斯三层负证全部生成时断言。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   4 组逐字引用（(claim,source) 主键每对恰一行）+
--   14 行 background_line（十四句形制：scene→1-4 city→5-8 world→9-11 person→12-14，
--   绑 text-work-t300-325-ws 的 14 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「题有山有人，山有传径而人无传名」）：
--   * 山（终南）在史部档案=仕宦疾径（通鉴 711 段，年标题位置断言）；
--     人（斛斯山人）两传李白区间零见、通鉴唯一斛斯=乐工斛斯正（同姓不同人双断言）、
--     全唐詩斛斯诸人衔称俱不合——谁也认领不了；
--   * 题目跨源异文：ws 题「遇」/ws 底注锚点+全唐詩标题「過」——同页并收登记不裁决；
--   * KNOWN 零：疾径段单得、任侠短语单得（旧传此段为家世句不合龙）——都不升；
--   * 两种终南形状并置、游侠手与忘机枪并置均为读法声明，audit 双声明在 BG 文本内；
--   * 酒八仙人/竹溪六逸/崔宗之锦袍/浪迹江湖/天机/辋川/鳏居/奉佛判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 46，不含 47
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-325-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-325-ws';  -- 恰 14（五古）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-325-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-325';                                  -- 14（4/4/3/3）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-325-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-325'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-325';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-325-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V047_rollback.sql（按 id 全枚举删除；不动 V014/V015/V018/V032/V045 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-325',
              'layer': {'bg-325-scene': 'SCENE', 'bg-325-city': 'CITY',
                        'bg-325-world': 'WORLD', 'bg-325-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（十四句：4/4/3/3） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-325-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 47, 'Li Bai Coming Down from the Southern Peak and Staying Overnight at a Hermit of the Husi Clan background layers (stage-D poem 28, fourteen-line five-character ancient, 4/4/3/3): dating verdict twenty-two, tenth shape of the title-evidence series -- the title splits into mountain and man, and only the mountain files papers: in the histories the Southern Peak has a reputation (Tongjian 711: Lu Cangyong points at it, Sima Chengzhen calls it the express path into office, and Tongjian brackets the entry positionally between the Jingyun-2 and Xiantian-1 year-headings), while the man has none: the surname Husi counts zero inside the Li Bai spans of both Tang histories, its single Tongjian occurrence is proven to be the groom Husi Zheng (same surname, different person -- position plus wording doubly asserted) -- zero forging, zero relation; a first-of-series cross-source title variant: the wikisource page title reads encountering while its own edition note and the Quantangshi heading read visiting -- both variants co-present on one page, quoted together, registered, never ruled; KNOWN zero honestly recorded (the express-path passage is single-source; the new-history phrase on swordplay and generosity is single-source -- the old history runs a family anecdote in that same slot, no agreement, no promotion); the two shapes of the mountain and the wuxia hands against the forgetting-worldliness face are declared as readings, not facts; the eight-drunk-immortals / bamboo-creek / Cui-Zongzhi / wandering / tian-ji / Wang-chuan / widower / piety lines stay closed precedents (audit keyword zero-entry); zero new sources'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 47);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V047 精确回滚：只删 V047 插入的行（id 全枚举）。',
         '-- work-t300-325 本体、其 text_line 14 行与 source-ws-t300-325 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi/zizhi-tongjian-events）与既往迁移的行不删；',
         '-- V047 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 47;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_L12, WS_L34, WS_L56, WS_L78,
              WS_L910, WS_L1112, WS_L1314, TJ_JY, XTS_RX]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # ws 零标记反向断言（V041 立规，范围=ws 侧引文）
    ws_ex = ''.join(ex for _, s, _, ex in CITATIONS if s == 'source-ws-t300-325')
    for tok in ('{{另', '{{别|', '{{*|'):
        if tok in ws_ex:
            bad.append(f'ws 零标记迁移的 ws 引文不得含 {tok}')
    # 跨源题异并收断言：两支各须在场
    city_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-325-city')
    if '下終南山遇' not in city_ex:
        bad.append('题面「遇」支未入 CITY 引文（跨源题异须并收）')
    if '下終南山過' not in city_ex:
        bad.append('底注「過」支未入 CITY 引文（跨源题异须并收）')
    # 疾径段在场且含判据要素
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-325-world')
    if '仕宦之疾徑' not in w_tj or '終南山' not in w_tj:
        bad.append('疾径段要素不齐（仕宦之疾徑+終南山须在场）')
    # 人无传名断言的引文侧：PERSON/CITY 不得代拟斛斯考
    p_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-325-person' and s == 'source-xintangshu-wenyi')
    if '斛斯' in p_xts or '斛斯' in w_tj:
        bad.append('史书侧引文出现「斛斯」——人无传名层不得代拟')
    # CITY 负证：引文零诗语
    for c, s, _, ex in CITATIONS:
        if c == 'claim-bg-325-city':
            for w in ('山月', '翠微', '荊扉', '綠竹', '青蘿', '美酒', '忘機'):
                if w in ex:
                    bad.append(f'CITY 层证据不得含诗语「{w}」')
    # 判例只引不重开（V032/V041/V043/V037/V039/V035 关键语零入引文）
    for tok in ('酒八仙人', '竹溪六逸', '崔宗之', '宮錦袍', '浪迹江湖', '賜金放還',
                '天機所到', '絕迹天機', '得宋之問藍田别墅', '地奇勝',
                '妻亡不再娶', '喪妻不娶', '蔬食', '篤志奉佛', '霓裳',
                '表輞川第為寺', '四百餘篇', '數十百篇'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 十四句形制 4/4/3/3
    want = {'bg-325-scene': 4, 'bg-325-city': 4, 'bg-325-world': 3, 'bg-325-person': 3}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('十四句 background_line 必须 4/4/3/3（scene4 city4 world3 person3）')
    if len(re.findall(r"text-work-t300-325-ws' AS version_id", sql)) != 14:
        bad.append('bg_line INSERT 的 version 行数应为 14')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V047 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V047 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-325' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V047 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-325' AS subject_id" in sql:
        bad.append('V047 的 claim 主语应全部是 bg-325-*，work-t300-325 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V047 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V047 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '人无传名' not in body_all:
        bad.append('BG/文件头须含「人无传名」判决声明')
    if '同姓不同人' not in body_all:
        bad.append('BG/文件头须含「同姓不同人」断言声明')
    if '读法声明' not in body_all:
        bad.append('BG 须含两处「读法声明」（两种山形/游侠手忘机枪）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 12 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；通鉴年标题位置断言（景雲二年→先天元年）；'
              f'负证机器复查三层（斛斯两传区间全零/通鉴唯一斛斯必为斛斯正/年标题位置，'
              f'快照变动即中止）；ws 零标记反向断言；跨源题异遇/過并收断言；'
              f'疾径段要素断言；史书侧引文禁「斛斯」代拟断言；CITY 零诗语断言；'
              f'判例只引不重开断言（酒八仙/竹溪/崔宗之/锦袍/浪迹/天机/辋川/鳏居/奉佛/辨乐/诏集关键语零入引文）；'
              f'十四句 4/4/3/3 形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
