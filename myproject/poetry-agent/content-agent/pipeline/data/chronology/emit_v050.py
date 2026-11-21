#!/usr/bin/env python3
"""阶段 D 第 31 首：生成 V050——孟浩然《與諸子登峴山》(work-t300-117, V018 已立) 四层背景。

「为什么写」走到一座史部里不存在的山：
**山（峴山）在通鉴零见、在孟浩然自己的集子里出现八次；碑（羊公碑）的典故
（羊祜/墮淚）在通鉴零见——通鉴唯一一次「杜預」是打仗的杜預，不是堕泪碑的杜預**——

系年第二十五次判决（题证系列第十三状·断链在典的加重版·地名只活在诗世界）：
「題有山有碑，山無史山、碑無史碑」——
V046 典无史源（牛渚：典实在快照全库零命中）、V047 人无传名（斛斯）——
这首把两者并到一个题上，还多出一层**地名反证**：峴山通鉴 75 卷计数全零，
全唐詩 120 卷共 21 处、其中卷160 恰 16 处——**全部是孟浩然集自己的篇题**
（8 枚锚点×2：篇题行+转引桩，机器精确断言）：
九日登峴山/峴山餞房琯崔宗之/傷峴山雲表觀主/與諸子登峴山/峴山送蕭員外之荆州/
峴山送張去非遊巴東/盧明府九日峴山宴…/登峴山亭寄晉陵張少府——
**峴山在史部没有档案，在孟浩然的诗世界里是一个去了八次的地方**。
零铸造零 relation。

典无史源·加重版（V046 同族）：「羊祜」「墮淚」「峴山」通鉴计数全零；
通鉴全库「杜預」恰一处（tj-208 景龍元年盧輔上疏「杜預射不穿禮，建平吳之勳」，
年标题位置断言——七零七年这个年份里的杜預是**军功样本**不是碑主）——
堕泪碑的整个故事在快照史部里没有一行。

读碑者亦有碑（PERSON 层，同句第二引·上限至此用满）：
XTS 孟段「澤乃更爲刻碑鳳林山南，封寵其墓。」——V048 已全段一引，
本迁移引其后半子段并 locator 明文声明第二引、此句对后来迁移关闭；
「碑」字在两传孟区间恰一处且必在此句内（位置断言）。
读羊公碑而泪沾襟的人，身后由节度使刻碑凤林山南——并置为读法声明非史实。

KNOWN 零（如实记录第六例，audit 反向断言 SQL 无 KNOWN 字面量）：
杜預句通鉴单得、刻碑句新传单得（旧传孟段无身后事）——claim 四行全 LIKELY。

负证机器复查三层（生成时断言，快照变动即中止）：
① 通鉴：羊祜/墮淚/峴山 计数全零；杜預恰一处且落景龍元年标题窗口
   （注意：七零七年用「零」字——年则字符类已扩 [〇零…]）；
② 全唐詩：峴山恰 21 处、卷160 恰 16 处、8 枚锚点各恰 1 次（×2 结构断言）；
   「碑」在两传孟区间恰一处且必落刻碑句内（XTS 侧）；
③ ws：{{另}} 恰一处且必在羊公碑行；{{别}}/{{*}} 零。

判例零重开（audit 关键语硬卡）：不才/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/
年四十/應進士不第/署為從事/不逹而卒/以詩自適/病疽背卒/開元、天寶。

八句律詩 2/2/2/2 形制；零新 source
（ws-117/xts/quantangshi-160/zizhi-tongjian-events 四源行均已立）。

用法: python3 -I emit_v050.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/與諸子登峴山.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')
V160 = pathlib.Path('/tmp/src-dl/quantangshi/vol160.txt').read_text(encoding='utf-8')
TJ208 = pathlib.Path('/tmp/src-dl/tongjian/tj-208.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 與諸子登峴山', '| title    = 與諸子登峴山', 'ws header title(题目直证)')
WS_AUTHOR = slice_between(WS, '| author   = 孟浩然', '| author   = 孟浩然', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '↑ [[全唐詩/卷160#與諸子登峴山|全唐詩·卷160]]', '全唐詩·卷160]]',
                        'ws 页底注(底本指向——整理者动作,非史料)')
WS_L12 = slice_between(WS, '人事有代謝，往來成古今。', '往來成古今。', 'ws第1联(人事代谢/往来古今——登临者的历史感)')
WS_L34 = slice_between(WS, '江山留勝跡，我輩復登臨。', '我輩復登臨。', 'ws第2联(江山胜迹/我辈复登——诸子与我)')
WS_L56 = slice_between(WS, '水落魚梁淺，天寒夢澤深。', '天寒夢澤深。', 'ws第3联(鱼梁浅/梦泽深——冬日岘山的实景)')
WS_L78 = slice_between(WS, '羊公碑{{另|尚|字}}在，讀罷淚沾襟。', '讀罷淚沾襟。', 'ws第4联(羊公碑在/读罢泪襟——含{{另|尚|字}}异文,照登不裁决)')
TJ_DY = slice_between(TJ208, '杜預射不穿禮，建平吳之勳。', '建平吳之勳。',
                      '通鉴707卢辅疏摘句(郤谷敦诗书为元帅/杜预射不穿礼建平吴之勋——通鉴全库唯一杜预,军功样本非碑主)')
XTS_BEI = slice_between(XTS, '澤乃更爲刻碑鳳林山南，封寵其墓。', '封寵其墓。',
                        '新传刻碑凤林山南子段(读碑者身后亦有碑——V048 全段已一引,此处第二引上限至此用满,locator 声明)')
# 卷160 岘山八锚点（各恰 1 次；峴山全卷 16 处 = 8 锚点 ×(篇题行+转引桩)）
_ANCH_TITLES = ('和賈主簿弁九日登峴山', '峴山餞房琯崔宗之', '傷峴山雲表觀主', '與諸子登峴山',
                '峴山送蕭員外之荆州', '峴山送張去非遊巴東', '盧明府九日峴山宴袁使君張郎中崔員外',
                '登峴山亭寄晉陵張少府')
_QS_ANCHORS = tuple(
    slice_between(V160, f'==[[{t}]]==', f'==[[{t}]]==', f'卷160 岘山篇题锚点({t})')
    for t in _ANCH_TITLES)

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=孟浩然='), JTS.find('=元德秀=')
_xa, _xb = XTS.find('==孟浩然=='), XTS.find('===附 王昌齡===')
if not (0 <= _ja < _jb and 0 <= _xa <= XTS.find(XTS_BEI) <= _xb):
    raise SystemExit('切片越出孟浩然传区块——修订后重生成')

# ---------- 通鉴年标题位置断言（V034 立规；注意七零七年用「零」字） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')
_heads = [m.start() for m in _HEAD.finditer(TJ208)]
_i = TJ208.find(TJ_DY)
_prev = [h for h in _heads if h < _i]
_next = [h for h in _heads if h > _i]
if not _prev or '景龍元年' not in TJ208[_prev[-1]:_prev[-1] + 60]:
    raise SystemExit('杜預句前的年标题不是景龍元年（707）——位置断言失效，判决须重估')
if _next and _next[0] <= _i:
    raise SystemExit('杜預句位置异常——重读快照')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
def _cnt(w, files):
    return sum(len(re.findall(re.escape(w), f.read_text(encoding='utf-8'))) for f in sorted(files))
# ① 通鉴：典实与山名计数全零；杜預恰一处（文件唯一性+位置已在上方断言）
for _w in ('羊祜', '墮淚', '峴山'):
    if _cnt(_w, _tj.glob('tj-*.txt')):
        raise SystemExit(f'「{_w}」在通鉴有命中——山无史山/碑无史碑论断须重估')
_dy = [f.name for f in sorted(_tj.glob('tj-*.txt')) if '杜預' in f.read_text(encoding='utf-8')]
if _dy != ['tj-208.txt']:
    raise SystemExit(f'通鉴「杜預」不是恰一处且非 tj-208（实 {_dy}）——唯一杜預论断须重估')
# ② 全唐詩：峴山 21/16 结构 + 8 锚点各恰 1 次；碑字在两传孟区间恰一处且必落刻碑句
if _cnt('峴山', _qts.glob('vol*.txt')) != 21 or V160.count('峴山') != 16:
    raise SystemExit('全唐詩「峴山」计数不是 21/卷160 恰 16——地名诗世界论断须重估')
for _t in _ANCH_TITLES:
    if V160.count(f'==[[{_t}]]==') != 1 or V160.count(f'{{:{_t}}}') != 1:
        raise SystemExit(f'卷160 锚点结构破坏：{_t}——8×2 结构断言失效')
if '峴' in _seg_j or '羊' in _seg_j or '峴' in _seg_x or '羊' in _seg_x:
    raise SystemExit('山名/碑主落在两传孟区间——负证失效，须重读原文')
if _seg_x.count('碑') != 1 or '刻碑鳳林山南' not in _seg_x or _seg_j.count('碑'):
    raise SystemExit('「碑」在两传孟区间不是恰一处（刻碑凤林山南）——读碑者亦有碑论断须重估')
# ③ ws：{{另}} 恰一处且必在羊公碑行
if WS.count('{{另') != 1 or WS.count('{{另|尚|字}}') != 1:
    raise SystemExit('ws 页 {{另}} 计数不是恰一（羊公碑行）——异文照登断言须重估')
if '{{别' in WS or '{{*' in WS:
    raise SystemExit('ws 页出现 {{别}}/{{*}}——快照已变，异文登记须重做')

BG = {
    'bg-117-scene': (
        '八句是一次冬日结伴登山的完整记录：人事自有代谢，来来往往就组成了古今'
        '（「人事有代謝，往來成古今」——登山先登山的时间深度）；'
        '江山留下了胜迹，我们这辈人又来登临'
        '（「江山留勝跡，我輩復登臨」——「我輩」就是题上的诸子）；'
        '水位落了，鱼梁洲露得浅，天冷了，梦泽显得深'
        '（「水落魚梁淺，天寒夢澤深」——一浅一深是冬日眼前的实景）；'
        '羊公碑还在，读完眼泪打湿了衣襟'
        '（「羊公碑{{另|尚|字}}在，讀罷淚沾襟」——此句页内挂 {{另}} 异文：'
        '「尚」在／一作「字」在，照登不裁决——「还在」与「字样还在」是两种读法，留给读者）。'),
    'bg-117-city': (
        '这座「城」是峴山，襄阳城南——但它在史部没有档案：'
        '通鉴 75 卷「峴山」计数全零（生成时机器断言）；'
        '全唐詩 120 卷共 21 处，其中卷160（孟浩然集）恰 16 处——'
        '全部是本集篇题：九日登峴山、峴山餞房琯崔宗之、傷峴山雲表觀主、'
        '與諸子登峴山、峴山送蕭員外之荆州、峴山送張去非遊巴東、'
        '盧明府九日峴山宴袁使君張郎中崔員外、登峴山亭寄晉陵張少府'
        '（8 枚篇题锚点×2 结构逐字入引，机器 8×2 断言）——'
        '**峴山在史部零档案，在孟浩然的诗世界里是一个去了八次的地方**。\n'
        '页底注（全唐詩·卷160 底本指向）是整理者动作：照登+非史料声明+不升格'
        '（V040/V046/V048 底注三重断言判例）。'),
    'bg-117-world': (
        '诗的收句押在整个典故上：羊公碑=羊祜，堕泪碑。但快照史部里这个故事'
        '一行都没有：「羊祜」「墮淚」「峴山」通鉴计数全零（机器断言）——'
        'V046 牛渚典无史源的加重版。全通鉴「杜預」倒是有过恰一处：'
        '707 年（景龍元年，年标题位置断言——此文件年份写「七零七年」，'
        '则字符类已含「零」）右补阙卢辅上疏，举「杜預射不穿禮，建平吳之勳」'
        '作**军功样本**——通鉴里唯一的杜预不是碑主，是打仗的杜预。\n'
        '堕泪碑的羊祜、读碑的孟浩然，都活在诗世界与选本世界里；'
        '史部的 707 年只关心突厥与平策。「人事有代謝」是诗的历史哲学，'
        '不是史料断言。本层到此为止，不给诗铸时间。'),
    'bg-117-person': (
        '传里唯一带「碑」字的一句在身后：新传记樊泽为节度使时，'
        '「澤乃更爲刻碑鳳林山南，封寵其墓」——**读碑者亦有碑**'
        '（此句 V048 已随全段一引，此处第二引、上限至此用满，'
        'locator 声明此句对后来迁移关闭；「碑」在两传孟区间恰此一处，机器位置断言）。\n'
        '读羊公碑而泪沾襟的人，身后由节度使刻碑凤林山南——'
        '羊祜的碑与孟浩然的碑之间隔着诗，**中间是同一种眼泪**——'
        '这是读法声明，不是史实；史实只有新传一句（单得，旧传孟段无身后事，'
        '不合龙不升）。判例零重开（audit 硬卡）：不才明主弃、放还、'
        '韩朝宗遑恤他、鹿门、孟亭、画浩然像、病疽背卒，本层一个不引。'),
}
CLAIMS = {
    'claim-bg-117-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页 {{另}} 恰一处且在羊公碑行——异文照登断言反向极性：'
        '页有标记且已登记则标记必逐字入引，V044 判例；Textquality 75% 如实记）；'
        '「我辈即诸子」「一浅一深」为本层读法声明，非史料断言。'),
    'claim-bg-117-city': (
        'FACT', 'LIKELY',
        '山无史山：峴山通鉴计数全零、全唐詩恰 21 处而卷160 恰 16 处'
        '（8 枚本集篇题锚点×2 结构机器断言，全部逐字入引）——'
        '地名只活在诗世界；页底注照登+非史料声明+不升格（底注三重断言判例）；'
        '题有山而山无史档→零铸造零 relation。'),
    'claim-bg-117-world': (
        'FACT', 'LIKELY',
        '碑无史碑：羊祜/墮淚通鉴计数全零（V046 典无史源加重版）；'
        '通鉴唯一杜預恰一处（tj-208，卢辅疏军功样本，年标题位置断言'
        '景龍元年七零七年——则字符类含「零」）→单得不升；'
        '「人事代謝」为诗的历史哲学非史料；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-117-person': (
        'FACT', 'LIKELY',
        '新传刻碑凤林山南子段单得（旧传孟段无身后事，合龙无望）→不升；'
        '同句 V048 全段一引+本迁移二引=两度上限用满，此句对后来迁移关闭'
        '（locator 声明）；「读碑者亦有碑」并置为读法声明；'
        '判例零重开（不才/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/'
        '病疽背卒/開元天寶——audit 关键语硬卡）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-117-scene', 'source-ws-t300-117',
     '页面 與諸子登峴山（header title+author+四联八句，六段以「……」相連——'
     '「羊公碑{{另|尚|字}}在」标记原样入引（tang300-variants.md 新行已登记，'
     '尚/字不裁决）；同一 (claim,source) 主键下一行容全文判例；'
     '正文另见 V018 claim-t300-117-text——本诗正文两度上限至此用满，后来者不得三引）',
     join(WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78)),
    ('claim-bg-117-city', 'source-quantangshi-160',
     '卷一百六十·孟浩然集峴山篇题锚点八枚（各取篇题行；本卷「峴山」恰 16 处='
     '8 枚×篇题行+转引桩——山只活在诗人自己的集子里；卷首作者注 V031 已立引，'
     '此处不重引；通鉴「峴山」计数全零为生成时机器断言，诗身不代拟进引文）',
     join(*_QS_ANCHORS)),
    ('claim-bg-117-city', 'source-ws-t300-117',
     '页面 與諸子登峴山（页底注照登——底本指向为整理者动作，'
     '非史料声明、不升格（底注三重断言判例））', WS_NOTE),
    ('claim-bg-117-world', 'source-zizhi-tongjian-events',
     '卷二百零八·景龍元年（七零七年）条内卢辅上疏摘句（通鉴全库唯一「杜預」'
     '恰此一处——军功样本非碑主；年标题位置断言生成时复查；'
     '羊祜/墮淚/峴山通鉴计数全零为机器断言；单得不升）', TJ_DY),
    ('claim-bg-117-person', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·孟浩然传刻碑凤林山南子段（读碑者身后亦有碑——'
     '新传单得不升；**同句第二引**：V048 曾随樊泽全段一引，'
     '两度上限至此用满，此句对后来迁移关闭；与羊公碑的并置是读法声明）', XTS_BEI),
]
BG_LINES = {'bg-117-scene': (1, 2), 'bg-117-city': (3, 4),
            'bg-117-world': (5, 6), 'bg-117-person': (7, 8)}
BG_AUDIENCE = {'bg-117-scene': 'PRIMARY', 'bg-117-city': 'JUNIOR',
               'bg-117-world': 'SENIOR', 'bg-117-person': 'SENIOR'}
BG_TITLES = {'bg-117-scene': '眼前：冬日结伴的一次登山',
             'bg-117-city': '这座城：去了八次的山',
             'bg-117-world': '这个天下：史部里没有的碑',
             'bg-117-person': '这个人：读碑者亦有碑'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 31 首·八句律詩 2/2/2/2）；史实句均有逐字引证；'
                 'background_line 八句形制：每层 2 行；系年第二十五次判决'
                 '「題有山有碑，山無史山、碑無史碑」（题证系列第十三状·'
                 '断链在典的加重版·地名只活在诗世界——峴山通鉴全零而孟集八见，'
                 '堕泪碑典通鉴全零而唯一杜預是军功样本）'
                 '→time.span/event.name/written_during 全缺席、零 relation；'
                 'KNOWN 零如实记录（杜預句单得、刻碑句单得——都不升）；'
                 '负证机器复查三层（通鉴羊祜/墮淚/峴山全零+杜預恰一处落景龍元年窗口/'
                 '全唐詩峴山 21+卷160 恰 16=8 锚点×2 结构+碑字两传孟区间恰一处/'
                 'ws {{另}} 恰一处必在羊公碑行）；同句第二引上限用满声明首见'
                 '（刻碑凤林山南句对后来迁移关闭）；异文照登反向极性（尚/字原样入引）；'
                 '底注三重断言照常；判例关键语零入引文。' for k in BG}


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
    A("""-- V050：孟浩然《與諸子登峴山》(work-t300-117) 四层背景（阶段 D 第 31 首·八句律詩）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V031、V048 已执行（work-t300-117 与其 text-work-t300-117-ws、
