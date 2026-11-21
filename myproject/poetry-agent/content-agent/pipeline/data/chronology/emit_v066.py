#!/usr/bin/env python3
"""阶段 D 第 47 首：生成 V066——李商隱《賈生》(work-t300-031, V018 已立) 四层背景。

**本迁移新建 1 个 source（source-ws-t300-031）——V058 以来连续六首零新源在此
诚实终结**：V018 当时以全唐詩卷540 卷页（source-quantangshi-540，version_code
vol-raw）立本诗正文，**ws《唐詩三百首》诗页从未建源**——卷页与诗页是两个独立
见证面（锚点归属 vs 选本转录），本迁移引诗页之署名/题面/分类/三百首标记，
非新源不能承载逐字引文（ledger 144→145，audit 断言恰一枚新源且只此一 INSERT）。

「为什么写」走到**咏史两界**（同字两界第十一形态·咏史形态首见；V056 泪/…/
V065 碧玉·狂夫·良人之后）：**「詩有賈生的場景，史部只有賈誼的话头」**——

通鉴「賈生」「宣室」「前席」「逐臣」「才調」「夜半前席」「問鬼神」全零（诗重构的
那场君臣夜谈整个不在史部）；而「**賈誼**」恰二处（闭域+双窗口，逐字入引）：
貞觀八年（甲午，六三四）魏徵对太宗「**賈誼當漢文帝時上書，云『可為痛哭者一，
可為流涕者二。』**」、元和七年（壬辰，八一二）李絳拒「天下已太平」之颂
「**漢文帝時兵木無刃，家給人足，賈誼猶以為厝火積薪之下，不可謂安**」——
**史部的贾谊是谏臣嘴里的话头（引经据证的权威），诗的贾谊是灯火底下的场景
（宣室、夜半、前席、鬼神）**：史部引用他，诗进入他的那个夜晚。
「**可憐**」恰一处（闭域+窗口入引）——會昌六年（丙寅，八四六）知贡举者语
「**可憐彼翁每歲受撻**」（老驿吏年年被鞭催试期，故李景莊不得不收）：
**史部唯一的「可怜」可怜的是科场受杖的老吏；诗「可憐夜半虛前席」可怜的
是见遇如天的天才——同一个怜字，一怜其劳力，一怜其空才**。

卷540 侧（CITY 层核心）：卷页「賈生」恰三处（机器断言闭域）=本篇篇题锚
「==賈生==」+本篇正文「賈生才調更無倫」+《安定城樓》「**賈生年少虛垂涕**」——
**同一卷里看得见李商隱把贾生又用了一次**：本篇替贾生问「虛前席」（君王白挪近
了坐席），《安定城樓》以贾生自嘲「虛垂涕」（自己的眼泪白流了）——**两个「虛」字
同诗人同卷自引首见**（安定城樓句域恰零=本迁移首引）。ws 诗页**notes 只有
{{唐詩三百首}} 而无任何 Textquality 评级——无评级页系列首见**（V055–V065
或 75% 或 100%，本篇无自评——选本标记与转录评级是两回事）；分类四行
「李商隱+唐诗+唐詩三百首|李+七言絕句」**系列最多（首录）**，且第三行简体
「唐诗」与第四行繁体「唐詩」并存同页——**同页分类简繁混排首见**（照登）。

PERSON 层：旧传李商隐段（简化字录入，V016 locator 已注）首引二句——
「**明年，令狐绹作相，商隐屡启陈情，绹不之省。**」「**名宦不进，坎壈终身。**」
（皆域恰零）：诗的贾生是**见遇而问错了方向**（宣室夜半不问苍生问鬼神），
传的李商隐是**求见而根本不被见**（屡启陈情，绹不之省）——
**同一种错位，史部记不见，诗记见而空**；旧传自断「名宦不进，坎壈终身」
系史臣语，照登（certainty LIKELY）。段内賈生/賈誼/蒼生/鬼神/宣室/前席全零
（机器断言——写尽贾生夜谈的人，传里没有一个贾生字）。

4 句七绝 shape：1/1/1/1 第三次（V056/V061 之后）。
正文第二引上限用满第十四例（V018 卷540 一引在先，双针「宣室求賢訪逐臣」
「不問蒼生問鬼神」各恰一处）——**本迁移第二引面正是 V018 未用的 ws 诗页**：
两引两面（卷页+诗页），上限恰满而不重叠。

用法: python3 -I emit_v066.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/賈生.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V540 = pathlib.Path('/tmp/src-dl/quantangshi/vol540.txt').read_text(encoding='utf-8')
TJ194 = pathlib.Path('/tmp/src-dl/tongjian/tj-194.txt').read_text(encoding='utf-8')
TJ238 = pathlib.Path('/tmp/src-dl/tongjian/tj-238.txt').read_text(encoding='utf-8')
TJ248 = pathlib.Path('/tmp/src-dl/tongjian/tj-248.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 賈生', '| title    = 賈生', 'ws header title(咏史题面)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{唐詩三百首}}', 'notes    = {{唐詩三百首}}',
                        'ws 页底注(整页 notes 只有三百首选本标记而无 Textquality 评级——无评级页首见)')
WS_CAT = slice_between(WS, '[[Category:李商隱]]', '[[Category:七言絕句]]',
                       'ws 分类四行连片(系列最多;第三行简体「唐诗」与第四行繁体「唐詩」同页混排首见)')
WS_BODY = slice_between(WS, '宣室求賢訪逐臣，賈生才調更無倫。\n可憐夜半虛前席，不問蒼生問鬼神。',
                        '不問蒼生問鬼神。', 'ws 页 poem 块四句(全句**第二引**：V018 卷540 一引在先)')
V540_ANCHOR = slice_between(V540, '==賈生==\n<poem>\n', '不問蒼生問鬼神。\n</poem>',
                            '卷540 本篇块(锚==賈生==裸名+poem四句——卷页旧式锚,无消歧器;'
                            '终锚用末句+闭tag全卷唯一,裸</poem>全卷216次不可作锚)')
V540_SELF = slice_between(V540, '賈生年少虛垂涕，王粲春來更遠遊。', '更遠遊。',
                          '卷540 安定城樓句(同卷自引贾生——虛垂涕对虛前席,双虚字同诗人同卷首见)')
TJ_ZT = slice_between(TJ194, '賈誼當漢文帝時上書，云『可為痛哭者一，可為流涕者二。』',
                      '可為流涕者二。』',
                      '通鉴贞观八年魏徵引贾谊上书段(贾谊史部一处——谏臣话头;窗口断言;'
                      '止于痛哭对未及同段狂夫之言句,零重开)')
TJ_CH = slice_between(TJ238, '漢文帝時兵木無刃，家給人足，賈誼猶以為厝火積薪之下，不可謂安。',
                      '不可謂安。',
                      '通鉴元和七年李绛拒太平颂段(贾谊史部二处——厝火积薪危言;窗口断言)')
TJ_KE = slice_between(TJ248, '可憐彼翁每歲受撻！', '受撻！',
                      '通鉴会昌六年知贡举语(可怜通鉴唯一一处——怜科场老吏;窗口断言)')
JTS_P1 = slice_between(JTS, '明年，令狐绹作相，商隐屡启陈情，绹不之省。', '绹不之省。',
                       '旧传李商隐段(绹不之省——屡启而不见;PERSON 首引)')
JTS_P2 = slice_between(JTS, '名宦不进，坎壈终身。', '坎壈终身。',
                       '旧传李商隐段自断(名宦不进坎壈终身——史臣语照登;PERSON 首引)')

# ---------- 传区间归属复验（V036 立规；段界 ==弟 羲叟==） ----------
_ja = JTS.find('=李商隱=')
_jm = re.search(r'\n==[^=\n]{1,12}==', JTS[_ja + 8:])
_seg_j = JTS[_ja:_ja + 8 + _jm.start()]
for _needle in (JTS_P1, JTS_P2):
    if _needle not in _seg_j:
        raise SystemExit('PERSON 首引句越出旧传李商隐段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；三扇窗口） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ194, TJ_ZT, '貞觀八年')
_window(TJ238, TJ_CH, '元和七年')
_window(TJ248, TJ_KE, '會昌六年')

# ---------- 负证机器复查（V042 立规） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：贾生场景词全零；贾谊恰二；可怜恰一
for _w in ('賈生', '宣室', '前席', '逐臣', '才調', '虛前席', '問鬼神'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗的场景不在史部的判决失效，须重读')
_jy = {n: t.count('賈誼') for n, t in _tjf.items() if '賈誼' in t}
if _jy != {'tj-194.txt': 1, 'tj-238.txt': 1}:
    raise SystemExit(f'通鉴「賈誼」分布变了（实 {_jy}）——贾谊只是话头判决须重估')
_kl = {n: t.count('可憐') for n, t in _tjf.items() if '可憐' in t}
if _kl != {'tj-248.txt': 1}:
    raise SystemExit(f'通鉴「可憐」不再是恰一处（实 {_kl}）——一怜劳力/一怜空才判决须重估')
# ② 全唐诗：卷540 贾生恰三（锚+正文+自引）；他卷在册
if V540.count('賈生') != 3:
    raise SystemExit(f'卷540「賈生」不再恰 3（实 {V540.count("賈生")}）——同卷自引闭域须重估')
if V540.count('賈生年少虛垂涕，王粲春來更遠遊。') != 1 or V540.count('==賈生==\n<poem>\n') != 1:
    raise SystemExit('卷540 自引句/锚块结构变了——自引与裸名锚断言失效')
_qs_x = {f.name: t.count('宣室') for f in sorted(_qts.glob('vol*.txt')) for t in [f.read_text(encoding='utf-8')] if '宣室' in t}
if sum(_qs_x.values()) != 4:
    raise SystemExit(f'全唐詩「宣室」不再恰 4（实 {sum(_qs_x.values())}）——在册闭域须重估')
if _allq.count('前席') != 2 or _allq.count('逐臣') != 3 or _allq.count('才調') != 3:
    raise SystemExit('全唐詩 前席/逐臣/才調 闭域数变了——在册零入引断言须重估')
# ③ ws：无评级 + notes 只有三百首 + 零标记 + 分类四行连片+简繁混排
if WS.count('{{Textquality') != 0:
    raise SystemExit('ws 页出现 Textquality 评级——无评级页首见断言失效')
if WS.count('| notes    = {{唐詩三百首}}') != 1 or WS.count('{{唐詩三百首}}') != 1:
    raise SystemExit('ws 页 notes 结构变了（notes 应只有三百首标记恰一）')
if WS.count('{{另') or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页出现异文/注记标记——零标记断言失效')
_cat = '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]\n[[Category:七言絕句]]'
if WS.count(_cat) != 1:
    raise SystemExit('ws 页分类四行连片结构变了（系列最多+同页简繁混排断言失效）')
if WS.count('[[Category:唐诗]]') != 1 or WS.count('唐詩三百首|李') != 1:
    raise SystemExit('ws 页分类简繁混排细节变了——简「唐诗」繁「唐詩」同页照登断言失效')
if WS.count('宣室求賢訪逐臣') != 2:
    raise SystemExit('ws 页宣室句不再恰 2（Vtext+poem 两面）——页内双转录照登失效')
# ④ 旧传李商隐段负证：诗面字全零（段级）
for _w in ('賈生', '賈誼', '蒼生', '鬼神', '宣室', '前席'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——传不载贾生夜谈负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V066')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

for _premise, _needle, _want in (
        ('本诗首句', '宣室求賢訪逐臣', ['V018']),
        ('本诗末句', '不問蒼生問鬼神', ['V018']),
        ('义山署名句', '李商隐，字义山', ['V016']),
        ('岭表随亚句', '商隐随亚在岭表累载', ['V016']),
        ('三十六体句', '与太原温庭筠、南郡段成式齐名', ['V016']),
        ('荥阳卒句', '府罷，客滎陽，卒', ['V016'])):
    _prev = _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
# 首引句必须零域；新源 id 必须全库不存在（确系 V018 未建）
for _first, _needle in (('痛哭对', '可為痛哭者一'), ('厝火语', '厝火積薪之下，不可謂安'),
                        ('受撻语', '可憐彼翁每歲受撻'), ('不之省', '绹不之省'),
                        ('坎壈断', '坎壈终身'), ('自引句', '賈生年少虛垂涕')):
    if _domain(_needle):
        raise SystemExit(f'首引前提破了：「{_needle}」（{_first}）既往有引（{_domain(_needle)}）——须重设计')
if _domain('source-ws-t300-031'):
    raise SystemExit('source-ws-t300-031 已存在于既往迁移——本迁移不再新建源，设计须改')
if not _domain('source-quantangshi-540') or _domain('source-quantangshi-540') != ['V018']:
    raise SystemExit('source-quantangshi-540 域非恰 [V018]——本迁移复用对象须重估')

BG = {
    'bg-031-scene': (
        '四句是一次没问对的夜谈：宣室求贤，访的是逐臣（「宣室求賢訪逐臣，'
        '賈生才調更無倫」）——汉文帝在宣室召见被贬的贾谊，天下第一等的才调；'
        '可怜夜半文帝不知不觉把坐席挪到贾生跟前（「可憐夜半虛前席」）——'
        '不问苍生的生计，问鬼神的所以然（「不問蒼生問鬼神」）。'
        'ws 诗页 notes **只有 {{唐詩三百首}} 选本标记而无任何 Textquality 评级**'
        '（无评级页系列首见——选本标记与转录评级是两回事）；{{另}}/{{別}}/{{*}}/<ref> '
        '全零；页内 Vtext/poem 双转录并存（「宣室求賢訪逐臣」页内恰 2，各从其录）。'
        '此诗正文系**第二引**：V018 卷540 卷页一引在先，本迁移引 ws 选本页——'
        '**两引两面（卷页+诗页），上限恰满而不重叠**；生成时全库查重双针各恰一处，'
        '两度上限至此用满，此诗正文对后来迁移关闭。'),
    'bg-031-city': (
        '卷540 侧：**「賈生」恰三处**（机器断言闭域）=本篇篇题锚「==賈生==」'
        '（卷页旧式裸名锚，无消歧器——同名则无消歧器判例延展至旧式卷页）+本篇正文'
        '「賈生才調更無倫」+**《安定城樓》「賈生年少虛垂涕」**——'
        '**同一卷里看得见李商隱把贾生又用了一次**：本篇替贾生问「虛前席」'
        '（君王白挪近了坐席），《安定城樓》以贾生自嘲「虛垂涕」（自己的眼泪白流）——'
        '**两个「虛」字，同诗人同卷自引首见**（安定城樓句全库域恰零，本迁移首引）。'
        'ws 诗页分类四行「李商隱+唐诗+唐詩三百首|李+七言絕句」——**系列最多（首录）**；'
        '第三行简体「唐诗」与第四行繁体「唐詩」同页并存——**同页分类简繁混排首见**'
        '（照登）；sortkey「|李」系编排动作。四行系整理者分类（V048 判例：'
        '非史料声明、不升格）。**本迁移新建 1 个 source（source-ws-t300-031）**：'
        'V018 以卷540 卷页立本诗（source-quantangshi-540，version_code vol-raw），'
        'ws《唐詩三百首》诗页从未建源——卷页与诗页是两个独立见证面（锚点归属 vs '
        '选本转录），非新源不能承载诗页逐字引文；audit 断言恰一枚新源 INSERT。'
        '（本层零 relation。）'),
    'bg-031-world': (
        '**詩有賈生的場景，史部只有賈誼的话头**（同字两界第十一形态·咏史形态首见）：'
        '通鉴「賈生」「宣室」「前席」「逐臣」「才調」「虛前席」「問鬼神」全零'
        '（机器断言——诗重构的那场君臣夜谈整个不在史部）；而「**賈誼**」恰二处'
        '（闭域+双窗口逐字入引）：貞觀八年（甲午，六三四）魏徵对太宗'
        '「**賈誼當漢文帝時上書，云『可為痛哭者一，可為流涕者二。』**」、'
        '元和七年（壬辰，八一二）李絳拒「天下已太平」之颂「**漢文帝時兵木無刃，'
        '家給人足，賈誼猶以為厝火積薪之下，不可謂安。**」——**史部的贾谊是谏臣'
        '嘴里的话头（引经据证的权威），诗的贾谊是灯火底下的场景（宣室、夜半、'
        '前席、鬼神）：史部引用他，诗进入他的那个夜晚**。「**可憐**」通鉴恰一处'
        '（闭域+窗口入引）——會昌六年（丙寅，八四六）知贡举者语'
        '「**可憐彼翁每歲受撻！**」：史部唯一的「可怜」可怜的是年年受杖催试期的'
        '老吏；诗「可憐夜半虛前席」可怜的是见遇如天却问错了方向的天才——'
        '**同一个怜字，一怜其劳力，一怜其空才**。全唐詩侧在册零入引（机器断言）：'
        '「宣室」恰 4 四卷、「前席」恰 2、「逐臣」恰 3、「才調」恰 3、'
        '「夜半」恰 9 八卷、「可憐」恰 39——诗眼词都有别人用，史部却不接这个场景。'
        '本层零铸造零 relation。'),
    'bg-031-person': (
        '旧传李商隐段（**简化字录入**，V016 locator 已注，本层引文照登简体原样）'
        '首引二句（皆生成时全库查重域恰零）：「**明年，令狐绹作相，'
        '商隐屡启陈情，绹不之省。**」「**名宦不进，坎壈终身。**」\n'
        '**同一种错位，两界各记一半**（读法声明，非史实）：诗的贾生是'
        '**见遇而问错了方向**（宣室夜半，虚前席，不问苍生问鬼神），'
        '传的李商隐是**求见而根本不被见**（屡启陈情，绹不之省）——'
        '贾生之怜在见而空，义山之困在不见。\n'
        '「名宦不进，坎壈终身」系**史臣自断**（照登，certainty LIKELY——'
        '史臣语非自家语）；传之脉络在册句零重开：字义山（V016）、开成二年登第'
        '（V016）、随郑亚岭表（V016）、三十六体（V016）、新传「府罷，客滎陽，卒」'
        '（V016）。**旧传李商隐段賈生/賈誼/蒼生/鬼神/宣室/前席全零**'
        '（机器断言——写尽贾生夜谈的人，传里没有一个贾生字）；'
        'certainty 不覆盖任何系年，本诗无底注无岁数注（无注可登），'
        '诗 time.span/event.name/written_during 仍零铸造（audit 硬卡）。'),
}
CLAIMS = {
    'claim-bg-031-scene': (
        'FACT', 'LIKELY',
        '四句七绝本文（ws 选本页 poem 块；页内 Vtext/poem 双转录并存恰 2，各从其录）；'
        'notes 只有 {{唐詩三百首}} 选本标记而无 Textquality 评级——无评级页系列首见；'
        '{{另}}/{{別}}/{{*}}/<ref> 全零；'
        '全句第二引：正文 V018 卷540 卷页 claim 一引在先（生成时全库查重双针'
        '「宣室求賢訪逐臣」「不問蒼生問鬼神」各恰一处），本迁移引 ws 诗页——'
        '两引两面（卷页+诗页）上限恰满不重叠；两度上限至此用满、'
        '此诗正文对后来迁移关闭（audit 硬卡）。'),
    'claim-bg-031-city': (
        'FACT', 'LIKELY',
        '卷540「賈生」恰三=锚+正文+《安定城樓》自引（机器断言闭域）——'
        '同诗人同卷自引首见（虛前席/虛垂涕双虚字；安定城樓句全库域恰零本迁移首引）；'
        '卷页旧式裸名锚「==賈生==」无消歧器（同名则无消歧器判例延展至旧式卷页，'
        'audit 照登硬卡锚字样）；ws 页分类四行系列最多首录+同页简繁混排'
        '（简体「唐诗」与繁体「唐詩三百首」并存）照登；分类行非史料声明+不升格'
        '（V048 判例）；sortkey「|李」系编排动作；**新建 source-ws-t300-031 恰一枚**'
        '（V018 以卷540 卷页立本诗、ws 诗页从未建源——卷页与诗页两个独立见证面；'
        'audit 断言恰一枚新源 INSERT 且 id 唯一）。'),
    'claim-bg-031-world': (
        'FACT', 'LIKELY',
        '通鉴「賈生/宣室/前席/逐臣/才調/虛前席/問鬼神」全零（诗的场景不在史部，'
        '机器断言）；「賈誼」恰二闭域双窗口逐字入引=貞觀八年（甲午，六三四）'
        '魏徵引「可為痛哭者一」对+元和七年（壬辰，八一二）李絳引「厝火積薪之下，'
        '不可謂安」（史部贾谊=谏臣话头，诗贾谊=灯火场景——同字两界第十一形态·'
        '咏史形态首见，audit 硬卡；痛哭对切片止于引文处，未及同段 V065 已引'
        '「狂夫之言」句——零重开）；「可憐」恰一闭域窗口入引=會昌六年（丙寅，'
        '八四六）「可憐彼翁每歲受撻」（一怜劳力/一怜空才）；全唐詩宣室恰 4/'
        '前席恰 2/逐臣恰 3/才調恰 3/夜半恰 9/可憐恰 39 在册零入引（机器断言）；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during 零铸造'
        '零 relation（audit 硬卡）。'),
    'claim-bg-031-person': (
        'FACT', 'LIKELY',
        '旧传李商隐段（简化字录入，引文照登简体原样）首引二句皆生成时全库查重'
        '域恰零=「明年，令狐绹作相，商隐屡启陈情，绹不之省。」+「名宦不进，'
        '坎壈终身。」（传区间归属机器断言）；「同一种错位：贾生见而空/义山不见」'
        '系读法声明；「名宦不进，坎壈终身」系史臣自断（照登 LIKELY）；'
        '字义山/开成二年/随亚岭表/三十六体/府罷客滎陽诸在册句（V016）零重开；'
        '旧传李商隐段賈生/賈誼/蒼生/鬼神/宣室/前席全零（机器断言）；'
        '本诗无底注无岁数注（无注可登）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-031-scene', 'source-ws-t300-031',
     '页面 賈生（《唐詩三百首》第 31 首选本页；header author+poem 块四句——'
     '全句**第二引**：V018 卷540 卷页一引在先，本引系 ws 诗页第二面——'
     '**两引面不重叠，上限恰满**，生成时全库查重双针恰一处，此后此诗正文关闭；'
     'notes 无 Textquality 评级（无评级页首见）；{{另}}/{{別}}/{{*}}/<ref> 全零；'
     '页内 Vtext/poem 双转录并存各从其录）',
     join(WS_AUTHOR, WS_BODY)),
    ('claim-bg-031-city', 'source-ws-t300-031',
     '页面 賈生（header title+整页 notes 行+分类四行连片——notes 只有三百首选本'
     '标记而无评级=无评级页首见；分类四行系列最多首录：第三行简体「唐诗」与'
     '第四行繁体「唐詩三百首」同页混排首见照登；分类行与 sortkey 系整理者/编排'
     '动作：非史料声明、不升格）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-031-city', 'source-quantangshi-540',
     '卷五百四十·李商隱《賈生》块（锚「==賈生==」卷页旧式裸名+poem 四句）'
     '……《安定城樓》「賈生年少虛垂涕，王粲春來更遠遊。」句（**同卷自引**——'
     '卷540「賈生」恰三=锚+正文+自引机器断言；虛前席/虛垂涕双虚字同诗人首见；'
     '安定城樓句全库域恰零本迁移首引；源行系 V018 已立、本迁移复用零新建）',
     join(V540_ANCHOR, V540_SELF)),
    ('claim-bg-031-world', 'source-zizhi-tongjian-events',
     '卷一百九十四·貞觀八年（甲午，六三四）魏徵引賈誼痛哭对段……卷二百三十八·'
     '元和七年（壬辰，八一二）李絳引厝火積薪段……卷二百四十八·會昌六年（丙寅，'
     '八四六）可憐彼翁受撻段（**通鉴賈生/宣室/前席/逐臣/才調全零、賈誼恰二、'
     '可憐恰一**：文件闭域+三处年标题窗口机器断言——史部只有贾谊的话头，'
     '唯一的可怜怜的是科场老吏；三段史文逐字入引为判决证据；痛哭对切片未及'
     '同段既有已引语——零重开；全唐詩在册句零入引）',
     join(TJ_ZT, TJ_CH, TJ_KE)),
    ('claim-bg-031-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）'
     '（「绹不之省」句+「名宦不进，坎壈终身。」句——皆全库查重恰零域首引；'
     '传区间归属机器断言；后者系史臣自断非自家语；「屡启而不见/见而空」对照'
     '系读法声明；字义山/岭表/三十六体诸在册句零重开）',
     join(JTS_P1, JTS_P2)),
]
BG_LINES = {'bg-031-scene': (1,), 'bg-031-city': (2,),
            'bg-031-world': (3,), 'bg-031-person': (4,)}
BG_AUDIENCE = {'bg-031-scene': 'PRIMARY', 'bg-031-city': 'JUNIOR',
               'bg-031-world': 'SENIOR', 'bg-031-person': 'JUNIOR'}
BG_TITLES = {'bg-031-scene': '眼前：宣室那场没问对的夜谈',
             'bg-031-city': '这座城：同一卷里两个虛字',
             'bg-031-world': '这个天下：史部只有贾谊的话头',
             'bg-031-person': '这个人：求见而不被见'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 47 首·四句七绝 1/1/1/1 第三次）；史实句均有逐字引证；'
                 '系年第四十一次判决（题证系列第廿九状·贾生与可怜）'
                 '「詩有賈生的場景，史部只有賈誼的话头」——同字两界第十一形态·'
                 '咏史形态首见：通鉴賈生/宣室/前席/逐臣/才調/虛前席/問鬼神全零；'
                 '賈誼恰二闭域双窗口入引（貞觀八年甲午六三四魏徵引「可為痛哭者一」'
                 '对+元和七年壬辰八一二李絳引「厝火積薪之下不可謂安」——'
                 '史部贾谊=谏臣话头/诗贾谊=灯火场景）；可憐恰一闭域窗口入引'
                 '（會昌六年丙寅八四六「可憐彼翁每歲受撻」——一怜劳力/一怜空才）；'
                 '全唐詩宣室恰 4/前席恰 2/逐臣恰 3/才調恰 3/夜半恰 9/可憐恰 39'
                 '在册零入引；卷540「賈生」恰三=锚+正文+《安定城樓》「賈生年少'
                 '虛垂涕」**同卷同诗人自引首见（虛前席/虛垂涕双虚字）**；'
                 'ws 页**无 Textquality 评级页首见**（notes 只有三百首标记）+'
                 '分类四行系列最多首录+同页简繁混排（简体「唐诗」繁体「唐詩三百首」）'
                 '首见照登；**新建 source-ws-t300-031 恰一枚（连续六首零新源诚实'
                 '终结——V018 以卷540 卷页立诗、ws 选本页从未建源，卷页/诗页两个'
                 '独立见证面；audit 断言恰一枚新源 INSERT）**；正文第二引上限用满'
                 '第十四例（V018 卷页在先+双针恰一，两引面不重叠）；'
                 'PERSON 旧传简化字段首引二句（绹不之省+名宦不进坎壈终身——'
                 '贾生见而空/义山不见的错位读法声明）；旧传段贾生/苍生/鬼神/宣室/'
                 '前席全零；KNOWN 零如实记录（第廿二例，audit 反向断言）；'
                 '判例关键语零入引文。' for k in BG}

NEW_SOURCE_ROW = {
    'id': 'source-ws-t300-031',
    'title': '维基文库《唐詩三百首》页面：賈生',
    'author': None,
    'edition': '全唐詩',
    'url': 'https://zh.wikisource.org/wiki/賈生',
    'rights_note': (
        '维基文库录入本，公有领域古籍。本行由 emit_v066.py 对 /tmp/src-dl 快照逐字定位。'
        '本诗 V018 立正文时用的是《全唐詩》卷540 卷页（source-quantangshi-540，'
        'version_code vol-raw），此《唐詩三百首》选本页当时未建源——卷页与诗页是'
        '两个独立见证面（卷页锚点归属 vs 选本页 header 署名/底注/分类），'
        '本迁移引诗页非新源不能承载。页面 notes 只有 {{唐詩三百首}} 标记而无 '
        'Textquality 评级（系列唯一无评级页照登）；页内 Vtext/poem 双转录并存；'
        '分类四行含简体「唐诗」与繁体「唐詩三百首」同页混排（照登）。'
        '核验状态保持 PENDING。'),
    'verification_status': 'PENDING',
    'source_kind': 'POETRY_COLLECTION',
    'reliability': 'HIGH',
}


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
    A("""-- V066：李商隱《賈生》(work-t300-031) 四层背景（阶段 D 第 47 首·贾生与可怜）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V048、V057、V058、V059、V060、V061、V062、
