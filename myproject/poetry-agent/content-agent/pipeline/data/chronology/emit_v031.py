#!/usr/bin/env python3
"""阶段 D 第 12 首：生成 V031——孟浩然《歲暮歸南山》(work-t300-119, V018 已立) 四层背景。

「为什么写」的形状第四次成立，而且换了个前所未有的证据类型：**本传直接引这首诗的句子**。
新唐书写玄宗掌故，把「不-{才}-明主棄」原句嵌进帝王的反问里——
「帝問其詩，浩然再拜，自誦所爲，至『不才明主棄』之句，帝曰：『卿不求仕，而朕未嘗棄卿，
奈何誣我？』因放還」——全库第一次，诗的一行本身就是史料里的因果物证。
旧传更短但把整条弧写全：「隠鹿門山，以詩自適。年四十來遊京師，應進士不第，還」——
隐→四十入京→不第→归，题目「歲暮歸南山」就是这条弧的终点站。

系年第六次判决：**全缺席，缺席原因是「史料有年龄没有年」**——两传都只说「年四十」，
生年本地核不到，四十岁换算不成公元年；徐松年谱说开元十六年（728）下第，本地无此记载不采信。
time.span / event.name / written_during 全部缺席 + 零 relation（V027/V028/V029 形状断言）。

两传对「怎么离开长安」各说一套，逐字并列不裁决：旧传「應進士不第，還」（考试失败），
新传「因放還」（明皇掌故）——两传都不提对方那一套，这是本库第一个「同一个人同一件事、
两传叙事线整体不同」的案子（V029 是三源两说同一件事的细节差）。
KNOWN 只给两传一致处：隱鹿門山（两传逐字同句）、年四十游京师、张九齡鎮荆州辟從事。

ws 诗页有四个页内异文 + 题目两条自注（異文登记先行：corpus/tang300-variants.md
「歲暮歸南山 119」行，2026-11-20）——本诗是阶段 D 第一首**正文带页内异文**的诗
（登樓的异文在 V018 双证路径已处理，这四是 V018 ws 路线首读入库后第一次原样引异文进背景引文，
同 V024 登樓 SCENE 判例：页内异文原样引，只登记不裁决）。
南山两读（襄阳南山 vs 题目自注「一作歸終南山」）不裁决——城市层就写在这座歧义上。

用法: python3 -I emit_v031.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/歲暮歸南山.txt').read_text(encoding='utf-8')
V160 = pathlib.Path('/tmp/src-dl/quantangshi/vol160.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
# ws 侧全部按**原始 wikitext** 切（含 {{另}}/{{*|}} 标记）——引文原样照登，同 V024 登樓判例
WS_L12 = slice_between(WS, '北闕休上書，南山歸敝廬。', '南山歸敝廬。', 'ws首联(休书/归庐)')
WS_L34 = slice_between(WS, '不才明主棄，{{另|多|臥}}病故人疎。', '病故人疎。',
                       'ws二联(明主弃——页内异文 多/臥 原样)')
WS_L56 = slice_between(WS, '白髮催年{{另|老|去}}，青陽逼歲除。', '青陽逼歲除。',
                       'ws三联(催年——页内异文 老/去 原样)')
WS_L78 = slice_between(WS, '永懷愁不{{另|寐|寢}}，松月夜{{另|窗|堂}}虛。', '松月夜{{另|窗|堂}}虛。',
                       'ws尾联(愁不寐——页内异文 寐/寢、窗/堂 原样)')
WS_HDR = slice_between(WS, '| title    = 歲暮歸南山{{*|一題作歸故園作，一作歸終南山}}\n| section  = \n| author   = 孟浩然',
                       '| author   = 孟浩然', 'ws header title(题目自注两条)+author')
V160_NOTE = slice_between(V160, "'''孟浩然'''", "'''孟浩然'''", 'vol160 卷首作者注')
V160_ANCHOR = slice_between(V160, '==[[歲暮歸南山]]==', '{{:歲暮歸南山}}', 'vol160 锚点+转引用桩')
JTS_BIO = slice_between(JTS, '孟浩然，隠鹿門山，以詩自適。年四十來遊京師，應進士不第，還。襄陽張九齡鎮荆州，署為從事，與之唱和，不逹而卒。',
                        '不逹而卒。', '旧传本传全文(隐鹿门/年四十/进士不第/张九龄从事/不达而卒)')
JTS_NAME = slice_between(JTS, '開元、天寳間，文士知名者，汴州崔顥，京兆王昌齡、高適，㐮陽孟浩然，皆名位不振，唯高適官逹，自有傳。',
                         '唯高適官逹，自有傳。', '旧传文苑总叙(名位不振)')
XTS_HEAD = slice_between(XTS, '孟浩然，字浩然，襄州襄陽人。', '襄州襄陽人。', '新传首句(襄阳人)')
XTS_LU = slice_between(XTS, '少好節義，喜振人患難，隱鹿門山。', '隱鹿門山。', '新传隐鹿门段')
XTS_S40 = slice_between(XTS, '年四十，乃-{游}-京師。嘗-{於}-太學賦詩，一座嗟伏，無敢抗。',
                        '無敢抗。', '新传年四十游京师段(-{游}- 转换标记原样)')
XTS_SHI = slice_between(XTS, '帝問其詩，浩然再拜，自誦所爲，至「不-{才}-明主棄」之句，帝曰：「卿不求仕，而朕未嘗棄卿，奈何誣我？」因放還。',
                        '因放還。', '新传明皇掌故(全库首次：本传原句引本诗)')
XTS_HAN = slice_between(XTS, '會故人至，劇飲歡甚，或曰：「君與韓公有期。」浩然叱曰：「業已飲，遑恤他！」卒不赴。朝宗怒，辭行，浩然不悔也。',
                        '浩然不悔也。', '新传韩朝宗爽约段')
XTS_END = slice_between(XTS, '張九齡爲荊州，-{辟}-置-{於}-府，府罷。開元末，病疽背卒。',
                        '病疽背卒。', '新传荆州幕罢+病疽背卒段')

BG = {
    'bg-sm-scene': (
        '这首诗的开头是一个转身：「北闕休上書，南山歸敝廬。」——宫门前那条上书求官的路，'
        '到此算了；转身回南山的老屋去。题目「歲暮歸南山」把这一步写得明明白白：'
        '岁末、归、南山——不是游历不是送别，是回身。\n'
        '他为什么转身：两本旧史的本传给了整条弧——旧唐书「隠鹿門山，以詩自適。'
        '年四十來遊京師，應進士不第，還」（旧唐书卷一百九十下文苑下），'
        '新唐书说他四十岁入京，太学赋诗一座叹服，最后一句「因放還」（新唐书卷二百零二文艺下）。'
        '「休上書」三个字后面站着的就是这条走完了的路。'),
    'bg-sm-city': (
        '诗题里的「南山」有两个读法，本库不裁决：维基文库诗页题目自注'
        '「一題作歸故園作，一作歸終南山」——归故园，襄阳的南山；归终南山，长安的南山。'
        '两个读法把这首诗放进两座城，诗本身不分说。\n'
        '襄阳这头有据：新传「孟浩然，字浩然，襄州襄陽人」，两传同记「隱鹿門山」'
        '（新传此三字在「少好節義，喜振人患難」之后）。长安那头也有据：'
        '「北闕」是长安的宫门，「明主」是长安的主上，年四十游京师也在长安。\n'
        '二联「不才明主棄，多病故人疎」正悬在两城之间：明主在长安，'
        '离开的故人——新传记他连韩朝宗的荐书都爽了：「卒不赴。朝宗怒，辭行，浩然不悔也」。\n'
        '（正文四句引的是维基文库诗页原文，页内 {{另}} 异文照登不裁决——'
        '「多病」页内又出「臥病」，登记在 corpus/tang300-variants.md。）'),
    'bg-sm-world': (
        '三联「白髮催年{{另|老|去}}，青陽逼歲除」——白发催人来、新年逼着旧年除，'
        '这个催逼是实的：两传都记他**年四十**才入京求仕（旧传「年四十來遊京師」，'
        '新传「年四十，乃-{游}-京師」）——在唐人里这是晚得不能再晚的出发。\n'
        '他走进的是一个考进士的时代。旧传记结局五个字：「應進士不第，還」。\n'
        '新传给的是另一条线：玄宗问他诗，他背到自己那句「不才明主棄」，'
        '帝曰「卿不求仕，而朕未嘗棄卿，奈何誣我？」因放還——被放还，不是落第。\n'
        '**两传叙事线整体不同，逐字并列不裁决**（这是库里第一例：同一个人同一件事，'
        '旧传只说不第、新传只说明皇掌故，互不提及）。年谱说此事在开元十六年（728）——'
        '本地两史通鉴都无年份，通鉴通篇无孟浩然，核不到不采信：这首诗不铸 time.span，'
        '「年四十」换算不成公元年（生年核不到）。'),
    'bg-sm-person': (
        '这个人的传记第一次做了一件事：**本传原句引了他正在被讨论的这首诗**。'
        '新唐书玄宗掌故里那句「不-{才}-明主棄」就是本集这一首的二联出句——'
        '诗行本身成了史料里的物证，「为什么写」和「写后发生了什么」在同一个句子会合。\n'
        '他的一生两史给得很齐：隐居鹿门（两传逐字同句「隱鹿門山」）、年四十游京师、'
        '张九齡鎮荆州辟为从事（旧传「署為從事，與之唱和」、新传「-{辟}-置-{於}-府，府罷」）、'
        '终于不仕——旧传「不逹而卒」，新传多两个字「開元末，病疽背卒」，死状只新传有，并列。\n'
        '新传还有两笔活的：太学赋诗「無敢抗」；韩朝宗约他入京荐举，故人来了他一句'
        '「業已飲，遑恤他！」卒不赴——朝宗怒辞行，他「不悔也」。'
        '新传末尾王维为他画像的孟亭一段在附传区，本层不取。\n'
        '名声旧传有总叙：「開元、天寳間，文士知名者，汴州崔顥，京兆王昌齡、高適，'
        '㐮陽孟浩然，皆名位不振」——四个大诗人三个困顿，「名位不振」是史家给的判词。\n'
        '全唐詩卷一百六十为整卷收他的诗，卷首 Collection header notes 标作者「孟浩然」；'
        '本诗在卷内只是锚点+转引用桩，正文在维基文库诗页。'),
}
CLAIMS = {
    'claim-bg-sm-scene': (
        'FACT', 'LIKELY',
        '题目+首联内证（休书/归庐）支撑转身动作；整条弧（隐→四十入京→归）由两史本传逐字支撑；'
        '离京原因两传异线见 world 层，本 claim 不采任何一线为唯一。'),
    'claim-bg-sm-city': (
        'FACT', 'LIKELY',
        '南山两读（故园/终南）为诗页题目自注原样，不裁决；襄阳人+隐鹿门两史逐字；'
        '韩朝宗爽约为新传逐字；页内异文照登（登记先行于 corpus/tang300-variants.md）。'),
    'claim-bg-sm-world': (
        'FACT', 'LIKELY',
        '年四十两传逐字（新传含 -{游}- 转换标记原样）；旧传「應進士不第，還」与新传'
        '明皇掌故「因放還」两线并列不裁决；年谱开元十六年本地核不到不采信；'
        '不铸 time.span、不挂 event、零 relation。'),
    'claim-bg-sm-person': (
        'FACT', 'KNOWN',
        '隐鹿门山（两传逐字同句）、年四十游京师、张九齡镇荆州辟从事——两史一致处升 KNOWN；'
        '死状「病疽背卒」只新传有、离京原因两传异线——均并列不升；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-sm-scene', 'source-ws-t300-119',
     '页面 歲暮歸南山（首联逐字；本诗正文的页内异文登记先行于 corpus/tang300-variants.md '
     '「歲暮歸南山 119」行——首联无页内异文，页内实测 {{另}} 只在二三四联；全文另见 V018 '
     'claim-t300-119-text 引文）', WS_L12),
    ('claim-bg-sm-city', 'source-ws-t300-119',
     '页面 歲暮歸南山（header title+author 字段逐字——题目自注两条即南山两读之证；'
     '+二联逐字，页内异文 {{另|多|臥}} 原样照登不裁决，V024 登樓判例）',
     join(WS_HDR, WS_L34)),
    ('claim-bg-sm-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·孟浩然（本传全文——隐鹿門山三字与新传逐字同）', JTS_BIO),
    ('claim-bg-sm-city', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·孟浩然传（首句襄阳人+隐鹿门段，两段以「……」相連）',
     join(XTS_HEAD, XTS_LU)),
    ('claim-bg-sm-world', 'source-ws-t300-119',
     '页面 歲暮歸南山（三联+尾联逐字以「……」相連，页内 {{另|老|去}}/{{另|寐|寢}}/'
     '{{另|窗|堂}} 三组原样照登不裁决）', join(WS_L56, WS_L78)),
    ('claim-bg-sm-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·孟浩然（「年四十來遊京師，應進士不第，還」——两传异线的旧传侧）',
     JTS_BIO),
    ('claim-bg-sm-world', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·孟浩然传（年四十段+明皇掌故段+韩朝宗段，三段以「……」相連——'
     '「因放還」与旧传「不第」异线的新传侧；明皇掌故为本传原句引本诗处，'
     '「不-{才}-明主棄」含繁简转换标记逐字照登）', join(XTS_S40, XTS_SHI, XTS_HAN)),
    ('claim-bg-sm-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下（本传全文＋文苑总叙「名位不振」句，两段以「……」相連）',
     join(JTS_BIO, JTS_NAME)),
    ('claim-bg-sm-person', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·孟浩然传（首句+隐鹿门段+明皇掌故段+韩朝宗段+荆州幕罢病疽段；'
     '五段以「……」相連，出处同卷同传；明皇掌故句为**本传原句引本诗**——全库首例）',
     join(XTS_HEAD, XTS_LU, XTS_SHI, XTS_HAN, XTS_END)),
    ('claim-bg-sm-person', 'source-quantangshi-160',
     '页面 全唐詩/卷160（卷首作者注＋本诗锚点与转引用桩 {{:歲暮歸南山}}；'
     '卷页无正文，正文证据在诗页；同 V022/V025–V029 桩教训）',
     join(V160_NOTE, V160_ANCHOR)),
]
BG_LINES = {'bg-sm-scene': (1, 2), 'bg-sm-city': (3, 4),
            'bg-sm-world': (5, 6), 'bg-sm-person': (7, 8)}
BG_AUDIENCE = {'bg-sm-scene': 'PRIMARY', 'bg-sm-city': 'JUNIOR',
               'bg-sm-world': 'SENIOR', 'bg-sm-person': 'SENIOR'}
BG_TITLES = {'bg-sm-scene': '眼前：上书的路到此为止',
             'bg-sm-city': '两座城：南山有两个读法',
             'bg-sm-world': '这个天下：年四十的出发与两条离京线',
             'bg-sm-person': '这个人：传记引了他的诗'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 12 首）；史实句均有逐字引证；'
                 '「应进士不第」与明皇掌故两传异线并列不裁决；系年缺席（年四十核不成公元年）；'
                 '正文页内异文四组先登记后原样引（corpus/tang300-variants.md）。' for k in BG}


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
    A("""-- V031：孟浩然《歲暮歸南山》(work-t300-119) 四层背景（阶段 D 第 12 首）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-119 与其 text-work-t300-119-ws、