--       source-ws-t300-117 是 V018 的行；source-xintangshu-wenyi 是 V016 的行；
--       source-quantangshi-160 是 V031 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源——
--       均不另开）。本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v050.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/與諸子登峴山.txt（{{另}} 恰一处反向断言+异文照登）、
--   舊唐書卷190下 / 新唐書卷203（孟段负证+刻碑子段）、全唐詩卷160（8 枚峴山篇题锚点）、
--   通鑑卷208（杜預摘句）+ 通鑑 75 卷/全唐詩 120 卷负证计数扫描——
--   传区间归属、景龍元年标题窗口（年份用「零」字，则字符类已扩）、
--   羊祜/墮淚/峴山/杜預/碑/{{另}} 全部计数与结构生成时断言。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制 2/2/2/2，绑 text-work-t300-117-ws 的 8 行）。
--   本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有山有碑，山無史山、碑無史碑」）：
--   * 峴山：通鉴全零、全唐詩 21 处中卷160 恰 16 处（8 枚本集篇题×2，机器结构断言）——
--     地名只活在诗世界；
--   * 羊公碑典：羊祜/墮淚通鉴全零；唯一杜預=707 卢辅疏军功样本（年标题窗口断言）——
--     V046 典无史源加重版；
--   * 读碑者亦有碑：刻碑凤林山南句新传单得、V048 一引本迁移二引=上限用满关闭；
--   * KNOWN 零如实记录（audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 我辈即诸子/一浅一深/中间是同一种眼泪均为读法声明，audit 双声明在 BG 文本内；
--   * 不才/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/年四十/應進士不第/署為從事/
--     不逹而卒/以詩自適/病疽背卒 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 49，不含 50
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-117-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-117-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-117-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-117';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-117-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-117'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-117';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-117-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V050_rollback.sql（按 id 全枚举删除；不动 V014/V015/V016/V018/V031/V048 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-117',
              'layer': {'bg-117-scene': 'SCENE', 'bg-117-city': 'CITY',
                        'bg-117-world': 'WORLD', 'bg-117-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（八句：2/2/2/2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-117-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 50, 'Meng Haoran Climbing the Xian Mountain with Friends background layers (stage-D poem 31, eight-line regulated verse 2/2/2/2): dating verdict twenty-five, thirteenth shape of the title-evidence series -- the title carries a mountain and a stele and history keeps neither: Xian Mountain has zero occurrences across all seventy-five juan of the Tongjian while among the twenty-one Quantangshi hits exactly sixteen sit in juan 160 -- eight title-anchors of Meng''s own collection counted twice each by structure (title line plus transclusion stub), machine-asserted -- the mountain exists only inside the poet''s own poetry world; the weeping-stele allusion likewise has no historical line (Yang Hu and weeping-tears zero in the Tongjian; the single surviving Du Yu passage, position-locked under the Jinglong-1 year-heading whose year is spelled with the zero glyph, is Lu Fu memorializing on military merit -- a war sample, not the stealeader), a heavier cousin of the no-source allusion verdict; the man who reads the stele weeping receives a stele himself after death: the new-history sentence on cutting the stone at Fenglin belongs to the second and final verbatim use after V048 quoted it whole -- ceiling reached, the sentence closes to all future migrations, declared in the locator; the single occurrence of the stone-stele character inside the Meng spans is position-proven to be exactly that sentence; KNOWN zero honestly recorded (audit reverse-asserts); one variant marker on the page (still/letter) transcribed verbatim per the registered-before-citing rule and left unruled; the editors'' edition note declared non-source; readings of companionship and of one shared tear declared as readings; fourteen closed precedent keywords stay out of citations; zero new sources'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 50);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V050 精确回滚：只删 V050 插入的行（id 全枚举）。',
         '-- work-t300-117 本体、其 text_line 8 行与 source-ws-t300-117 都是 V018 的行，绝不删；',
         '-- 共用 source 行（xintangshu-wenyi/quantangshi-160/zizhi-tongjian-events）与既往迁移的行不删；',
         '-- V050 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 50;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_L12, WS_L34, WS_L56, WS_L78,
              TJ_DY, XTS_BEI] + list(_QS_ANCHORS)
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异文照登反向极性（V044）：页有标记且已登记 → 标记必逐字入 SCENE 引文
    scene_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-117-scene')
    if '{{另|尚|字}}' not in scene_ex:
        bad.append('异文标记 {{另|尚|字}} 未逐字入 SCENE 引文（照登断言）')
    # CITY 八锚点全在
    city_qs = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-117-city' and s == 'source-quantangshi-160')
    for t in _ANCH_TITLES:
        if f'==[[{t}]]==' not in city_qs:
            bad.append(f'峴山篇题锚点「{t}」未入 CITY 引文（8 枚须全入）')
    # 底注三重断言
    ws_note = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-117-city' and s == 'source-ws-t300-117')
    if '全唐詩·卷160' not in ws_note:
        bad.append('页底注未照登入 CITY 引文（三重断言第一项失效）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-117-city' and s == 'source-ws-t300-117'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # 通鉴摘句要素断言
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-117-world')
    if '杜預' not in w_tj or '建平吳之勳' not in w_tj:
        bad.append('杜預摘句要素不齐（杜預+建平吳之勳须在场）')
    # 史书/集部侧引文禁代拟+禁判例句
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-117':
            for w in ('不才', '放還', '韓朝宗', '遑恤他', '鹿門', '孟亭', '畫浩然像',
                      '年四十', '應進士不第', '署為從事', '不逹而卒', '以詩自適', '病疽背卒'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
            for w in ('羊祜', '墮淚', '峴山'):
                if c == 'claim-bg-117-world' and w in ex:
                    bad.append(f'通鉴侧引文出现「{w}」——碑无史碑层不得代拟')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '卒不赴',
                '隱鹿門山', '隠鹿門山', '孟亭', '畫浩然像', '太學賦詩',
                '皆位不顯', '開元、天寶間', '刻碑鳳林山南，封寵其墓。樊澤'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 同句第二引上限声明断言
    p_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-117-person')
    if '第二引' not in p_loc or '上限' not in p_loc:
        bad.append('PERSON locator 须含「第二引/上限」声明（同句第二引上限用满声明首见）')
    # 八句形制 2/2/2/2
    want = {'bg-117-scene': 2, 'bg-117-city': 2, 'bg-117-world': 2, 'bg-117-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('八句 background_line 必须 2/2/2/2')
    if len(re.findall(r"text-work-t300-117-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V050 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V050 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-117' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V050 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-117' AS subject_id" in sql:
        bad.append('V050 的 claim 主语应全部是 bg-117-*，work-t300-117 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V050 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V050 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '山無史山' not in body_all:
        bad.append('BG/文件头须含「山無史山」判决声明')
    if '只活在诗世界' not in body_all and '只活在诗人自己的集子里' not in body_all:
        bad.append('BG/CITY 须含「地名只活在诗世界」判决声明')
    if '读法声明' not in body_all:
        bad.append('BG 须含两处「读法声明」（我辈即诸子/同一种眼泪）')
    if '对后来迁移关闭' not in body_all:
        bad.append('BG/locator 须含「对后来迁移关闭」（上限用满声明）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 17 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；通鉴年标题窗口位置断言（景龍元年七零七年——则字符类含「零」）；'
              f'负证机器复查三层（通鉴羊祜/墮淚/峴山全零+杜預恰一处 tj-208/'
              f'全唐詩峴山 21+卷160 恰 16=8 锚点×2 结构+碑字两传孟区间恰一处/'
              f'ws {{另}} 恰一处必在羊公碑行，快照变动即中止）；'
              f'异文照登反向极性断言（{{{{另|尚|字}}}} 原样入 SCENE 引文）；'
              f'八锚点全入 CITY 断言；底注三重断言；通鉴侧引文禁代拟断言；'
              f'同句第二引上限声明断言（刻碑句对后来迁移关闭）；判例只引不重开断言；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
