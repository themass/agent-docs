#!/usr/bin/env python3
"""阶段 D 第 29 首：生成 V048——孟浩然《過故人莊》(work-t300-118, V018 已立) 四层背景。

「为什么写」再成立一次。这首诗全身都是时间，唯独没有年份：
**题有故人而人无名、诗有重陽而節無年**——

系年第二十三次判决（题证系列第十一状·首见周期时间不系年）：
V043 时刻反转、V044 锚不系年、V045 见必它事、V046 典无史源、V047 题拆两半——
这首的时间不在题里而在**诗身最末**：「待到重陽日，還來就菊花」——
全诗唯一的时间词是一个**周期性的约定**：它指「下一个」重阳，不指任何一年。
史源侧同查：通鉴 75 卷「重陽」全库恰两处（生成时机器断言），两支都是宫廷节令
（695 刘知几疏「重陽之節，佇降皇恩」盼赦、821 李玨疏谏重阳大宴）——
史书里的重阳是皇帝的节日，诗里的重阳是农家的约会，两支年标题位置断言各自锁年，
与诗无关。故人无名：两传孟段「故人」唯一一处是韩朝宗剧饮事（V031 **已两入，
两度上限，本迁移零引**——audit 关键语硬卡）。零铸造零 relation。

KNOWN 零（如实记录第四例，audit 反向断言 SQL 无 KNOWN 字面量）：
WORLD 两支通鉴各单得、PERSON 樊泽符载身后段新传单得（旧传孟段无身后事）——
都不合龙不升，claim 四行全 LIKELY。

三层负证机器复查（生成时断言，快照变动即中止）：
① 诗语八字（重陽/菊花/雞黍/桑麻/場圃/田家/村/郭）在两传孟区间计数全零；
② 通鉴「重陽」恰两处且位置各自锁进年标题窗口
   （tj-205 落天冊萬歲元年→萬歲通天元年之间；tj-241 落元和十四年→长庆元年之间）；
③ 新传孟段「故人」唯一一处必为韩朝宗剧饮事（位置断言：在「採訪使韓朝宗」之后）——
   诗中故人无名可考，唯一的「故人」已被两度上限锁死。

底注+分类三重断言（V040/V046 判例扩展首用至分类行）：
页底注「全唐詩·卷160」+分类「五言律詩/重陽節」是整理者动作——
照登+「非史料」声明+不升格：分类行说它是重阳节诗，**本迁移不据此给诗铸任何时间**。

Textquality|100% 与零标记互证首见：本页是阶段 D 首张 100% 页，页内 {{另}}/{{别}}/{{*}}
零标记——评级与零标记**相互一致**（audit 反向断言 ws 侧引文无标记），
并声明评级是维基文库质量工程记号、非史料声明。

判例零重开（audit 关键语硬卡）：不才/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/
太學/奈何誣我/皆位不顯/病疽背卒/開元、天寶。

八句律詩 2/2/2/2 形制；零新 source
（ws-118/jts/xts/zizhi-tongjian-events 四源行均已立）。

用法: python3 -I emit_v048.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/過故人莊.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')
TJ205 = pathlib.Path('/tmp/src-dl/tongjian/tj-205.txt').read_text(encoding='utf-8')
TJ241 = pathlib.Path('/tmp/src-dl/tongjian/tj-241.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 過故人莊', '| title    = 過故人莊', 'ws header title(题目直证)')
WS_AUTHOR = slice_between(WS, '| author   = 孟浩然', '| author   = 孟浩然', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '↑ [[全唐詩/卷160#過故人莊|全唐詩·卷160]]', '全唐詩·卷160]]',
                        'ws 页底注(底本指向——整理者动作,非史料)')
WS_CAT = slice_between(WS, '[[Category:五言律詩]]', '[[Category:重陽節]]',
                       'ws 分类行两枚(五言律詩/重陽節——整理者分类,非史料;本迁移不据此铸时间)')
WS_L12 = slice_between(WS, '故人具雞黍，邀我至田家。', '故人具雞黍，邀我至田家。', 'ws第1联(故人具鸡黍/邀至田家——题面兑现于首句)')
WS_L34 = slice_between(WS, '綠樹村邊合，青山郭外斜。', '綠樹村邊合，青山郭外斜。', 'ws第2联(绿树村合/青山郭斜——庄园的地理)')
WS_L56 = slice_between(WS, '開筵面場圃，把酒話桑麻。', '開筵面場圃，把酒話桑麻。', 'ws第3联(筵面对场圃/把酒话桑麻——农事的席面)')
WS_L78 = slice_between(WS, '待到重陽日，還來就菊花。', '待到重陽日，還來就菊花。', 'ws第4联(待到重阳/还来就菊——全诗唯一时间词,周期性约定)')
TJ_ZY695 = slice_between(TJ205, '元日之朝，指期天澤，重陽之節，佇降皇恩', '佇降皇恩',
                         '通鉴695刘知几表陈四事摘句(元日/重阳皆俟赦恩——重阳在史部的宫廷节令身份A)')
TJ_ZY821 = slice_between(TJ241, '九月，欲以重陽大宴。拾遺李玨帥其同僚上疏曰', '上不聽。',
                         '通鉴821穆宗欲重阳大宴李玨上疏段(重阳在史部的宫廷节令身份B)')
XTS_FZ = slice_between(XTS, '後}-樊澤爲節度使', '封寵其墓。',
                       '新传樊泽符载身后段(故处士孟浩然/刻碑凤林山南——身后哀荣,新传单得;PERSON 层本体)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=孟浩然='), JTS.find('=元德秀=')
_xa, _xb = XTS.find('==孟浩然=='), XTS.find('===附 王昌齡===')
if not (0 <= _ja < _jb and 0 <= _xa <= XTS.find(XTS_FZ) <= _xb):
    raise SystemExit('切片越出孟浩然传区块——修订后重生成')

# ---------- 通鉴年标题位置断言（V034 立规；重阳两支各自锁年） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇一二三四五六七八九十百千]+年）[=\n]')
def _window(txt, needle, prev_kw, next_kw):
    i = txt.find(needle)
    heads = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in heads if h < i][-1]
    nxts = [h for h in heads if h > i]
    if not nxts:
        raise SystemExit('通鉴切片后无年标题——位置断言无法闭合')
    ph, nh = txt[prev:prev + 60], txt[nxts[0]:nxts[0] + 60]
    if prev_kw not in ph or next_kw not in txt[nxts[0]:nxts[0] + 80]:
        raise SystemExit(f'通鉴切片不在 {prev_kw}→{next_kw} 年标题窗口内——快照或锚点已变，判决须重估')
_window(TJ205, TJ_ZY695, '天冊萬歲元年', '萬歲通天元年')
_window(TJ241, TJ_ZY821, '元和十四年', '長慶元年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
# ① 诗语八字两传孟区间计数全零
for _w in ('重陽', '菊花', '雞黍', '桑麻', '場圃', '田家', '村', '郭'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'诗语「{_w}」落在两传孟区间——人无诗事的负证失效，须重读原文')
# ② 通鉴重阳恰两处（位置已由 _window 各自锁年）
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_hits = [1 for f in sorted(_tj.glob('tj-*.txt')) if '重陽' in f.read_text(encoding='utf-8')]
if len(_hits) != 2:
    raise SystemExit(f'通鉴快照「重陽」命中文件数不是 2（实 {len(_hits)}）——重阳两支论断须重估')
# ③ 新传孟段「故人」唯一一处必在韩朝宗剧饮事内（位置断言）
if _seg_x.count('故人') != 1:
    raise SystemExit(f'新传孟段「故人」计数不是 1（实 {_seg_x.count("故人")}）——故人无名论断须重估')
if not (_seg_x.find('採訪使韓朝宗') < _seg_x.find('故人')):
    raise SystemExit('新传孟段唯一「故人」不在韩朝宗条内——故人无名论断须重估')

BG = {
    'bg-118-scene': (
        '八句是一次受邀农庄半日的完整记录：老朋友备好了鸡黍，邀我到他田家'
        '（「故人具雞黍，邀我至田家」——题面在首句就兑现）；'
        '村边绿树合拢，城外青山横斜（「綠樹村邊合，青山郭外斜」——'
        '庄园的地理一近一远）；席面朝着打谷场和菜园，端着酒杯聊桑和麻'
        '（「開筵面場圃，把酒話桑麻」——这是农家自己的待客规格）；'
        '等到重阳节那天，我还要来赴菊花之约（「待到重陽日，還來就菊花」——'
        '收句不是告别，是把这次访问续成下一次）。'),
    'bg-118-city': (
        '这座「城」连名字都没有：只有村、郭、场圃、桑麻——诗不给坐标，'
        '史也不给坐标。两传孟浩然区间里，诗语八字（重陽/菊花/雞黍/桑麻/'
        '場圃/田家/村/郭）计数全零（生成时断言）——**没有任何一条史料记过'
        '这次访问**。\n'
        '「故人」在新传孟段只出现一次，且必在韩朝宗剧饮条内（机器位置断言）——'
        '那是另一件事（爽约韩朝宗，V031 已两入、本迁移零引）；'
        '本页的故人无名可考。页底注（底本指向）与两枚分类行'
        '（五言律詩/重陽節）都是整理者动作——照登、声明非史料、**不升格**'
        '（V040/V046 判例扩展首用至分类行）：分类行说它属于重阳节，'
        '本迁移不据此给诗铸任何时间。'),
    'bg-118-world': (
        '史书里的重阳是皇帝的节日：通鉴 75 卷「重陽」全库恰两处（生成时机器断言），'
        '两支都锁在年标题窗口里——695 年刘知几表陈四事：'
        '「元日之朝，指期天澤，重陽之節，佇降皇恩」'
        '（小人们算准了元日重阳都会赦，落在天冊萬歲元年→萬歲通天元年之间）；'
        '821 年穆宗想办重阳大宴，拾遗李玨率同僚上疏切谏，'
        '「上不聽」（落在元和十四年→长庆元年之间——两头各单得，不合龙不升）。\n'
        '诗里的重阳是农家的约会：「待到重陽日」——**一个周期性时间，'
        '它指下一个，不指任何一年**。这是与题证系列前十状不同的新情形：'
        '时间词明明在诗身最末，但它的语法是「每到」而不是「在某年」——'
        '周期时间不系年。两种重阳的并置是本层读法声明：史实只有通鉴两段，'
        '且两段都在孟浩然 lifetime 之外的朝廷里。'),
    'bg-118-person': (
        '传里能立住的是身后：新传记樊泽做节度使时孟浩然的墓低塌了，'
        '符载写信催办——「**故處士孟浩然**，文質傑美……行路慨然」，'
        '于是「澤乃更爲刻碑鳳林山南，封寵其墓」（新传单得——旧传孟段止于'
        '「不逹而卒」，无身后事，合龙无望→LIKELY）。\n'
        '「故處士」三个字是史部给孟浩然的最终身份：一辈子没做官，'
        '身后连墓碑都要朋友的学生写信催。这与诗里的身份严丝合缝：'
        '会备鸡黍请客的、会被约菊花酒的，就是处士圈子里的人——'
        '但这句「严丝合缝」是读法声明，不是史实。判例零重开'
        '（audit 硬卡）：不才明主弃、放还、韩朝宗遑恤他、鹿门山、孟亭、'
        '画浩然像、太学赋诗、皆位不显，本层一个不引。'),
}
CLAIMS = {
    'claim-bg-118-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页页内零异文标记——另/别/自注三类皆无，audit 反向断言；'
        'Textquality 100% 与零标记互证首见，评级为维基文库质量工程记号非史料声明）；'
        '「题面首句兑现」「收句续成下一次」为本层读法声明，非史料断言。'),
    'claim-bg-118-city': (
        'FACT', 'LIKELY',
        '诗无坐标、事无记载：诗语八字两传孟区间计数全零（生成时机器复查）；'
        '新传孟段「故人」唯一一处必为韩朝宗剧饮事（位置断言；该事 V031 已两入'
        '两度上限，本迁移零引，audit 关键语硬卡）；页底注+分类行照登并声明'
        '整理者动作非史料（三重断言扩展首用至分类行），不据此铸时间；'
        '题有故人而人无名→零铸造零 relation。'),
    'claim-bg-118-world': (
        'FACT', 'LIKELY',
        '通鉴重阳恰两处（全库机器断言）：695 刘知几摘句、821 李玨谏大宴段——'
        '各单得不升；两支年标题位置断言（V034 立规）：天冊萬歲元年→萬歲通天元年、'
        '元和十四年→长庆元年两窗口内；周期时间不系年为本层读法判决，'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during '
        '零铸造零 relation。'),
    'claim-bg-118-person': (
        'FACT', 'LIKELY',
        '新传樊泽符载身后段单得（旧传孟段无身后事，合龙无望）→不升；'
        '「故處士身份与诗严丝合缝」为读法声明非史实；判例零重开'
        '（不才/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/太學/奈何誣我/'
        '皆位不顯/病疽背卒/開元天寶——audit 关键语硬卡）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-118-scene', 'source-ws-t300-118',
     '页面 過故人莊（header title+author+四联八句，六段以「……」相連——'
     '页面零异文标记（Textquality 100% 与零标记互证首见），无标记即不造标记；'
     '同一 (claim,source) 主键下一行容全文，V037/V039/V040/V041/V042/V043/'
     'V044/V045/V046/V047 判例；全文另见 V018 claim-t300-118-text 引文——'
     '本诗正文两度上限至此用满，后来者不得三引）',
     join(WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78)),
    ('claim-bg-118-city', 'source-ws-t300-118',
     '页面 過故人莊（页底注+两枚分类行并收——底本指向与五言律詩/重陽節分类'
     '均为整理者动作，非史料声明（V040/V046 底注三重断言扩展首用至分类行，'
     '不升格、不铸时间）；人无诗事的负证为两传区间八字全零+故人位置断言，'
     '生成时机器复查，诗身不代拟进引文）', join(WS_NOTE, WS_CAT)),
    ('claim-bg-118-world', 'source-zizhi-tongjian-events',
     '卷二百零五则天朝刘知几表陈四事摘句……卷二百四十一穆宗长庆朝'
     '重阳大宴李玨上疏段（通鉴重阳全库恰两处，两支年标题位置断言：'
     '天冊萬歲元年→萬歲通天元年、元和十四年→长庆元年；各单得不升）',
     join(TJ_ZY695, TJ_ZY821)),
    ('claim-bg-118-person', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·孟浩然传樊泽符载身后段（故处士孟浩然/刻碑凤林山南'
     '——新传单得，旧传孟段无身后事不合龙；与诗身份的并置是读法声明）', XTS_FZ),
]
BG_LINES = {'bg-118-scene': (1, 2), 'bg-118-city': (3, 4),
            'bg-118-world': (5, 6), 'bg-118-person': (7, 8)}
BG_AUDIENCE = {'bg-118-scene': 'PRIMARY', 'bg-118-city': 'JUNIOR',
               'bg-118-world': 'SENIOR', 'bg-118-person': 'SENIOR'}
BG_TITLES = {'bg-118-scene': '眼前：受邀农庄的半日',
             'bg-118-city': '这座城：连名字都没有',
             'bg-118-world': '这个天下：两种重阳',
             'bg-118-person': '这个人：故处士'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 29 首·八句律詩 2/2/2/2）；史实句均有逐字引证；'
                 'background_line 八句形制：每层 2 行；系年第二十三次判决'
                 '「题有故人而人无名、诗有重陽而節無年」（题证系列第十一状·'
                 '首见周期时间不系年——全诗唯一时间词是周期性约定，指不指任何一年）'
                 '→time.span/event.name/written_during 全缺席、零 relation；'
                 'KNOWN 零如实记录（通鉴重阳两支各单得、新传身后段单得——'
                 '都不合龙不升）；负证机器复查三层（诗语八字两传孟区间全零/'
                 '通鉴重阳恰两处且各锁年标题窗口/新传故人唯一一处必在韩朝宗条内）；'
                 '底注+分类行三重断言扩展首用至分类行（非史料、不升格、不铸时间）；'
                 'Textquality 100% 与零标记互证首见；韩朝宗剧饮事两度上限零重引。' for k in BG}


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
    A("""-- V048：孟浩然《過故人莊》(work-t300-118) 四层背景（阶段 D 第 29 首·八句律詩）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018 已执行（work-t300-118 与其 text-work-t300-118-ws、
