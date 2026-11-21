#!/usr/bin/env python3
"""阶段 D 第 24 首：生成 V043——王维《山居秋暝》(work-t300-134, V018 已立) 四层背景。

「为什么写」再成立一次：这首诗是**一个被两唐书认证过「天机」的人，
自己住进了天机里**——
旧传画评「書畫特臻其妙…如山水平遠，雲峯石色，**絕迹天機，非繪者之所及也**」+
新传画评「**畫思入神**，至山水準遠，雲勢石色，繪工以為**天機所到，學者不及也**」：
「山水之画到天机处他人到不了」这个鉴定，两源各自成句独立出现——
**王维画山水得天机升 KNOWN（阶段 D 首见：艺术家技能两源合龙）**。
而《山居秋暝》正是那个鉴定在诗里的对翻版：「明月松間照，清泉石上流」
「竹喧歸浣女，蓮動下漁舟」——别人画不出的那一层，他自己住进去了。

系年第十八次判决（题证系列第六状）：**「题有时刻无地点」**——
V038 题有地无年、V039 题两地无一年、V040 页有年史无年、V041 题有角色无人、
V042 诗语有地地不在传——这首反过来把**时刻**钉死（秋暝=秋天的傍晚），
地点整个松开（空山无名，诗八句零地名，两传之山唯辋川——V035/V039 已立，
本迁移不三引，边界声明）。时刻是感受的（新雨后傍晚的凉），不是历法的：
「晚來秋」是体感不是日期。零铸造零 relation。

KNOWN 两处：
① 画得天机（上）——**不外溢**：画评主语是王维画，不是这首诗；
② 知音辨乐两源——旧传「人有得奏樂圖…維視之曰：『霓裳第三疊第一拍也。』
   好事者集樂工按之，一無差」+新传「客有以《按樂圖》示者…『此《霓裳》
   第三疊最初拍也。』…引工按曲，乃信」——事体两源一致（辨图乐为霓裳第三叠、
   召乐工验证不差）升 KNOWN；**措辞分歧（第一拍/最初拍、人有得/客有以）
   各归其侧照登不裁决**（audit 互斥断言）。

判例只引不重开：奉佛（V039 KNOWN）、鳏居（V037 KNOWN）、诗名盛开天（V035 KNOWN）、
辋川段（V035/V039 已两度再证——本迁移第三次都不引）——audit 关键语零入引文硬卡。

八句 2/2/2/2；ws 页零标记反向断言（Textquality 75% 但无另/别/自注）；
异文登记零新行；零新 source（ws-134/jts/xts 三源行均已立）。

用法: python3 -I emit_v043.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/山居秋暝.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 山居秋暝', '| title    = 山居秋暝',
                         'ws header title(题钉时刻松地点:山居+秋暝)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_L12 = slice_between(WS, '空山新雨後，天氣晚來秋。', '空山新雨後，天氣晚來秋。', 'ws第1-2句联(空山新雨/晚来秋——时刻钉死、地点松开)')
WS_L34 = slice_between(WS, '明月松間照，清泉石上流。', '明月松間照，清泉石上流。', 'ws第3-4句联(明月清泉——画评山水的诗体对翻版)')
WS_L56 = slice_between(WS, '竹喧歸浣女，蓮動下漁舟。', '竹喧歸浣女，蓮動下漁舟。', 'ws第5-6句联(竹喧浣女/莲动渔舟——先声后形)')
WS_L78 = slice_between(WS, '隨意春芳歇，王孫自可留。', '隨意春芳歇，王孫自可留。', 'ws第7-8句联(春芳歇/王孙留——楚辞反用)')
JTS_HUA = slice_between(JTS, '書畫特臻其妙，筆蹤措思，參於造化，而創意經圖，即有所缺，如山水平遠，雲峯石色，絕迹天機，非繪者之所及也。',
                        '非繪者之所及也。', '旧传画评段(山水平远云峰石色绝迹天机非绘者所及——画得天机两源合龙旧传侧)')
XTS_HUA = slice_between(XTS, '畫思入神，至山水準遠，雲勢石色，繪工以為天機所到，學者不及也。',
                        '學者不及也。', '新传画评段(画思入神/天机所到/学者不及——画得天机两源合龙新传侧;要素:山水+天机+他人不及,各自成句)')
JTS_YUE = slice_between(JTS, '人有得奏樂圖，不知其名，維視之曰：「霓裳第三疊第一拍也。」好事者集樂工按之，一無差，咸服其精思。',
                        '咸服其精思。', '旧传辨乐段(奏乐图/第一拍/集乐工按之无差——辨乐两源旧传侧;「第一拍」措辞归旧侧)')
XTS_YUE = slice_between(XTS, '客有以《按樂圖》示者，無題識，維徐曰：「此《霓裳》第三疊最初拍也。」客未然，引工按曲，乃信。',
                        '乃信。', '新传辨乐段(按乐图/最初拍/引工按曲乃信——辨乐两源新传侧;「最初拍」措辞归新侧;第一拍/最初拍措辞分歧各归其侧不裁决)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=王維='), JTS.find('=李白=')
_xa, _xb = XTS.find('==王維=='), XTS.find('==鄭虔==')
for _s, _tag in [(JTS_HUA, 'JTS_HUA'), (JTS_YUE, 'JTS_YUE')]:
    if not (_ja <= JTS.find(_s) <= _jb):
        raise SystemExit(f'切片越出王维传区间：{_tag}——修订后重生成')
for _s, _tag in [(XTS_HUA, 'XTS_HUA'), (XTS_YUE, 'XTS_YUE')]:
    if not (_xa <= XTS.find(_s) <= _xb):
        raise SystemExit(f'切片越出王维传区块：{_tag}——修订后重生成')
# ws 页零标记反向断言（V041 立规）
for _tok in ('{{另', '{{别', '{{*'):
    if _tok in WS:
        raise SystemExit('ws 页出现计划外异文标记——先登记后重生成')

BG = {
    'bg-sq-scene': (
        '八句是一场感官的点名：山是空的，因为刚下过雨（「空山新雨後」——'
        '空山不是没人，是雨把杂音洗掉了）；凉是傍晚才到的秋天（「天氣晚來秋」——'
        '秋天在体感里发生，不在日历上）；月光在松树**之间**，泉声在石头上**上面**'
        '（「明月松間照，清泉石上流」——介词是这首诗的画笔画框）；'
        '先听见竹林喧闹才知道是洗衣的姑娘回来，先看见荷叶摇动才推出渔船顺流而下'
        '（「竹喧歸浣女，蓮動下漁舟」——先声后形，诗按感知的次序下笔）；'
        '春天的芳菲随它去吧，这种人本来就该留下（「隨意春芳歇，王孫自可留」——'
        '《楚辞》「王孫兮歸來」被反着用：山在留人，不是人在恋山）。\n'
        '全诗零地名——地点松开，时刻钉死。'),
    'bg-sq-city': (
        '「山居」之山无名，「秋暝」只是时刻：题给了**什么时候**，没给**哪里**；'
        '八句之内也没有一座可考的山。两传里王维明记的居所只有一处——辋川'
        '（V035 辋川线、V039 别名侧已两度逐字立证，**本迁移第三引都不做**：'
        '同句两度再证已是上限，三引即把「未指认」拖成「已指认」）。\n'
        '诗里的山可以是辋川、可以是终南、可以是任何一座雨后的山——'
        '史料一步都不陪它走。这座「城」的档案就一句话：'
        '时刻有（秋暝，还是体感的时刻），地点无——'
        '题有时刻无地点。空山的「空」由此获得一个史料学注脚：'
        '山没有名字，所以装得下所有人。'),
    'bg-sq-world': (
        '两唐书有一组罕见的**独立一致的鉴定**，主语是王维的画：\n'
        '旧传「書畫特臻其妙，筆蹤措思，參於造化……如山水平遠，雲峯石色，'
        '**絕迹天機，非繪者之所及也**」；新传「**畫思入神**，至山水準遠，'
        '雲勢石色，繪工以為**天機所到，學者不及也**」——两源各自成句，'
        '要素对榫（山水之远景/云峰石色/天机之境/他人到不了）：'
        '**王维画山水得天机升 KNOWN**（阶段 D 首见艺术家技能的合龙）。\n'
        '于是开天边地的文化市场上，王维的名字同时挂着两种通货：诗名（V035 已判 KNOWN，'
        '此处只引不重开）与画品（本层新判）。而《山居秋暝》恰好是画评的诗体翻版——'
        '「山水平遠，雲峯石色」与「明月松間照，清泉石上流」共享同一种取景法。'
        '但**画评主语是画不是诗**：KNOWN 不外溢给这首《山居秋暝》——审计与账本双声明。'),
    'bg-sq-person': (
        '传里给王维留了一则两源都收的轶事，主语是他的耳朵：'
        '旧传有人拿来一幅奏乐图，王维看了一眼：「**霓裳第三疊第一拍**也」，'
        '好事者把乐工召来对着弹，「一無差，咸服其精思」；'
        '新传同一幕：客出《按樂圖》，维曰「此《霓裳》第三疊**最初拍**也」，'
        '客不信，引工按曲，「乃信」——**事体两源一致升 KNOWN**'
        '（辨图乐为霓裳第三叠+召乐工验证不差）；\n'
        '**措辞分歧照登不裁决**：「第一拍」／「最初拍」、「人有得奏樂圖」／'
        '「客有以《按樂圖》示者」——各归其侧（audit 互斥断言保证不串写），'
        '这与辋川段「裴廸/裴迪」（V035）、竹溪「韓沔/韓准」（V041）同一谱系。\n'
        '鳏居（V037）、奉佛（V039）两条 KNOWN 判例本迁移零重开——'
        '传里那个孤居一室的人，在这首诗里只留下「王孫自可留」五个字的背影。'),
}
CLAIMS = {
    'claim-bg-sq-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页零页内标记——另/别/自注三类皆无，audit 反向断言；'
        'Textquality 75% 与零标记并存如实记）；先声后形/体感之秋为本层读法声明；'
        '王孙=楚辞反用系题解通义非史料断言。'),
    'claim-bg-sq-city': (
        'FACT', 'LIKELY',
        '题钉时刻（秋暝）松地点（山居无名）；八句零地名（负证=CITY 引文只有题与署名，'
        'audit 断言引文零山名水名）；两传之山唯辋川且 V035/V039 已两度立证——'
        '本迁移不三引（边界声明）；题有时刻无地点→零铸造零 relation。'),
    'claim-bg-sq-world': (
        'FACT', 'KNOWN',
        '王维画山水得天机两源独立一致：旧传「如山水平遠…絕迹天機，非繪者之所及」+新传'
        '「天機所到，學者不及」要素对榫各成句→升 KNOWN；主语是画评不是此诗，不外溢；'
        '诗名段 V035 已判 KNOWN 只引不重开；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-sq-person': (
        'FACT', 'KNOWN',
        '辨乐轶事事体两源一致（辨图乐为霓裳第三叠+召乐工验证不差）→升 KNOWN；'
        '措辞分歧（第一拍/最初拍、人有得/客有以）各归其侧不裁决（audit 互斥）；'
        '鳏居 V037/奉佛 V039 判例零重开（audit 关键语硬卡）；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-sq-scene', 'source-ws-t300-134',
     '页面 山居秋暝（header title+author+八句四联，六段以「……」相連——'
     '页面零异文标记（Textquality 75% 但另/别/自注三类皆无），无标记即不造标记；'
     '同一 (claim,source) 主键下一行容全文，V037/V039/V040/V041/V042 判例；'
     '全文另见 V018 claim-t300-134-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78)),
    ('claim-bg-sq-city', 'source-ws-t300-134',
     '页面 山居秋暝（header title+author 两字段——负证的引文形态：只题与署名，'
     '八句诗身另在 SCENE 层，此层证据不含任何山名水名；'
     '两传辋川段 V035/V039 已两度逐字立证，本迁移不三引——边界声明）',
     join(WS_TITLE, WS_AUTHOR)),
    ('claim-bg-sq-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传画评段（绝迹天机/非绘者所及——两源合龙旧传侧逐字；'
     '主语是画，不外溢到此诗）', JTS_HUA),
    ('claim-bg-sq-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传画评段（画思入神/天机所到/学者不及——两源合龙新传侧逐字）',
     XTS_HUA),
    ('claim-bg-sq-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传辨乐段（奏乐图/霓裳第三叠第一拍/集乐工按之一无差——'
     '事体两源旧传侧；「第一拍」措辞归旧侧）', JTS_YUE),
    ('claim-bg-sq-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传辨乐段（按乐图/霓裳第三叠最初拍/引工按曲乃信——'
     '事体两源新传侧；「最初拍」措辞归新侧，与旧侧各归其侧不裁决）', XTS_YUE),
]
BG_LINES = {'bg-sq-scene': (1, 2), 'bg-sq-city': (3, 4), 'bg-sq-world': (5, 6), 'bg-sq-person': (7, 8)}
BG_AUDIENCE = {'bg-sq-scene': 'PRIMARY', 'bg-sq-city': 'JUNIOR',
               'bg-sq-world': 'SENIOR', 'bg-sq-person': 'SENIOR'}
BG_TITLES = {'bg-sq-scene': '眼前：按感知的次序下笔',
             'bg-sq-city': '这座城：山没有名字',
             'bg-sq-world': '这个天下：两种通货',
             'bg-sq-person': '这个人：传里留了他的耳朵'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 24 首·八句 2/2/2/2）；史实句均有逐字引证；'
                 'background_line 八句形制：每层两行（1-2/3-4/5-6/7-8）；'
                 '系年第十八次判决「题有时刻无地点」（题证系列第六状）→time.span/'
                 'event.name/written_during 全缺席、零 relation；'
                 'KNOWN 两处（画得天机两源合龙——阶段 D 首见艺术家技能合龙；'
                 '辨乐事体两源一致）；措辞分歧各归其侧不裁决（第一拍/最初拍，audit 互斥）；'
                 '辋川段两度已立本迁移不三引；奉佛/鳏居/诗名判例只引不重开。' for k in BG}


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
    A("""-- V043：王维《山居秋暝》(work-t300-134) 四层背景（阶段 D 第 24 首·八句 2/2/2/2）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-134 与其 text-work-t300-134-ws、