--       V063、V064、V065 已执行
--       （work-t300-031 与其 text-work-t300-031-ws、source-quantangshi-540 是 V018 的行
--       （V018 以卷540 卷页立本诗正文，version_code=vol-raw——ws 选本页当时未建源）；
--       source-ws-t300-031 是本迁移新建的选本页源（恰一枚；audit 断言）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体 V016、狂夫之言 V065、避地桃源诸语 V064）
--       只对照不重开）。
--       **本迁移新建恰 1 个 source（source-ws-t300-031）——连续六首零新源诚实终结；
--       audit 断言恰一枚诗源表新建插入语句且 id 唯一、回滚按 id 删且只删此行。**
--
-- 数据源（可复现）：emit_v066.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/賈生.txt（无 Textquality 评级首见+notes 只有三百首标记+零异文标记+
--   分类四行简繁混排+Vtext/poem 双转录）、
--   全唐詩卷540（旧式裸名锚+poem 块+《安定城樓》自引句；賈生恰三闭域；
--   宣室/前席/逐臣/才調/夜半/可憐 全库存档扫描）、
--   舊唐書卷190下（李商隐段首引二句+段内诗面字全零+段边界 ==弟 羲叟== 断言）、
--   通鑑卷194/238/248（贾谊恰二+可怜恰一+三处年标题窗口）+
--   通鑑 75 卷负证计数扫描（賈生/宣室/前席/逐臣/才調/虛前席/問鬼神）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域/新源不存在前提全部生成时断言。
--
-- 做：新 poetry_source 行 1（source-ws-t300-031，PENDING）+
--   4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 background_line（四句七绝 **1/1/1/1 第三次**（V056/V061 之后）：scene→1 city→2
--   world→3 person→4，绑 text-work-t300-031-ws 的 4 行）+ 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「詩有賈生的場景，史部只有賈誼的话头」）：
--   * 贾生场景词通鉴全零+贾谊恰二双窗口入引+可怜恰一窗口入引（一怜劳力/一怜空才）；
--   * 「贾生见而空/义山不见」错位对照标明读法声明；「名宦不进，坎壈终身」标明史臣自断；
--   * 同卷同诗人自引（虛前席/虛垂涕）系卷540 恰三闭域上的照登，非外部佐证；
--   * 无评级页/分类四行/简繁混排均照登不判（选本标记与转录评级、编排与史料是两回事）；
--   * 新源恰一枚如实开例（两引面不重叠声明在案），审计断言唯一性，回滚可精确撤销；
--   * 全唐詩宣室/前席/逐臣/才調/夜半/可憐在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第廿二例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 义山/开成二年/岭表/三十六体/荥阳卒（V016）、狂夫之言（V065）判例只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 65，不含 66
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-031-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-031','source-quantangshi-540');  -- 只含 540
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-031-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-031-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-031';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-031-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-031';   -- 恰 1（本迁移新建）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-031'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-031';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-031-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V066_rollback.sql（按 id 全枚举删除；source 只删本迁移新建的
--   source-ws-t300-031 一行——source-quantangshi-540 系 V018 所立绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新 source 恰一枚（source-ws-t300-031 选本页；PENDING 照 V031/V035/V036 判例） ----------')
    scols = ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability']
    A(guard('poetry_source', scols, [NEW_SOURCE_ROW], 'x.id = t.id'))

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
    brows = [{'id': k, 'work_id': 'work-t300-031',
              'layer': {'bg-031-scene': 'SCENE', 'bg-031-city': 'CITY',
                        'bg-031-world': 'WORLD', 'bg-031-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句七绝 1/1/1/1 第三次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-031-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 66, 'Li Shang-yin''s Jia Yi (work-t300-031) background layers (stage-D poem 47, four-line jueju 1/1/1/1 third time): dating verdict forty-one, twenty-ninth shape of the title-evidence series -- Jia Sheng and kelian, the archaist split in two realms: the poem stages Jia Yi''s night audience -- the Xuan-hall summons, the midnight席 moved forward, the questions about ghosts instead of the people -- and every staging word (Jia-sheng, xuanshi, qianxi, zhuchen, caidiao, wen guishen) scores zero across the Tongjian (machine-asserted); yet Jia Yi himself appears exactly twice, both as a talking point quoted by remonstrators at court: Wei Zheng citing the "one thing to weep over" memorial (Zhenguan 8th, jiawu, 634) and Li Ziang citing "fire stacked under firewood" to refuse a peace celebration (Yuanhe 7th, renchen, 812) -- the histories quote him, the poem enters his night (the eleventh same-character split, first archaist shape); kelian appears exactly once -- "pity that old man, flogged year after year" over the exam-reminders (Huichang 6th, bingyin, 846): the histories'' pity is for a beaten clerk, the poem''s pity is for a genius asked the wrong questions; juan 540 holds exactly three Jia-sheng characters (closed-domain assert): this poem''s anchor, this poem''s line, and Li Shang-yin''s own self-quote in "Ascending the City of Ding''an" -- "Jia Yi wasted his tears when young" -- two xu (in-vain) characters, one poet, one scroll (first self-quote seen: wasted-the-seat / wasted-the-tears); the ws anthology page carries no Textquality grade at all (first grade-less page; the marker in notes is the selection mark, not a transcription grade) with four category rows (series most, first) mixing simplified tang-shi and traditional tang-shi-shi-baishou on one page (logged); PERSON first-cites two zero-domain sentences from the simplified-character JTS biography -- "Tao never glanced at his letters" and "office never advanced; hardship to the end" (the historian''s own verdict, logged as such): Jia Yi was seen and asked wrongly, Li Shang-yin was never seen at all (reading declared); the biography segment contains no Jia-sheng/cangshen/guishen/xuanshi/qianxi character (machine-asserted); exactly ONE new poetry_source row (source-ws-t300-031): V018 had sourced the poem from the juan-540 scroll page and the ws anthology page had never been sourced -- two independent witnesses (anchor attribution vs anthology header/notes/categories), so the honest zero-new-source streak of six poems ends here by principle, audit-asserted single INSERT, rollback deletes only this row; body quotes hit their two-use ceiling (V018 scroll-page citation first, twin needles; the two witnesses never overlap); KNOWN zero honestly recorded (twenty-second instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 66);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V066 精确回滚：只删 V066 插入的行（id 全枚举）。source 只删一行：',
         '-- source-ws-t300-031 是本迁移新建的选本页源（恰一枚，审计断言）——按 id 删除；',
         '-- source-quantangshi-540 是 V018 已立的卷540 卷页源（本迁移复用），绝不删；',
         '-- work-t300-031 本体、其 text_line 4 行都是 V018 的行，绝不删；',
         '-- source-zizhi-tongjian-events / source-jiutangshu-wenyi 为他迁移所立，零删除。',
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
    L.append("DELETE FROM poetry_source WHERE id = 'source-ws-t300-031';")
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 66;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_BODY,
              V540_ANCHOR, V540_SELF, TJ_ZT, TJ_CH, TJ_KE, JTS_P1, JTS_P2]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 无评级页 + notes 只有三百首 + 分类四行照登硬卡（CITY ws 引文）
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-031-city' and s == 'source-ws-t300-031')
    if 'notes    = {{唐詩三百首}}' not in city_ws:
        bad.append('notes 整行（只有选本标记无评级）未逐字入 CITY 引文（无评级页首见照登硬卡）')
    if '[[Category:唐诗]]' not in city_ws or '[[Category:唐詩三百首|李]]' not in city_ws:
        bad.append('分类简繁混排未逐字入 CITY 引文（同页混排首见照登硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-031-city' and s == 'source-ws-t300-031'):
        bad.append('CITY ws locator 须含「不升格」声明（分类行三重断言失效）')
    # 卷页锚+自引照登硬卡
    city_q = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-031-city' and s == 'source-quantangshi-540')
    if '==賈生==' not in city_q or '賈生年少虛垂涕' not in city_q:
        bad.append('卷540 锚或自引句未逐字入 CITY 引文（同卷自引首见照登硬卡）')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-031-scene' and s == 'source-ws-t300-031')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V065 同款硬卡）')
    # WORLD：三段史文必须在引文内；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-031-world')
    for tok in ('可為痛哭者一', '厝火積薪之下', '可憐彼翁每歲受撻'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（贾谊两处/可怜一处必须入引）')
    for tok in ('宣室求賢', '夜半虛前席', '問蒼生', '安定城樓', '虛垂涕'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    # PERSON 首引句必须在引文内
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-031-person')
    for tok in ('绹不之省', '坎壈终身'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    if '狂夫之言' in cited or '所謂狂夫' in cited:
        bad.append('V065 已引「狂夫之言」零重开——本迁移切片必须止于痛哭对')
    for c, s, _, ex in CITATIONS:
        if not s.startswith('source-ws-t300-') and s != 'source-quantangshi-540':
            for w in ('謫仙', '脫靴', '賜金放還', '宮錦袍', '夜郎', '山東人'):
                if w in ex:
                    bad.append(f'非 ws/卷页引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒',
                '仕宦之疾徑', '茶鐺', '解官以贖', '柴毁骨立', '毀幾不生',
                '車如流水馬如龍', '歴右拾遺', '天寳末，為給事中', '或牒歸故鄉',
                '昆仲宦遊兩都', '輞口', '藍田别墅', '下馬飲君酒', '歸臥南山陲',
                '閉關以拒之', '殺郡王', '雲南王孫', '春草未生', '今宵歸不歸',
                '山中相送罷', '日暮掩柴扉', '一作山中送別', '聚斂為長策',
                '脫巾解帶', '解帶繫頸', '議者不之罪', '晚年唯好靜', '漁歌入浦深',
                '貶晙為梓州刺史', '段子璋反', '參天可汗道', '火炬於樹杪',
                '九歲知屬辭', '別墅在輞川', '華子岡', '版圖墮於避地', '避地江左',
                '龍陽江漲', '仙源公主', '碧玉赴井死', '狂夫之言', '狂夫竊發',
                '不傷良人', '綠珠怨', '贈秘書監', '停筆而化',
                '李商隐，字义山，怀州河内人。', '开成二年，方登进士第',
                '商隐随亚在岭表累载', '与太原温庭筠、南郡段成式齐名',
                '府罷，客滎陽，卒'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 四句 1/1/1/1 第三次
    if {k: v for k, v in BG_LINES.items()} != {'bg-031-scene': (1,), 'bg-031-city': (2,),
                                               'bg-031-world': (3,), 'bg-031-person': (4,)}:
        bad.append('四句 background_line 须 1/1/1/1（第三次）')
    if len(re.findall(r"text-work-t300-031-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # **新源恰一枚**（本迁移是 V058 以来首例——断言反转为恰一 INSERT 且 id 正确）
    ins_src = sql.count('INSERT INTO poetry_' + 'source')
    if ins_src != 1:
        bad.append(f'本迁移应恰新建 1 个 source（恰一枚 INSERT），实 {ins_src}')
    src_blk = sql[sql.index('INSERT INTO poetry_' + 'source'):]
    src_blk = src_blk[:src_blk.index(';')]
    if "'source-ws-t300-031'" not in src_blk or "'source-quantangshi-540'" in src_blk:
        bad.append('新源 INSERT 的 id 不对（应恰 source-ws-t300-031，不得含 540）')
    rb = build_rollback()
    if rb.count('DELETE FROM poetry_source') != 1 or 'source-ws-t300-031' not in rb.split('DELETE FROM poetry_source')[1][:60]:
        bad.append('回滚的 source 删除应恰一行且只删 source-ws-t300-031')
    if 'source-quantangshi-540' in rb.split('DELETE FROM poetry_source')[1]:
        bad.append('回滚绝不得删 source-quantangshi-540（V018 所立）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V066 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V066 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-031' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V066 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-031' AS subject_id" in sql:
        bad.append('V066 的 claim 主语应全部是 bg-031-*，work-t300-031 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V066 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '话头' not in ''.join(BG.values()):
        bad.append('BG/WORLD 须含「史部只有賈誼的话头」判决声明')
    if '咏史形态首见' not in body_all and '咏史形态首见' not in body_all:
        bad.append('BG 须含「咏史形态首见」（同字两界第十一形态）声明')
    if '同卷' not in body_all or '自引' not in body_all:
        bad.append('BG/CITY 须含「同卷同诗人自引」首见声明')
    if '无评级页' not in body_all:
        bad.append('BG 须含「无评级页首见」声明')
    if '新源' not in body_all or '恰一' not in body_all:
        bad.append('BG/CITY 须含「新建恰一枚 source」诚实开例声明')
    if '虚前席' not in body_all or '虛垂涕' not in body_all:
        bad.append('BG/CITY 须含「虛前席/虛垂涕双虚字」对照声明')
    if '读法声明' not in body_all:
        bad.append('BG 须含「读法声明」')
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
    if len(NEW_SOURCE_ROW['id']) > 64 or len(NEW_SOURCE_ROW['title']) > 200 \
            or len(NEW_SOURCE_ROW['rights_note']) > 1000:
        bad.append('poetry_source 新行宽度超限')
    for m in re.finditer(r'INSERT INTO (poetry_\w+)', sql):
        if m.group(1) == 'poetry_schema_version':
            continue  # 长英文版本描述使通用状态机失步——V064/V065 判例：下面显式断言
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
    # 版本账本显式守卫（V064/V065 判例延续）
    vblk = sql[sql.index('INSERT INTO poetry_schema_version'):]
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 66)' not in vblk:
        bad.append('poetry_schema_version INSERT 缺显式幂等守卫')
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
              f'切片传区间归属断言（旧传李商隐段二首引句，段界 ==弟 羲叟==）；'
              f'三处年标题窗口断言（貞觀八年六三四/元和七年八一二/會昌六年八四六）；'
              f'负证机器复查五层（通鉴賈生/宣室/前席/逐臣/才調/虛前席/問鬼神全零+'
              f'賈誼恰二闭域(tj-194/238)+可憐恰一闭域(tj-248)/卷540 賈生恰三闭域+'
              f'自引句与锚块各恰一/全唐詩宣室恰4前席恰2逐臣恰3才調恰3/'
              f'ws 无评级恰零+notes 选本标记恰一+零标记+分类四行连片简繁混排+'
              f'宣室句页内恰二/旧传段诗面字全零，快照变动即中止）；'
              f'前提全库查重硬卡六件+六首引句零域断言+新源 id 全库不存在断言+540 源恰[V018]域断言；'
              f'无评级页/分类简繁混排/卷页锚/自引句照登硬卡；CITY「不升格」硬卡；'
              f'SCENE 第二引/上限硬卡；贾谊可怜三史文入引+诗语零混入断言；'
              f'PERSON 二首引句入引硬卡+V065 狂夫之言零重开硬卡；'
              f'判例只引不重开断言（含 V064/V065 与 V016 李商隐在册诸语）；'
              f'四句 1/1/1/1 形制断言；零 KNOWN 反向断言；'
              f'**新源恰一枚断言（INSERT 恰一+id 正确+回滚恰删此行且不碰 540）**——'
              f'连续六首零新源诚实终结（卷页/诗页两个独立见证面）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
