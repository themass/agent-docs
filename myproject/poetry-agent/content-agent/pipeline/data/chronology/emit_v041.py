#!/usr/bin/env python3
"""阶段 D 第 22 首：生成 V041——李白《送友人》(work-t300-323, V018 已立) 四层背景。

「为什么写」第十四次成立，这首给的是**空白最多的一首**：
题只给角色不给人名（「友人」），诗只给意象不给锚点
（「青山橫北郭，白水繞東城」——青山白水是律诗通用对，不是地名），
受赠人与饯地两头全空，连 V037 送別那样的首句消歧都没有。

系年第十六次判决（题证系列第四状）：**「题有角色无人，诗有意象无地」**——
V037「送别无系事+受赠人无名」是题短；这首是题给满了类别（送、友人）
而每一类都落空。两传对李白的行迹写得再满——徂徠山、會稽、長安、
金陵、夜郎、宣城——也**无一字系这场送别**。不选友人不选城：
「北郭/東城」的工整对恰恰是通用的证据，通用对不锚地。
time.span/event.name/written_during 零铸造，零 relation。

KNOWN 一处：**徂徠山「竹溪六逸」之集两源合龙**——
旧传「少與魯中諸生孔巢父、韓沔、裴政、張叔明、陶沔等隠於徂徠山，酣歌縱酒，
時號『竹溪六逸』」+ 新传「更客任城，與孔巢父、韓准、裴政、張叔明、陶沔
居徂徠山，日沈飲，號『竹溪六逸』」——集名与四人同名两源独立一致升 KNOWN；
**名单一名之异（韓沔/韓准）并列不裁决**（V036 卒地分歧同款：各归其侧，
audit 互斥断言）。李白年轻时不是一个人在写送别——他有一整个六人编制。

不裁决第二处·去翰林之因：旧传「由是斥去」（得罪史笔）vs
新传「懇求還山，帝賜金放還」（体面史笔）——两传各说一遍，
PERSON 层并列照登，audit 互斥断言（斥去语不入侵传侧、还山语不入侵旧传侧）。

身后节（新传单得不升）：范傳正祭塚改葬+文宗诏「三絕」——
李白身后被经典化的两幕，与「友人」同时代无人可考形成全诗最大反讽。
死状（醉死宣城/葬東麓）V036 已并列——本迁移零入引文，audit 硬卡。

跨迁移同句再证两处（V038 合规先例）：JTS_ZX（V032 徂徠段）、
JTS_CQ（V032 脱靴段前部）——claim 不同故主键不冲突，locator 双声明。

八句第二例之后第三用：background_line 每层 2 行（1-2/3-4/5-6/7-8）。
ws 页干净（0 标记），异文登记零新行（audit 不查标记在场，反向：断言零标记不误引）。

用法: python3 -I emit_v041.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/送友人__李白_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 送友人', '| title    = 送友人',
                         'ws header title(题只给角色——送/友人两类皆类别名)')
WS_AUTHOR = slice_between(WS, '| author   = 李白', 'author   = 李白', 'ws header author(署名直证)')
WS_L12 = slice_between(WS, '青山橫北郭，白水繞東城。', '白水繞東城。', 'ws第1-2句联(青山白水——通用对不锚地)')
WS_L12A = slice_between(WS, '青山橫北郭，白水繞東城。', '青山橫北郭，', 'ws第1句(青山横北郭)')
WS_L34 = slice_between(WS, '此地一為別，孤蓬萬里征。', '孤蓬萬里征。', 'ws第3-4句联(此地一别/孤蓬万里)')
WS_L34A = slice_between(WS, '此地一為別，孤蓬萬里征。', '此地一為別，', 'ws第3句(此地一为别)')
WS_L56 = slice_between(WS, '浮雲遊子意，落日故人情。', '落日故人情。', 'ws第5-6句联(浮云游子/落日故人)')
WS_L56A = slice_between(WS, '浮雲遊子意，落日故人情。', '浮雲遊子意，', 'ws第5句(浮云游子意)')
WS_L78 = slice_between(WS, '揮手自茲去，蕭蕭班馬鳴。', '蕭蕭班馬鳴。', 'ws第7-8句联(挥手兹去/班马鸣)')
WS_L78A = slice_between(WS, '揮手自茲去，蕭蕭班馬鳴。', '揮手自茲去，', 'ws第7句(挥手自兹去)')
JTS_LJ = slice_between(JTS, '乃浪迹江湖，終日沉飲。', '終日沉飲。',
                       '旧传放还后行迹句(浪迹江湖终日沉饮——行迹总括无此地零系事之负证正面文本;V032 未引此后半段)')
JTS_ZX = slice_between(JTS, '少與魯中諸生孔巢父、韓沔、裴政、張叔明、陶沔等隠於徂徠山，酣歌縱酒，時號「竹溪六逸」。',
                       '時號「竹溪六逸」。',
                       '旧传竹溪六逸段(韩沔名单——六逸两源合龙旧传侧;V032 已立此句(徂徠线),此处集名侧再证;跨迁移同句再证,claim 不同主键不冲突)')
JTS_CQ = slice_between(JTS, '嘗沉醉殿上，引足令高力士脫靴，由是斥去。', '由是斥去。',
                       '旧传斥去段(得罪侧因果——去翰林分歧旧传侧;V032 已立此句前半(脱靴),此处斥去侧再证)')
XTS_ZX = slice_between(XTS, '更客任城，與孔巢父、韓准、裴政、張叔明、陶沔居徂徠山，日沈飲，號「竹溪六逸」。',
                       '號「竹溪六逸」。',
                       '新传竹溪六逸段(韩准名单——六逸两源合龙新传侧;名单一名之异并列不裁决,audit 互斥)')
XTS_FH = slice_between(XTS, '懇求還山，帝賜金放還。', '帝賜金放還。',
                       '新传还山段(体面侧因果——去翰林分歧新传侧,与旧传斥去各归其侧不裁决)')
XTS_JB = slice_between(XTS, '與知章、李適之、汝陽王璡、崔宗之、蘇晉、張旭、焦遂為「酒八仙人」。',
                       '為「酒八仙人」。', '新传酒八仙人段(长安东第二编制——新传单得)')
XTS_FCZ = slice_between(XTS, '元和末，宣歙觀察使范傳正祭其塚，禁樵採。', '禁樵採。',
                        '新传范传正段(身后元和末祭塚禁樵——身后经典化第一幕,新传单得不升;死状句 V036 已立不重开,本段不含)')
XTS_WZ = slice_between(XTS, '文宗時，詔以白歌詩、裴旻劍舞、張旭草書為「三絕」。', '為「三絕」。',
                       '新传三绝段(文宗诏三绝——身后经典化第二幕,新传单得不升)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=李白='), JTS.find('=杜甫=')
_xa, _xb = XTS.find('==李白=='), XTS.find('===附 張旭===')
for _s, _tag in [(JTS_LJ, 'JTS_LJ'), (JTS_ZX, 'JTS_ZX'), (JTS_CQ, 'JTS_CQ')]:
    if not (_ja <= JTS.find(_s) <= _jb):
        raise SystemExit(f'切片越出李白传区间：{_tag}——修订后重生成')
for _s, _tag in [(XTS_ZX, 'XTS_ZX'), (XTS_FH, 'XTS_FH'), (XTS_JB, 'XTS_JB'),
                 (XTS_FCZ, 'XTS_FCZ'), (XTS_WZ, 'XTS_WZ')]:
    if not (_xa <= XTS.find(_s) <= _xb):
        raise SystemExit(f'切片越出李白传区块：{_tag}——修订后重生成')
# ws 页干净断言（这首的纪律反向：无标记即不得误造标记）
for _tok in ('{{另', '{{别', '{{*'):
    if _tok in WS:
        raise SystemExit('ws 页出现计划外异文标记——先登记后重生成')

BG = {
    'bg-fr-scene': (
        '八句全诗是一场**没有名物的送别**：山横着，水绕着（「青山橫北郭，'
        '白水繞東城」——青/白、北郭/東城，工整到没有一座具体的城）；'
        '就在这里分手，他像断根的蓬草走一万里（「此地一為別，孤蓬萬里征」）；'
        '云是游子的心思，落日老朋友的脸色（「浮雲遊子意，落日故人情」）；'
        '挥手，各走，连马都不忍分别地萧萧叫着（「揮手自茲去，蕭蕭班馬鳴」——'
        '班马=离群之马，诗把最后的感情外包给牲口）。\n'
        '全诗可考之物为零：不写友人名、不写所去之地、不写何年何节——'
        '每个名词都是类别。这首的「为什么」全押在送别这个动作本身。'),
    'bg-fr-city': (
        '饯地在哪，史料不说，诗也不给：「北郭」「東城」是律诗通用对——'
        '**通用对不锚地**（audit 断言 CITY 引文不含诗语）。旧传写尽李白行迹：'
        '徂徠山、會稽、翰林、金陵采石、夜郎、宣城——唯独放还之后的总括只有一句'
        '「乃浪迹江湖，終日沉飲」：行迹是一团，没有一条拴住这场送别。\n'
        '于是这座「城」只能这样立：它存在（诗有城），不可考（两传零记载）。'
        '历代注家指安陆、指宣城、指桐江——都不在本库引证范围内。'
        '题有角色无人，诗有意象无地。'),
    'bg-fr-world': (
        '但李白年轻时有编制：旧传「少與魯中諸生孔巢父、韓沔、裴政、張叔明、'
        '陶沔等隠於徂徠山，酣歌縱酒，時號『竹溪六逸』」，新传「更客任城，'
        '與孔巢父、韓准、裴政、張叔明、陶沔居徂徠山，日沈飲，號『竹溪六逸』」——'
        '集名、徂徠山、四名同列，两源独立一致：**竹溪六逸之集升 KNOWN**。\n'
        '一处名单分歧照登不裁决：旧传作**韓沔**，新传作**韓准**——'
        '同一位置的第六人两传名字不同，各归其侧（V036 卒地分歧同款纪律，'
        'audit 互斥断言保证不串写）。开元前后的士人年轻时代就是这样的：'
        '隐居是合伙制，酒是社务；《送友人》写给的那个「友人」，'
        '最像六逸这样来来去去的人——但这是读法，史料不认领。'),
    'bg-fr-person': (
        '离开朝廷这一页，两传各写了一个版本，本库并列不裁决：'
        '旧传一句「嘗沉醉殿上，引足令高力士脫靴，**由是斥去**」——得罪史笔；'
        '新传一句「**懇求還山，帝賜金放還**」——体面史笔。同一个人离同一种生活，'
        '一说是被赶的，一说是自己走的；两说都进了正史，各归其侧（audit 互斥）。\n'
        '新传还留了两段身后的故事：元和末宣歙观察使范传正去祭他的坟、下令禁樵采；'
        '文宗时朝廷下诏，把李白的歌诗与裴旻剑舞、张旭草书并号「**三絕**」——'
        '新传单源，不升 KNOWN。全诗最大的反讽在此：他生前写给无名友人的这首送别，'
        '身后他本人成了被整个朝廷送进经典的人。'
        '死状两条线（醉死宣城/葬東麓）V036 已并列——本迁移零重开。'),
}
CLAIMS = {
    'claim-bg-fr-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页零页内标记——另/别/自注三类皆无，audit 反向断言无标记即不造标记；'
        'V018 已立异体字折叠路径）；无名词锚点为本层读法声明；'
        '班马=离群之马系题解通义非史料断言。'),
    'claim-bg-fr-city': (
        'FACT', 'LIKELY',
        '饯地不可考：「北郭/東城」通用对不锚地（CITY 引文零诗语，audit 断言）；'
        '旧传放还后行迹总括「乃浪迹江湖，終日沉飲」——行迹一团零系此别（负证正面文本）；'
        '历代注家所指不在引证范围；题有角色无人、诗有意象无地→零铸造零 relation。'),
    'claim-bg-fr-world': (
        'FACT', 'KNOWN',
        '竹溪六逸之集两源独立一致（徂徠山+集名+四名同列）→升 KNOWN；'
        '第六人名单旧「韓沔」/新「韓准」一名之异并列不裁决（V036 先例，'
        'audit 互斥断言各归其侧）；六逸与「友人」之关联系读法不外溢；'
        '诗 time.span/event.name/written_during 零铸造、零 relation。'),
    'claim-bg-fr-person': (
        'FACT', 'LIKELY',
        '去翰林因果两传分歧并列不裁决（旧「由是斥去」/新「懇求還山，帝賜金放還」，'
        'audit 互斥断言）；酒八仙人/范传正祭塚/文宗三绝均新传单得不升；'
        '死状两条线 V036 已立——本迁移零重开（audit 硬卡醉死/葬東麓零入引文）；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-fr-scene', 'source-ws-t300-323',
     '页面 送友人 (李白)（header title+author+八句全文，十段以「……」相連——'
     '页面零异文标记（Textquality 100%），无标记即不造标记；'
     '同一 (claim,source) 主键下一行容全文，V037/V039/V040 判例；'
     '全文另见 V018 claim-t300-323-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L12A, WS_L12, WS_L34A, WS_L34, WS_L56A, WS_L56, WS_L78A, WS_L78)),
    ('claim-bg-fr-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传放还后行迹句（「乃浪迹江湖，終日沉飲」——'
     '行迹总括无锚点，零系此别之负证以本句为界成立；V032 未引此半句，零重叠）',
     JTS_LJ),
    ('claim-bg-fr-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传竹溪六逸段（时号竹溪六逸/韩沔名单——'
     '两源合龙旧传侧；V032 已立此句（徂徠线），此处集名侧再证——'
     '跨迁移同句再证，claim 不同故主键不冲突）', JTS_ZX),
    ('claim-bg-fr-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传竹溪六逸段（号竹溪六逸/韩准名单——'
     '两源合龙新传侧；第六人名与旧传一异，并列不裁决各归其侧）', XTS_ZX),
    ('claim-bg-fr-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传斥去段（由是斥去——得罪侧因果；'
     'V032 已立此句前半（脱靴），此处斥去侧再证——跨迁移同句再证声明）', JTS_CQ),
    ('claim-bg-fr-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传（酒八仙人段+恳求还山段+范传正祭塚段+文宗三绝段，'
     '四段以「……」相連，同卷同传——还山体面侧/三编制/身后经典化两幕均单得；'
     '死状句不在此四段内，V036 已立零重开）',
     join(XTS_JB, XTS_FH, XTS_FCZ, XTS_WZ)),
]
BG_LINES = {'bg-fr-scene': (1, 2), 'bg-fr-city': (3, 4), 'bg-fr-world': (5, 6), 'bg-fr-person': (7, 8)}
BG_AUDIENCE = {'bg-fr-scene': 'PRIMARY', 'bg-fr-city': 'JUNIOR',
               'bg-fr-world': 'SENIOR', 'bg-fr-person': 'SENIOR'}
BG_TITLES = {'bg-fr-scene': '眼前：一场没有名物的送别',
             'bg-fr-city': '这座城：通用对不锚地',
             'bg-fr-world': '这个天下：竹溪的六人编制',
             'bg-fr-person': '这个人：被赶的还是自己走的'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 22 首·八句 2/2/2/2）；史实句均有逐字引证；'
                 'background_line 八句形制：每层两行（1-2/3-4/5-6/7-8）；'
                 '系年第十六次判决「题有角色无人，诗有意象无地」（题证系列第四状）→'
                 'time.span/event.name/written_during 全缺席、零 relation；'
                 'KNOWN 一处（竹溪六逸两源合龙）；两处分歧并列不裁决'
                 '（韩沔/韩准、斥去/还山，audit 互斥）；死状 V036 判例零重开；'
                 'ws 页零标记反向断言。' for k in BG}


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
    A("""-- V041：李白《送友人》(work-t300-323) 四层背景（阶段 D 第 22 首·八句 2/2/2/2）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-323 与其 text-work-t300-323-ws、