--       source-ws-t300-119 都是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——本迁移首次用到 卷190下/卷203 的引文，来源行 V016 已登记，不另开行）。
--
-- 数据源（可复现）：emit_v031.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/歲暮歸南山.txt（**原始 wikitext 原样引用**——含 {{另}} 页内异文与 {{*|}} 题目自注，
--   V024 登樓判例：页内异文原样引，只登记不裁决；异文登记先行于 corpus/tang300-variants.md）、
--   全唐詩/卷160（卷首注+锚点+转引用桩）、舊唐書卷190下、新唐書卷203。
--
-- 做：1 个新 source 登记（全唐詩卷160，PENDING——登记不等于核验）+
--   4 BACKGROUND content/claim/background + 10 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，绑 text-work-t300-119-ws）。
--   本迁移**不碰 poetry_text_line**（119 的 8 行 V018 落得正确；291 的修复在 V030 单独完成）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「史料有年龄没有年」）：
--   * 两传只说「年四十」，生年本地核不到→公元年换算不出来；年谱开元十六年(728)说
--     本地无记载不采信；通鉴通篇无孟浩然——time.span/event.name/written_during 一个都不造
--     （V023/V024/V027 形状断言 + V028 零 relation 断言）；
--   * 离京两传**叙事线整体不同**（旧传「應進士不第，還」vs 新传明皇掌故「因放還」，互不提及）——
--     库里首例两传异线，逐字并列不裁决，任何一层都不合并成第三条故事；
--   * 死状「病疽背卒」只新传有、籍贯襄阳两传同——不一致处不升 KNOWN；
--   * 南山两读（故园襄阳/终南长安）为题目自注原样，城市层写在歧义上、不裁决；
--   * 页内异文四组（多/臥、老/去、寐/寢、窗/堂）：登记先行（variants.md 119 行），
--     引文取原始 wikitext 照登——阶段 D 第一首正文带页内异文的背景迁移。
--
-- 干支对账：本迁移无通鉴年标题、无干支断言（audit 检查4 无涉）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 30，不含 31
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-sm-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-119-ws';  -- 恰 8（无需修复）
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-160';     -- 空
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-sm-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-119';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-sm-person';   -- KNOWN
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-119'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-119';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-sm-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V031_rollback.sql（按 id 全枚举删除；不动 V018 的行，
--   不动共用两唐书/ws 来源行）
START TRANSACTION;""")

    A('\n-- ---------- 1. 来源登记（一律 PENDING：登记不等于核验） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-160',
              'title': '《全唐詩》全唐詩/卷160（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷160（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷160',
              'rights_note': '维基文库录入本，公有领域古籍。本卷为孟浩然诗卷，卷首 Collection header '
                             "notes 标作者 '''孟浩然'''。本诗条目只有锚点+转引用桩，正文在诗页。"
                             '本行由 emit_v031.py 对快照逐字定位。核验状态保持 PENDING。',
              'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
              'reliability': 'HIGH'}],
            'x.id = t.id'))

    A('\n-- ---------- 2. BACKGROUND content identities ----------')
    rows = [{'id': k, 'entity_type': 'BACKGROUND', 'slug': k[3:], 'title': BG_TITLES[k],
             'summary': BG_SUMMARY[k], 'time_precision': 'UNKNOWN'} for k in BG]
    A(guard('poetry_content', ['id', 'entity_type', 'slug', 'title', 'summary', 'time_precision'],
            rows, 'x.id = t.id'))

    A('\n-- ---------- 3. claims（主语=BACKGROUND content 行；claim id 带 claim- 前缀，V004 同款） ----------')
    crows = [{'id': k, 'subject_id': k.replace('claim-', '', 1), 'property_key': 'context',
              'value_text': v[2], 'claim_kind': v[0], 'certainty': v[1]} for k, v in CLAIMS.items()]
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            crows, 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': k.replace('claim-', '', 1), 'property_key': 'context', 'claim_id': k}
             for k in CLAIMS],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    A('\n-- ---------- 4. background rows ----------')
    brows = [{'id': k, 'work_id': 'work-t300-119',
              'layer': {'bg-sm-scene': 'SCENE', 'bg-sm-city': 'CITY',
                        'bg-sm-world': 'WORLD', 'bg-sm-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': 'claim-' + k} for k in BG]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 5. 逐字引文（(claim,source) 主键每对恰一行） ----------')
    L.append('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(c)} AS claim_id, {sql_s(s)} AS source_id, {sql_s(loc)} AS locator, "
        f"{sql_s(ex)} AS evidence_excerpt FROM DUAL"
        for c, s, loc, ex in CITATIONS))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
             'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 6. background_line ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-119-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 31, 'Meng Haoran Sui-mu gui Nan-shan background layers (stage-D poem 12): the biography-quote shape appears for the first time -- the Xin Tang-shu Xuan-zong anecdote quotes this very poem-line bu-cai-ming-zhu-qi inside the emperor-s rebuttal, so the poem line itself is the causal artifact in the source; dating absent for a new sixth reason -- both biographies give only age forty, birth year cannot be verified locally so the age never converts to an era year, the Tongjian never mentions Meng, chronology-s 728 claim not adopted; for the first time the two standard histories tell two whole different exit stories (JTS: sat the jinshi exam and failed; XTS: offended the emperor and was released home) -- registered verbatim side by side, no merge; four page-internal variants of the poem page registered first in corpus/tang300-variants.md then quoted raw from wikitext (V024 precedent); Nan-shan place-ambiguity (home-hill vs Zhong-nan-shan per title note) left unadjudicated'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 31);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V031 精确回滚：只删 V031 插入的行（id 全枚举）。',
         '-- work-t300-119 本体、其 text_line 8 行与 source-ws-t300-119 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）不删；V031 零 poetry_relation 行。',
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
    dels('poetry_source', 'id', ['source-quantangshi-160'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 31;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_L12, WS_L34, WS_L56, WS_L78, WS_HDR, V160_NOTE, V160_ANCHOR,
              JTS_BIO, JTS_NAME, XTS_HEAD, XTS_LU, XTS_S40, XTS_SHI, XTS_HAN, XTS_END):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # {{另}} 标记必须原样在场（防止任何环节悄悄折叠）
    for mark in ('{{另|多|臥}}', '{{另|老|去}}', '{{另|寐|寢}}', '{{另|窗|堂}}',
                 '{{*|一題作歸故園作，一作歸終南山}}', '不-{才}-明主棄'):
        if mark not in flat:
            bad.append(f'页内标记未原样进入 SQL: {mark}')
    # poetry_citation 主键 (claim_id, source_id)：本文件内每对恰出现一次
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    # 缺席断言（V023/V024/V027/V028/V029 同款）
    if "'written_during' AS predicate" in sql:
        bad.append("V031 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V031 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-119' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V031 有意不给诗铸 {pk}，但该主语组合出现了')
    if 'text-work-t300-119-ws' in build_rollback():
        bad.append('回滚不得触碰 119 的 text_line（V018 的行，本迁移没改过它们）')
    if "DELETE FROM poetry_text_line" in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V031 不碰 poetry_text_line（119 无需修复；291 的修复在 V030）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 15 切片逐字过审，'
              f'页内异文/转换标记原样在场；(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言；text_line 未被触碰已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
