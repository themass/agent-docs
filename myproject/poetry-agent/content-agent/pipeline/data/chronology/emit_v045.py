#!/usr/bin/env python3
"""阶段 D 第 26 首：生成 V045——李白《金陵酒肆留別》(work-t300-320, V018 已立) 四层背景。

「为什么写」再成立一次。这首把题拆开看是三个钉子：地名（金陵）、场所（酒肆）、
场面（留別）；再看两传——**金陵在李白传区间只有一处关联**（两传皆然），
而那处是**另一件事**：崔宗之谪官金陵、白与同舟笑傲的采石夜航段
（V032 城层已两史并立逐字——本迁移第二证，已达两度上限）。

系年第二十次判决（题证系列第八状）：**「题有地名有物色，地有传见而见必它事」**——
V044 是传锚在（辋川）而锚不系年；这首是传见在（金陵一见于两传）
而见必它事：同舟笑傲之城 vs 酒肆留別之城，同城两会，会各一事，
年份仍无。负证机器复查（V042 立规）：六个诗语在两传李白区间计数全零 +
**两传区间内每一处「金陵」都必须落在崔宗之句内**（位置断言，快照变动即中止）。

KNOWN 一处（两源独立一致）：
**李白与崔宗之同舟游赏金陵段**——旧传「時侍御史崔宗之謫官金陵，與白詩酒唱和。
嘗月夜乘舟，自采石達金陵，白衣宮錦袍，於舟中顧瞻笑傲，傍若無人」+
新传「白浮游四方，嘗乘舟與崔宗之自採石至金陵，著宮錦袍坐舟中，旁若無人」：
事体四要素两源一致（同舟崔宗之/采石—金陵之间/宫锦袍/旁若无人）升 KNOWN；
**叙事框架分歧各归其侧**（旧传：崔谪官金陵在前+白衣宮錦袍+顧瞻笑傲；
新传：白浮游四方+著宮錦袍+坐舟中）——audit 双向互斥断言。

PERSON 层不对称如实记：旧传李白区间「酒肆」两见（V036 已引嗜酒段——本层
嗜酒常态侧再证一句，同句两度为上限），**新传李白区块「酒肆」零见**
（生成时机器断言）——同一人同一癖好，两传的词汇密度不同，照登不推论。

异文照登断言反向使用（V044 立规）：此页三处 {{另}} 自注（風吹/白門、喚/勸、
試問/問取）必须原样进 SCENE 引文——其中「白門」一支异文自带金陵别称，
只在 BG 作读法注记，不裁决入正文。先登记后引用（tang300-variants.md 新行已入）。

六句 2/2/1/1（V037/V042 同款）；零新 source（ws-320/jts/xts 三源行均已立）。

用法: python3 -I emit_v045.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/金陵酒肆留別.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 金陵酒肆留別', '| title    = 金陵酒肆留別',
                         'ws header title(三钉齐全:地名+场所+场面)')
WS_AUTHOR = slice_between(WS, '| author   = 李白', '| author   = 李白', 'ws header author(署名直证)')
WS_L12 = slice_between(WS, '{{另|風吹|白門}}柳花滿店香，吳姬壓酒{{另|喚|勸}}客嘗。',
                       '{{另|風吹|白門}}柳花滿店香，吳姬壓酒{{另|喚|勸}}客嘗。',
                       'ws第1-2句联(柳花店香/吴姬压酒——物色与店人;两处异文原样)')
WS_L34 = slice_between(WS, '金陵子弟來相送，欲行不行各盡觴。', '金陵子弟來相送，欲行不行各盡觴。',
                       'ws第3-4句联(子弟相送/欲行不行——留别的拖延)')
WS_L56 = slice_between(WS, '請君{{另|試問|問取}}東流水，別意與之誰短長。',
                       '請君{{另|試問|問取}}東流水，別意與之誰短長。',
                       'ws第5-6句联(东流水比别意——问水的痴话;一处异文原样)')
JTS_CUI = slice_between(JTS, '時侍御史崔宗之謫官金陵，與白詩酒唱和。嘗月夜乘舟，自采石達金陵，白衣宮錦袍，於舟中顧瞻笑傲，傍若無人。',
                        '傍若無人。', '旧传采石夜航段(崔谪官金陵/与白唱和/月夜乘舟自采石达金陵/白衣宫锦袍顾瞻笑傲——同舟金陵两源合龙旧传侧;框架与措辞归旧侧)')
XTS_CUI = slice_between(XTS, '白浮游四方，嘗乘舟與崔宗之自採石至金陵，著宮錦袍坐舟中，旁若無人。',
                        '旁若無人。', '新传采石夜航段(白浮游四方/乘舟与崔宗之自采石至金陵/著宫锦袍坐舟中旁若无人——同舟金陵两源合龙新传侧;框架与措辞归新侧;与V032同两句之第二证)')
JTS_SHIJIU = slice_between(JTS, '白旣嗜酒，日與飲徒醉於酒肆。', '醉於酒肆。',
                           '旧传嗜酒短句(日与饮徒醉于酒肆——V036全段第一证的嗜酒常态侧再证,同句两度为上限;PERSON 层本体)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=李白='), JTS.find('=杜甫=')
_xa, _xb = XTS.find('==李白=='), XTS.find('===附 張旭===')
for _s, _tag in [(JTS_CUI, 'JTS_CUI'), (JTS_SHIJIU, 'JTS_SHIJIU')]:
    if not (0 <= _ja <= JTS.find(_s) <= _jb):
        raise SystemExit(f'切片越出李白传区间：{_tag}——修订后重生成')
for _s, _tag in [(XTS_CUI, 'XTS_CUI')]:
    if not (0 <= _xa <= XTS.find(_s) <= _xb):
        raise SystemExit(f'切片越出李白传区块：{_tag}——修订后重生成')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
# ① 六个诗语在两传李白区间必须计数全零——「酒肆留别的场面在传中零记录」由此可复查
for _w in ('吳姬', '柳花', '盡觴', '東流水', '子弟', '留別'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'两传李白区间出现「{_w}」——酒肆留别场景零记录负证失效，须重读原文再设计')
# ② 金陵位置断言：两传李白区间内每一处「金陵」都必须落在崔宗之句内
for _seg, _cui, _src in ((_seg_j, JTS_CUI, 'JTS'), (_seg_x, XTS_CUI, 'XTS')):
    _c0 = _seg.find(_cui)
    for _m in re.finditer('金陵', _seg):
        if not (_c0 <= _m.start() < _c0 + len(_cui)):
            raise SystemExit(f'金陵位置断言失效：{_src} 李白区间出现崔宗之句外的「金陵」——「一见于传而见必它事」判决须重估')
# ③ 旧传「酒肆」两见而新传区块零见——不对称负证
if JTS[_ja:JTS.find(JTS_CUI)].count('酒肆') != 2:
    raise SystemExit('旧传李白区间崔宗之句前的「酒肆」计数不是 2——嗜酒两见负证失效')
if '酒肆' in _seg_x:
    raise SystemExit('新传李白区块出现「酒肆」——旧传两见新传零见的词汇不对称负证失效')

BG = {
    'bg-lb-scene': (
        '题三个钉子：金陵（城）、酒肆（店）、留別（场面）。开场是春天开进店里：'
        '柳絮（异文作「白門」——白門本是金陵别称，一支异文自带地名，照登不裁决）'
        '飞满店铺，酒是新压的，唤客人来尝的是吴地酒家女'
        '（「柳花滿店香，吳姬壓酒喚客嘗」——香是柳花的还是酒的，句法故意不分）；'
        '来送行的是本地一群年轻朋友，走走停停、停停又饮'
        '（「金陵子弟來相送，欲行不行各盡觴」——「欲行不行」四字把起身又坐下的'
        '拖延全装下）；最后客人干了件痴事：请诸位试问东流的水，'
        '这别意跟水比谁长谁短（「請君試問東流水，別意與之誰短長」——'
        '把抽象的「别意」递给水去称量，是李白送别的招牌手势）。\n'
        '三处页内自注（風吹/白門、喚/勸、試問/問取）照登不裁决，引文含标记原样。'),
    'bg-lb-city': (
        '这座城在两传李白区间只有一处关联，而那处是**另一件事**：'
        '采石到金陵的夜航、同舟的是崔宗之、看的是顾瞻笑傲——'
        '同舟笑傲之城，与这首诗的酒肆留別之城同城两会，会各一事。\n'
        '负证机器复查（生成时断言，快照变动即中止）：'
        '吳姬/柳花/盡觴/東流水/子弟/留別六个诗语在两传李白区间计数全零；'
        '两传区间内每一处「金陵」都落在崔宗之句内——诗里的店、人、水在传中'
        '无处落籍，城里唯一的传见又被另一场宴会占了。'
        '题有地名有物色，地有传见而见必它事：同城不同事，年份仍无——'
        '金陵在传给不出这条街的坐标，金陵在诗给不出这一年的日期。'),
    'bg-lb-world': (
        '两唐书共同保住了李白生涯里一场著名的夜航：\n'
        '旧传「時侍御史崔宗之謫官金陵，與白詩酒唱和。嘗月夜乘舟，自采石達金陵，'
        '白衣宮錦袍，於舟中顧瞻笑傲，傍若無人」；新传「白浮游四方，嘗乘舟與崔宗之'
        '自採石至金陵，著宮錦袍坐舟中，旁若無人」——**事体四要素两源一致**'
        '（与崔宗之同舟/采石—金陵之间/着宫锦袍/旁若无人）：'
        '**同舟游赏金陵段升 KNOWN**（V032 城层已两史并立逐字，当时判 LIKELY 系'
        '就城层合盘而言；本层就事体本身两源合龙——判例：合龙看要素不看层名）。\n'
        '**叙事框架分歧各归其侧不裁决**：旧传以崔宗之谪官金陵为事由、白往和之，'
        '新传以白浮游四方为主线、崔为同舟——袍之「白衣宮錦袍」／「著宮錦袍」、'
        '态之「顧瞻笑傲」／「坐舟中」亦然（audit 双向互斥断言）。\n'
        '这条 KNOWN 是「天下」层给这首诗的上下文：盛唐士人游赏的排场由'
        '两史共证——但它**不外溢为写作时间**：同舟是夜航，留別是晨饮，'
        '同城异景，谁也不给谁系年。'),
    'bg-lb-person': (
        '旧传给李白留了一个词汇学的事实：**「酒肆」在他传内两见**'
        '（「白旣嗜酒，日與飲徒醉於酒肆」——嗜酒常态侧，V036 已引全段第一证、'
        '此句再证即达两度上限；后一处即玄宗亟召、醉卧酒肆那个著名段子），'
        '而**新传李白区块「酒肆」零见**（生成时机器断言）——'
        '同一人同一癖好，两传的词汇密度不同，照登不推论'
        '（不裁「哪个传更真」，只记两传各用什么词讲这个人）。\n'
        '这首诗把这个词汇学的事实变成前台：诗题的「酒肆」正是旧传的两处酒肆之一'
        '所住的那种场所——但诗里的酒肆在金陵、传里的酒肆不明所在，'
        '场所同、坐标异。判例零重开：浪迹江湖（V032/V041）、'
        '竹溪六逸（V041）、脫靴斥去（V041）、青山终焉（V032）皆不引。'),
}
CLAIMS = {
    'claim-bg-lb-scene': (
        'FACT', 'LIKELY',
        '六句全诗本文（ws 页三处 {{另}} 页内自注原样照登——先登记后引用，'
        'tang300-variants.md 新行；Textquality 75% 如实记；异文「白門」自带'
        '金陵别称仅作读法注记不裁决）；香之归属/欲行不行/问水比别意为本层读法声明，'
        '非史料断言。'),
    'claim-bg-lb-city': (
        'FACT', 'LIKELY',
        '题三钉（地名+场所+场面）；两传李白区间金陵仅一处关联且必为崔宗之句'
        '（位置断言生成时复查）；六诗语两传区间计数全零（生成时断言）；'
        '同城两会会各一事→题有地名有物色，地有传见而见必它事→'
        '零铸造零 relation。'),
    'claim-bg-lb-world': (
        'FACT', 'KNOWN',
        '同舟游赏金陵段事体四要素两源独立一致（与崔宗之同舟/采石—金陵之间/'
        '宫锦袍/旁若无人）→升 KNOWN（V032 城层并立判 LIKELY 系合盘而言，'
        '本层就事体合龙——合龙看要素不看层名）；叙事框架与措辞分歧'
        '（谪官唱和/浮游四方、白衣宮錦袍/著宮錦袍、顧瞻笑傲/坐舟中）'
        '各归其侧不裁决（audit 双向互斥）；同城异景不外溢为写作时间；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during '
        '零铸造零 relation。'),
    'claim-bg-lb-person': (
        'FACT', 'LIKELY',
        '旧传李白区间酒肆两见（嗜酒常态句再证达两度上限）而新传区块酒肆零见'
        '（生成时断言）——两传词汇密度不对称如实照登不推论；'
        '场所同坐标异；浪迹江湖/竹溪六逸/脫靴斥去/青山终焉判例零重开'
        '（audit 关键语硬卡）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-lb-scene', 'source-ws-t300-320',
     '页面 金陵酒肆留別（header title+author+六句三联，五段以「……」相連——'
     '三处 {{另}} 自注原样照登（先登记后引用，tang300-variants.md 新行）；'
     '同一 (claim,source) 主键下一行容全文，V037/V039/V040/V041/V042/V043/V044 判例；'
     '全文另见 V018 claim-t300-320-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56)),
    ('claim-bg-lb-city', 'source-ws-t300-320',
     '页面 金陵酒肆留別（header title 单字段——题三钉（地名+场所+场面）即证据本体；'
     '六诗语与金陵位置的负证为两传区间生成时机器断言，诗身不代拟进引文）',
     WS_TITLE),
    ('claim-bg-lb-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传采石夜航段（崔谪官金陵/月夜乘舟自采石达金陵/'
     '白衣宫锦袍顾瞻笑傲——同舟金陵两源合龙旧传侧逐字；'
     'V032 城层已立此句，此处事体侧再证——第二证已达两度上限，locator 声明）',
     JTS_CUI),
    ('claim-bg-lb-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传采石夜航段（浮游四方/乘舟与崔宗之自采石至金陵/'
     '著宫锦袍坐舟中旁若无人——两源合龙新传侧逐字；框架与措辞归新侧'
     '与旧侧各归其侧不裁决；V032 城层已立此句，此处事体侧再证——第二证已达两度上限）',
     XTS_CUI),
    ('claim-bg-lb-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传嗜酒短句（日与饮徒醉于酒肆——V036 全段'
     '乐府新词侧第一证，此处嗜酒常态侧再证——同句两度为上限；'
     '新传区块酒肆零见的不对称由生成时断言保证，无新传侧引文即无代拟）',
     JTS_SHIJIU),
]
BG_LINES = {'bg-lb-scene': (1, 2), 'bg-lb-city': (3, 4), 'bg-lb-world': (5,), 'bg-lb-person': (6,)}
BG_AUDIENCE = {'bg-lb-scene': 'PRIMARY', 'bg-lb-city': 'JUNIOR',
               'bg-lb-world': 'SENIOR', 'bg-lb-person': 'SENIOR'}
BG_TITLES = {'bg-lb-scene': '眼前：春天开进店里',
             'bg-lb-city': '这座城：同城两会',
             'bg-lb-world': '这个天下：一场两史共证的夜航',
             'bg-lb-person': '这个人：两传词汇学'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 26 首·六句 2/2/1/1）；史实句均有逐字引证；'
                 'background_line 六句形制：scene 两行 city 两行 world/person 各一行；'
                 '系年第二十次判决「题有地名有物色，地有传见而见必它事」'
                 '（题证系列第八状）→time.span/event.name/written_during 全缺席、'
                 '零 relation；KNOWN 一处（同舟游赏金陵段事体四要素两源一致——'
                 '合龙看要素不看层名）；叙事框架分歧各归其侧不裁决（audit 双向互斥）；'
                 '负证机器复查（六诗语零计数+金陵位置断言+酒肆两见/零见不对称）；'
                 '采石两句与嗜酒一句各达两度上限；判例零重开。' for k in BG}


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
    A("""-- V045：李白《金陵酒肆留別》(work-t300-320) 四层背景（阶段 D 第 26 首·六句 2/2/1/1）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-320 与其 text-work-t300-320-ws、