--       source-ws-t300-118 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源——均不另开）。
--       本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v048.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/過故人莊.txt（Textquality 100% 与零标记互证首见；页内零标记反向断言）、
--   舊唐書卷190下 / 新唐書卷203（孟段负证+身后段）、通鑑卷205/241（重阳两支）——
--   传区间归属、通鉴年标题窗口位置、三层负证全部生成时断言。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   4 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制 2/2/2/2，绑 text-work-t300-118-ws 的 8 行）。
--   本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「题有故人而人无名、诗有重陽而節無年」）：
--   * 全诗唯一时间词「待到重陽日」是周期性约定——语法是「每到」不是「在某年」，
--     周期时间不系年（题证系列第十一状首见）；
--   * 史书重阳恰两支（695 俟赦/821 大宴）皆宫廷节令、各单得不升、各锁年标题窗口；
--   * 故人无名：新传唯一「故人」是韩朝宗剧饮事（V031 已两入，两度上限零重引）；
--   * 页底注+分类行（五言律詩/重陽節）照登+非史料声明+不升格（三重断言扩展首用至分类行）；
--   * KNOWN 零如实记录（audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 两种重阳并置、故处士身份与诗「严丝合缝」均为读法声明，audit 双声明在 BG 文本内；
--   * 不才/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/太學/奈何誣我/皆位不顯/病疽背卒
--     判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 47，不含 48
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-118-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-118-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-118-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-118';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-118-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-118'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-118';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-118-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V048_rollback.sql（按 id 全枚举删除；不动 V014/V015/V016/V018/V031 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-118',
              'layer': {'bg-118-scene': 'SCENE', 'bg-118-city': 'CITY',
                        'bg-118-world': 'WORLD', 'bg-118-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-118-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 48, 'Meng Haoran Visiting a Late Friend''s Farmstead background layers (stage-D poem 29, eight-line regulated verse 2/2/2/2): dating verdict twenty-three, eleventh shape of the title-evidence series and the first cyclical-time case -- the poem is made of time yet has no year: its title names a friend who goes unnamed in history, and its only date-word, the closing promise to return for the Double Ninth, is a recurring appointment -- its grammar is every-autumn, not in-the-year-N; the histories keep exactly two Double-Ninth passages in all seventy-five juan (machine-asserted), 695 awaiting amnesty and 821 an aborted imperial banquet, each single-source and each locked between year-headings -- court festivals, unrelated; the single occurrence of old-friend inside the new-history span is proven to be the Han Chaozong drinking affair (already cited twice in V031, two-use ceiling, zero re-quote here); the page note and the two category lines are transcribed as editors'' acts with a non-source declaration and no promotion -- the first extension of the three-fold bottom-note assertion to category lines; a first mutual witness: the Textquality 100% rating agrees with the page''s zero variant markers (the rating itself is a wikisource engineering badge, not a source); KNOWN zero honestly recorded (audit reverse-asserts the literal is absent); the two Double Ninths juxtaposed and the retired-recluse identity said to fit the poem are declared readings, not facts; twelve closed precedent keywords stay out of citations; zero new sources'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 48);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V048 精确回滚：只删 V048 插入的行（id 全枚举）。',
         '-- work-t300-118 本体、其 text_line 8 行与 source-ws-t300-118 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi/zizhi-tongjian-events）与既往迁移的行不删；',
         '-- V048 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 48;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L12, WS_L34, WS_L56, WS_L78,
              TJ_ZY695, TJ_ZY821, XTS_FZ]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # ws 零标记反向断言（V041 立规，范围=ws 侧引文）
    ws_ex = ''.join(ex for _, s, _, ex in CITATIONS if s == 'source-ws-t300-118')
    for tok in ('{{另', '{{别|', '{{*|'):
        if tok in ws_ex:
            bad.append(f'ws 零标记迁移的 ws 引文不得含 {tok}')
    # 底注+分类三重断言：照登在场 + 非史料声明在场 + 不升格（无时间铸造）
    city_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-118-city')
    if '全唐詩·卷160' not in city_ex or 'Category:重陽節' not in city_ex:
        bad.append('底注/分类行未照登入 CITY 引文（三重断言第一项失效）')
    city_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-118-city')
    if '非史料' not in city_loc:
        bad.append('CITY locator 须含「非史料」声明（三重断言第二项失效）')
    # 重阳两支要素断言
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-118-world')
    if '重陽之節' not in w_tj or '重陽大宴' not in w_tj:
        bad.append('重阳两支要素不齐（重陽之節+重陽大宴须在场）')
    # 引文侧禁代拟：史书侧引文不得出现无名故人考、不得含韩朝宗判例句
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-118':
            for w in ('遑恤他', '韓朝宗', '鹿門', '孟亭', '不才'):
                if w in ex:
                    bad.append(f'史书侧引文不得含判例/已两入语「{w}」')
    # 判例只引不重开（V031/V038 关键语零入引文）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '韓朝宗', '遑恤他', '卒不赴',
                '隱鹿門山', '隠鹿門山', '孟亭', '畫浩然像', '太學賦詩', '一座嗟伏',
                '皆位不顯', '病疽背卒', '開元、天寶間', '以詩自適', '年四十'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制 2/2/2/2
    want = {'bg-118-scene': 2, 'bg-118-city': 2, 'bg-118-world': 2, 'bg-118-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('八句 background_line 必须 2/2/2/2')
    if len(re.findall(r"text-work-t300-118-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # KNOWN 零如实记录（V042/V046 判例：audit 反向断言）
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V048 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V048 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-118' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V048 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-118' AS subject_id" in sql:
        bad.append('V048 的 claim 主语应全部是 bg-118-*，work-t300-118 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V048 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V048 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '節無年' not in body_all:
        bad.append('BG/文件头须含「節無年」判决声明')
    if '周期时间不系年' not in body_all:
        bad.append('BG/文件头须含「周期时间不系年」判决声明')
    if '非史料' not in ''.join(BG.values()):
        bad.append('BG 须含「非史料」声明（底注+分类行三重断言）')
    if '读法声明' not in body_all:
        bad.append('BG 须含两处「读法声明」（两种重阳/故处士身份）')
    if '互证' not in body_all:
        bad.append('BG/claim 须含「互证」（Textquality 100% 与零标记首见）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 11 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；通鉴年标题窗口位置断言（695/821 两支各自锁年）；'
              f'负证机器复查三层（诗语八字两传孟区间全零/通鉴重阳恰两处/'
              f'新传故人唯一一处必在韩朝宗条内，快照变动即中止）；'
              f'ws 零标记反向断言；底注+分类三重断言（照登+非史料+不升格）；'
              f'重阳两支要素断言；史书侧引文禁判例句断言；'
              f'判例只引不重开断言（不才/放還/韓朝宗/遑恤他/鹿門/孟亭/画象/太学/'
              f'位不显/病卒/开元天宝/以诗自适/年四十关键语零入引文）；'
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