--       source-ws-t300-134 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——均不另开）。本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v043.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/山居秋暝.txt（页面零异文标记——反向断言）、
--   舊唐書卷190下（画评段+辨乐段）、新唐書卷202（画评段+辨乐段）——
--   四段切片传区间归属生成时断言。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   6 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制：scene→1-2 city→3-4 world→5-6 person→7-8，
--   绑 text-work-t300-134-ws 的 8 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「题有时刻无地点」）：
--   * 时刻钉死（秋暝）但为体感时刻非历法时刻；地点整个松开（题与八句零地名）；
--   * 两传之山唯辋川，V035/V039 已两度逐字立证——**同句两度为上限，本迁移不三引**；
--   * KNOWN 两处：①画得天机（画评两源合龙，阶段 D 首见艺术家技能合龙）——
--     主语是画不是诗，不外溢；②辨乐事体两源一致——措辞分歧
--     （第一拍/最初拍、人有得/客有以）各归其侧不裁决（audit 互斥）；
--   * 诗名（V035）/奉佛（V039）/鳏居（V037）判例只引不重开（audit 关键语硬卡）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 42，不含 43
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-sq-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-134-ws';  -- 恰 8（五律）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-sq-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-134';                                  -- 8（每层两行）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-sq-world','claim-bg-sq-person');
--     -- KNOWN / KNOWN（world=画得天机两源；person=辨乐事体两源）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-sq-scene','claim-bg-sq-city');
--     -- LIKELY / LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-134'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-134';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-sq-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V043_rollback.sql（按 id 全枚举删除；不动 V018/V035/V039 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-134',
              'layer': {'bg-sq-scene': 'SCENE', 'bg-sq-city': 'CITY',
                        'bg-sq-world': 'WORLD', 'bg-sq-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-134-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 43, 'Wang Wei Mountain Dwelling Autumn Dusk background layers (stage-D poem 24, 2/2/2/2): dating verdict eighteen, sixth shape of the title-evidence series -- the title pins the moment (autumn dusk, and a bodily one: autumn arrives in the body feeling, not on the calendar) while place opens wide: no mountain-name in title or eight lines, the only recorded hill in both biographies is Wang-chuan already quoted verbatim twice (V035 the Wang-chuan line, V039 the alias side) and this migration refuses a third citation -- two re-citations of one line is the ceiling, a third would drag the unclaimed into the claimed; two KNOWNs: (1) his landscape painting reaches tian-ji -- JTS jue-ji tian-ji fei hui-zhe suo-ji plus XTS tian-ji suo-dao xue-zhe bu-ji, element-for-element across independent wordings, the stage-D first two-source agreement on an artistic skill, strictly about the paintings and never overflowing to this poem; (2) the music-score anecdote as a fact agrees across both histories (identifies the score as the third die of Rainbow-Feather, musicians summoned confirm) while the wording diverges (di-yi-pai vs zui-chu-pai; a person obtained vs a guest presented) -- each kept on its own side, un-ruled, mutual-exclusion asserted, same family as the Pei-di variant (V035) and Han-Mian/Han-Zhun (V041); the fame/poverty-piety/widower lines stay closed precedents (audit keyword zero-entry); zero new sources'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 43);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V043 精确回滚：只删 V043 插入的行（id 全枚举）。',
         '-- work-t300-134 本体、其 text_line 8 行与 source-ws-t300-134 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）与 V035/V039 的行不删；',
         '-- V043 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 43;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78,
              JTS_HUA, XTS_HUA, JTS_YUE, XTS_YUE]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # ws 零标记反向断言
    ws_ex = ''.join(ex for _, s, _, ex in CITATIONS if s == 'source-ws-t300-134')
    for tok in ('{{另', '{{别|', '{{*|'):
        if tok in ws_ex:
            bad.append(f'ws 零标记迁移的 ws 引文不得含 {tok}')
    # 画得天机两源断言
    h_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-sq-world' and s == 'source-jiutangshu-wenyuan')
    h_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-sq-world' and s == 'source-xintangshu-wenyi')
    if '天機' not in h_jts or '天機' not in h_xts or '山水' not in h_jts or '山水' not in h_xts:
        bad.append('画得天机两源不齐（天机+山水须各侧在场）')
    # 辨乐两源 + 措辞互斥
    y_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-sq-person' and s == 'source-jiutangshu-wenyuan')
    y_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-sq-person' and s == 'source-xintangshu-wenyi')
    if '霓裳' not in y_jts or '霓裳' not in y_xts:
        bad.append('辨乐两源不齐（霓裳须两侧在场）')
    if '最初拍' in y_jts:
        bad.append('辨乐措辞串侧（最初拍不得入旧传侧）')
    if re.search(r'(?<!最)第一拍', y_xts):
        bad.append('辨乐措辞串侧（独立的第一拍不得入新传侧）')
    # CITY 负证：引文零山名水名
    for c, s, _, ex in CITATIONS:
        if c == 'claim-bg-sq-city':
            for w in ('明月', '清泉', '竹喧', '蓮動', '松', '石上'):
                if w in ex:
                    bad.append(f'CITY 层证据不得含诗语「{w}」（山无名=负证，不代拟进引文）')
    # 判例只引不重开（V035/V037/V039/V041 关键语）
    for tok in ('得宋之問藍田别墅', '妻亡不再娶', '蔬食', '篤志奉佛', '竹溪六逸',
                '開元、天寶間，同知名者', '以詩名盛於'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制
    if sum(len(v) for v in BG_LINES.values()) != 8 or any(len(v) != 2 for v in BG_LINES.values()):
        bad.append('八句 background_line 必须是每层恰 2 行（4 层共 8 行）')
    if len(re.findall(r"text-work-t300-134-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V043 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V043 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-134' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V043 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-134' AS subject_id" in sql:
        bad.append('V043 的 claim 主语应全部是 bg-sq-*，work-t300-134 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V043 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V043 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '题有时刻无地点' not in body_all:
        bad.append('BG/文件头须含「题有时刻无地点」判决声明')
    if '不三引' not in body_all:
        bad.append('BG/文件头须含「辋川段不三引」边界声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 10 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；ws 零标记反向断言；画得天机两源断言；'
              f'辨乐事体两源+措辞互斥断言（第一拍/最初拍各归其侧）；CITY 零诗语断言；'
              f'判例只引不重开断言（辋川/鳏居/奉佛/诗名/竹溪关键语零入引文）；'
              f'不三引边界声明断言；八句每层两行形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