--       source-ws-t300-320 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——均不另开）。本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v045.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/金陵酒肆留別.txt（三处 {{另}} 自注原样照登，先登记后引用）、
--   舊唐書卷190下（采石夜航段+嗜酒短句）、新唐書卷202（采石夜航段）——
--   三段切片传区间归属生成时断言；六诗语两传区间计数全零+金陵位置断言+
--   旧传酒肆两见新传零见不对称，全部生成时断言（负证机器复查）。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   5 组逐字引用（(claim,source) 主键每对恰一行）+
--   6 行 background_line（六句形制：scene→1-2 city→3-4 world→5 person→6，
--   绑 text-work-t300-320-ws 的 6 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「题有地名有物色，地有传见而见必它事」）：
--   * 题三钉齐全（金陵/酒肆/留別）但两传李白区间金陵仅一处关联、且必为崔宗之句
--     （位置断言机器复查）；同舟笑傲之城与酒肆留別之城同城两会会各一事；
--   * 采石夜航两句（V032 城层已立）与嗜酒短句（V036 已立）各为第二证——
--     **同句两度为上限**，locator 逐一声明；
--   * KNOWN 一处：同舟游赏金陵段事体四要素两源一致（合龙看要素不看层名）——
--     叙事框架/袍之措辞/舟中之态分歧各归其侧不裁决（audit 双向互斥），
--     同城异景不外溢为写作时间；
--   * 旧传酒肆两见新传零见的词汇不对称如实照登不推论；
--   * 浪迹江湖（V032/V041）/竹溪六逸（V041）/脫靴斥去（V041）/青山终焉（V032）
--     判例只引不重开（audit 关键语硬卡）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 44，不含 45
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-lb-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-320-ws';  -- 恰 6（七古）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-lb-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-320';                                  -- 6（2/2/1/1）
--   SELECT certainty FROM poetry_claim WHERE id = 'claim-bg-lb-world';  -- KNOWN（同舟金陵两源）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-lb-scene','claim-bg-lb-city','claim-bg-lb-person');
--     -- LIKELY / LIKELY / LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-320'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-320';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-lb-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V045_rollback.sql（按 id 全枚举删除；不动 V018/V032/V036/V041 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-320',
              'layer': {'bg-lb-scene': 'SCENE', 'bg-lb-city': 'CITY',
                        'bg-lb-world': 'WORLD', 'bg-lb-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（六句：2/2/1/1） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-320-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 45, 'Li Bai Staying at a Wine Shop in Jinling background layers (stage-D poem 26, six-line 2/2/1/1): dating verdict twenty, eighth shape of the title-evidence series -- the title drives three stakes (city / venue / parting) yet the city appears exactly once inside the Li Bai span of both histories and that appearance is always a different affair (the moonlit boat with Cui Zongzhi, established verbatim at the city layer by V032): the city of boating-side-by-side-laughing and the city of wine-shop-parting are one city, two gatherings -- zero forging, zero relation; machine re-checks at generation time (six poem-words counted zero across both spans, every occurrence of Jinling proven to sit inside the Cui sentence, the two-vs-zero asymmetry of the word for wine-shop between the two histories recorded without inference); one KNOWN: the moonlit boat segment as a fact agrees across both histories on four elements (fellow travelers with Cui Zongzhi / Caishi to Jinling / brocade robe / oblivious air) -- the stage-D rule: agreement is judged on elements, not on layer names; the narrative framing (Cui demoted to Jinling vs Li roaming the four quarters), the robe wording (in white brocade vs wearing brocade) and the posture on the boat all diverge and each stays on its side (bidirectional mutual-exclusion asserted); same city, different scene, never overflowing into writing time; the two Cui sentences and the one drinking sentence each reach the ceiling of two verbatim citations (locator-declared); the wandering/bamboo-creek/boots/banishment and Green Hills lines stay closed precedents (audit keyword zero-entry); zero new sources'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 45);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V045 精确回滚：只删 V045 插入的行（id 全枚举）。',
         '-- work-t300-320 本体、其 text_line 6 行与 source-ws-t300-320 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）与 V032/V036/V041 的行不删；',
         '-- V045 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 45;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, JTS_CUI, XTS_CUI, JTS_SHIJIU]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异文照登断言（V044 反向使用：有标记且已登记→必须原样入 ws 引文）
    ws_ex = ''.join(ex for _, s, _, ex in CITATIONS if s == 'source-ws-t300-320')
    for tok in ('{{另|風吹|白門}}', '{{另|喚|勸}}', '{{另|試問|問取}}'):
        if tok not in ws_ex:
            bad.append(f'ws 页内自注未原样照登: {tok}（先登记后引用，不可静默剥离）')
    # 同舟金陵两源合龙断言（事体四要素各侧在场）
    w_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-lb-world' and s == 'source-jiutangshu-wenyuan')
    w_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-lb-world' and s == 'source-xintangshu-wenyi')
    for tok in ('崔宗之', '采石', '金陵', '錦袍'):
        if tok not in w_jts.replace('採石', '采石') or tok not in w_xts.replace('採石', '采石'):
            bad.append(f'同舟金陵两源不齐（{tok} 须两侧在场——採石/采石视为同词异写）')
    # 框架分歧双向互斥
    if '浮游四方' in w_jts or '坐舟中' in w_jts:
        bad.append('框架分歧串侧（浮游四方/坐舟中不得入旧传侧）')
    if '謫官' in w_xts or '顧瞻笑傲' in w_xts or '白衣' in w_xts:
        bad.append('框架分歧串侧（謫官/顧瞻笑傲/白衣不得入新传侧）')
    # CITY 负证：引文零诗语（题三钉即证据本体，诗身不代拟）
    for c, s, _, ex in CITATIONS:
        if c == 'claim-bg-lb-city':
            for w in ('吳姬', '柳花', '盡觴', '東流水', '子弟'):
                if w in ex:
                    bad.append(f'CITY 层证据不得含诗语「{w}」')
    # 判例只引不重开（V032/V036/V041/V043/V044 关键语零入引文）
    for tok in ('浪迹江湖', '竹溪六逸', '脫靴', '高力士', '賜金放還', '悅謝家青山',
                '霓裳', '絕迹天機', '天機所到', '得宋之問藍田别墅', '地奇勝',
                '妻亡不再娶', '喪妻不娶', '篤志奉佛'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 六句形制 2/2/1/1
    want = {'bg-lb-scene': 2, 'bg-lb-city': 2, 'bg-lb-world': 1, 'bg-lb-person': 1}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('六句 background_line 必须 2/2/1/1（scene/city 各 2 行、world/person 各 1 行）')
    if len(re.findall(r"text-work-t300-320-ws' AS version_id", sql)) != 6:
        bad.append('bg_line INSERT 的 version 行数应为 6')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V045 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V045 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-320' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V045 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-320' AS subject_id" in sql:
        bad.append('V045 的 claim 主语应全部是 bg-lb-*，work-t300-320 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V045 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V045 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '见必它事' not in body_all:
        bad.append('BG/文件头须含「见必它事」判决声明')
    if '两度为上限' not in body_all:
        bad.append('BG/文件头须含「同句两度为上限」声明（采石两句+嗜酒一句）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 8 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；负证机器复查（六诗语两传区间计数全零+金陵位置断言+'
              f'旧传酒肆两见新传零见不对称，快照变动即中止）；ws 三处自注原样照登断言；'
              f'同舟金陵两源合龙断言（四要素）+框架分歧双向互斥断言；CITY 零诗语断言；'
              f'判例只引不重开断言（浪迹/竹溪/脫靴/赐金/青山/天机/辋川/鳏居/奉佛关键语零入引文）；'
              f'两度上限声明断言；六句 2/2/1/1 形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