--       source-ws-t300-323 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——均不另开）。本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v041.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/送友人__李白_.txt（页面零异文标记——生成时反向断言）、
--   舊唐書卷190下（李白传浪迹句+竹溪六逸段+斥去段——后两段 V032 部分已立，
--   异侧再证声明入 locator）、新唐書卷202（竹溪段+酒八仙人段+还山段+身后两段；
--   切片传区间归属生成时断言）。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   6 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制：scene→1-2 city→3-4 world→5-6 person→7-8，
--   绑 text-work-t300-323-ws 的 8 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「题有角色无人，诗有意象无地」）：
--   * 受赠人=类别名「友人」零实名（连 V037 的首句消歧都没有）；饯地=通用对零锚点；
--   * 两传行迹满纸而零系此别（负证以「乃浪迹江湖」句为界正面立出）；
--   * KNOWN 一处：竹溪六逸之集两源合龙（徂徠山+集名+四名同列）；不外溢；
--   * 分歧两处并列不裁决：第六人韩沔/韩准（各归其侧）、去翰林斥去/还山（各归其侧）
--     ——audit 互斥断言双侧保证；
--   * 酒八仙人/范传正祭塚/文宗三绝均新传单得不升；
--   * 死状两条线 V036 已并列——本迁移零重开（醉死/葬東麓零入引文，audit 硬卡）；
--   * 跨迁移同句再证两处（JTS_ZX/JTS_CQ，V038 合规先例），locator 声明。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 40，不含 41
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-fr-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-323-ws';  -- 恰 8（五律）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-fr-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-323';                                  -- 8（每层两行）
--   SELECT certainty FROM poetry_claim WHERE id = 'claim-bg-fr-world';  -- KNOWN（六逸两源合龙）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-fr-scene','claim-bg-fr-city','claim-bg-fr-person');
--     -- LIKELY / LIKELY / LIKELY（person 层两分歧并列整体 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-323'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-323';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-fr-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V041_rollback.sql（按 id 全枚举删除；不动 V018/V032/V036 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-323',
              'layer': {'bg-fr-scene': 'SCENE', 'bg-fr-city': 'CITY',
                        'bg-fr-world': 'WORLD', 'bg-fr-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-323-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 41, 'Li Bai Seeing Off a Friend background layers (stage-D poem 22, 2/2/2/2): dating verdict sixteen, fourth shape of the title-evidence series -- the title names only a role (a friend, no name; not even V037-s first-line disambiguation exists) while the poem offers only generic couplets: green hills north wall, white water east gate is a regulated-verse universal pair, and a universal pair anchors no city (audit asserts zero poem-words in CITY evidence); the biographies fill every other itinerary line (Cu-lai mountain, Kuai-ji, Han-lin, Jin-ling, Ye-lang, Xuancheng) yet tie zero of them to this farewell -- the negative proof stands on the JTS summary line nai lang-ji jiang-hu (after release his tracks were one blur); one KNOWN: the Bamboo Creek Six Recluses circle, JTS yin Cu-lai shan ... shi hao Zhu-xi liu-yi plus XTS ... ju Cu-lai shan ... hao Zhu-xi liu-yi -- circle name, mountain and four members agree across two sources; the sixth member diverges (JTS Han Mian vs XTS Han Zhun) and is filed side by side, un-ruled, V036 death-place precedent, mutual-exclusion asserted in audit; second un-ruled divergence in PERSON: leaving the Han-lin academy -- JTS says driven out (you-shi chi-qu) while XTS says he begged to return to the mountains and was granted gold (ken-qiu huan-shan), each kept on its own side; Eight Immortals of Wine, Fan Chuan-zheng-s grave rites and Wenzong-s Three Perfections edict are all XTS-single, not raised; death accounts stay closed under V036 (zero re-entry asserted); two lawful cross-migration re-citations (JTS Zu-lai and boot lines from V032, different claims)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 41);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V041 精确回滚：只删 V041 插入的行（id 全枚举）。',
         '-- work-t300-323 本体、其 text_line 8 行与 source-ws-t300-323 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）与 V032/V036 的行不删；',
         '-- V041 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 41;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_L12, WS_L12A, WS_L34, WS_L34A, WS_L56, WS_L56A,
              WS_L78, WS_L78A, JTS_LJ, JTS_ZX, JTS_CQ, XTS_ZX, XTS_FH, XTS_JB, XTS_FCZ, XTS_WZ]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # ws 页干净：全 SQL 不得出现计划外标记
    for tok in ('{{另', '{{别|', '{{*|'):
        if tok in flat:
            bad.append(f'ws 页零标记迁移不得出现 {tok}')
    # 六逸两源 + 名单互斥
    w_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-fr-world' and s == 'source-jiutangshu-wenyuan')
    w_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-fr-world' and s == 'source-xintangshu-wenyi')
    if '竹溪六逸' not in w_jts or '竹溪六逸' not in w_xts:
        bad.append('竹溪六逸两源不齐')
    if '韓准' in w_jts or '韓沔' in w_xts:
        bad.append('名单分歧串侧（韩沔/韩准各归其侧被违反）')
    # 斥去/还山互斥
    p_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-fr-person' and s == 'source-jiutangshu-wenyuan')
    p_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-fr-person' and s == 'source-xintangshu-wenyi')
    if '由是斥去' not in p_jts or '放還' not in p_xts:
        bad.append('去翰林两传因果不齐')
    if '還山' in p_jts or '斥去' in p_xts:
        bad.append('去翰林分歧串侧（斥去/还山各归其侧被违反）')
    # CITY 负证：引文零诗语
    for c, s, _, ex in CITATIONS:
        if c == 'claim-bg-fr-city':
            for w in ('青山橫', '白水繞', '北郭', '東城'):
                if w in ex:
                    bad.append(f'CITY 层证据不得含诗语「{w}」（通用对不锚地）')
    if '浪迹江湖' not in ''.join(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-fr-city'):
        bad.append('CITY 层须有行迹总括句（负证正面文本）')
    # 判例只引不重开：V036 死状/V037 送别/V039 关键语零入引文
    for tok in ('醉死', '葬東麓', '下馬飲君酒', '中歲頗好道', '時年十七'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制
    if sum(len(v) for v in BG_LINES.values()) != 8 or any(len(v) != 2 for v in BG_LINES.values()):
        bad.append('八句 background_line 必须是每层恰 2 行（4 层共 8 行）')
    if len(re.findall(r"text-work-t300-323-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V041 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V041 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-323' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V041 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-323' AS subject_id" in sql:
        bad.append('V041 的 claim 主语应全部是 bg-fr-*，work-t300-323 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V041 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V041 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '题有角色无人' not in body_all or '诗有意象无地' not in body_all:
        bad.append('BG/文件头须含「题有角色无人，诗有意象无地」判决声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 18 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；ws 零标记反向断言；六逸两源+名单互斥断言；'
              f'斥去/还山互斥断言；CITY 零诗语+行迹总括断言；判例只引不重开断言'
              f'（V036/V037/V039/V040 关键语零入引文）；八句每层两行形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
