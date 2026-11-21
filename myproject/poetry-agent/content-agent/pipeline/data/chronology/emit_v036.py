#!/usr/bin/env python3
"""阶段 D 第 17 首：生成 V036——李白《玉階怨》(work-t300-308, V018 已立) 四层背景。

「为什么写」第九次成立，这次本传给的是**一段两源合龙的创作语境**：《玉階怨》是乐府旧题，
而两唐书各自记了同一场皇帝催乐词的场景——旧传「玄宗度曲，欲造樂府新詞，亟召白…
以水灑面，即令秉筆，頃之成十餘章」，新传「帝坐沈香亭子…欲得白為樂章…以水靧面，
稍解，援筆成文，婉麗精切無留思」——同一个故事的两个独立讲法（醉/召/洒水/立就四要素全同），
KNOWN 升这一处；贺知章「謫仙人」之赏也是两传各自在场（旧传「此天上謫仙人也」/
新传「子，謫仙人也！」），再升一处。

系年第十一次判决：**「乐府题不纪行旅 + 创作语境只有『天寶初』的模糊时代标签」**。
比 V034（726 事件年硬而到不了诗）更软一层：这里连事件本身两传都只给「天寶初」——
没有年标题级坐标，不做年表式演算。time.span/event.name/written_during 零铸造 + 零 relation。

两传分歧登记（新素材型）：**卒地两传各自说法**——旧传「竟以飲酒過度，醉死於宣城」，
新传「悅謝家青山，欲終焉。及卒，葬東麓」（当涂青山）。不裁决、并列照登，
audit 断言两处都在且只进同一 claim 的并列陈述（分歧不许被单源独吞）。

V032（同诗人《登金陵鳳凰臺》）已用过的传文切片全部避开：翰林荐举/脱靴/永王/流放/
崔宗之采石等一概不重复——本首只取 V032 未碰的四段（樂府新詞段/天寶初段/謫仙人段/卒段）。

绝句第二例：background_line 每层一行（scene→1 city→2 world→3 person→4），audit 加形制断言。
ws 诗页干净（0 个 {{另}}，不开 variants 行）；1 个新 source：全唐詩卷164 桩页
（锚点+转引用桩，noauthor 字段为空——同 V035 卷126 判例，PENDING）。

用法: python3 -I emit_v036.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/玉階怨__李白_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
QT164 = pathlib.Path('/tmp/src-dl/quantangshi/vol164.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一，且均落在李白传区间内——生成时断言） ----------
WS_L1 = slice_between(WS, '玉階生白露，夜久侵羅襪。', '玉階生白露，', 'ws第1句(玉阶白露)')
WS_L2 = slice_between(WS, '玉階生白露，夜久侵羅襪。', '夜久侵羅襪。', 'ws第2句(罗袜侵露)')
WS_L3 = slice_between(WS, '却下水晶簾，玲瓏望秋月。', '却下水晶簾，', 'ws第3句(下水精帘)')
WS_L4 = slice_between(WS, '却下水晶簾，玲瓏望秋月。', '玲瓏望秋月。', 'ws第4句(玲珑望月)')
WS_TITLE = slice_between(WS, '| title    = [[玉階怨]]', '| title    = [[玉階怨]]', 'ws header title(乐府旧题)')
WS_AUTHOR = slice_between(WS, '| author   = 李白', 'author   = 李白', 'ws header author(署名直证)')
JTS_LEAF = slice_between(JTS, '白旣嗜酒，日與飲徒醉於酒肆。玄宗度曲，欲造樂府新詞，亟召白，白已臥於酒肆矣。召入，以水灑面，即令秉筆，頃之成十餘章，帝頗嘉之。',
                         '帝頗嘉之。', '旧传乐府新词段(醉卧酒肆/水洒面/顷刻成章——两源合龙第一源)')
JTS_TB = slice_between(JTS, '天寳初，客遊會稽，與道士吳筠隱於剡中。', '隱於剡中。',
                       '旧传天宝初段(会稽吴筠——模糊时代标签原文)')
JTS_YY = slice_between(JTS, '初賀知章見白，賞之曰：「此天上謫仙人也。」', '此天上謫仙人也。」',
                       '旧传谪仙人段(两源合龙第二源·旧传侧)')
JTS_SZ = slice_between(JTS, '竟以飲酒過度，醉死於宣城。', '醉死於宣城。',
                       '旧传统卒地段(醉死宣城——两传分歧·旧传侧)')
XTS_LQ = slice_between(XTS, '帝坐沈香亭子，意有所感，欲得白為樂章；召入，而白已醉，左右以水靧面，稍解，援筆成文，婉麗精切無留思。',
                        '婉麗精切無留思。', '新传乐章段(沉香亭/水靧面/援笔成文——两源合龙第二源)')
XTS_TB = slice_between(XTS, '天寶初，南入會稽，與吳筠善，筠被召，故白亦至長安。', '故白亦至長安。',
                       '新传天宝初段(筠被召故白至长安——模糊时代标签原文+入京因果)')
XTS_HZY = slice_between(XTS, '往見賀知章，知章見其文，歎曰：「子，謫仙人也！」', '子，謫仙人也！」',
                        '新传谪仙人段(两源合龙第二源·新传侧)')
XTS_QS = slice_between(XTS, '白晚好黃老，度牛渚磯至姑孰，悅謝家青山，欲終焉。及卒，葬東麓。', '葬東麓。',
                       '新传统卒地段(青山欲终/葬东麓——两传分歧·新传侧)')
QT_STUB = slice_between(QT164, '==[[玉階怨 (李白)|玉階怨]]==\n{{:玉階怨 (李白)}}',
                        '{{:玉階怨 (李白)}}', '全唐诗卷164本诗条目(锚点+转引用桩——卷页无正文)')

# 传区间归属复验（V035 教训：切片必须落在本人传区间内，不落在别人传里）
_ja, _jb = JTS.find('=李白='), JTS.find('=杜甫=')
_xa = XTS.find('　　李白，')
_xb = _xa + re.search(r'^==[^=]', XTS[_xa:], re.M).start()
for _s, _r, _tag in [(JTS_LEAF, (_ja, _jb), 'JTS_LEAF'), (JTS_TB, (_ja, _jb), 'JTS_TB'),
                     (JTS_YY, (_ja, _jb), 'JTS_YY'), (JTS_SZ, (_ja, _jb), 'JTS_SZ'),
                     (XTS_LQ, (_xa, _xb), 'XTS_LQ'), (XTS_TB, (_xa, _xb), 'XTS_TB'),
                     (XTS_HZY, (_xa, _xb), 'XTS_HZY'), (XTS_QS, (_xa, _xb), 'XTS_QS')]:
    _src = JTS if _tag.startswith('JTS') else XTS
    if not (_r[0] <= _src.find(_s) <= _r[1]):
        raise SystemExit(f'切片越出李白传区间：{_tag}——修订后重生成')

BG = {
    'bg-yj-scene': (
        '这首诗只有二十个字，开场就是一级台阶：「玉階生白露，夜久侵羅襪」——'
        '玉石台阶上露水一点点积起来，久了，凉意漫进丝袜。没有人，没有事，'
        '只有一个站了很久的人的脚边证据。\n'
        '本传给不了这场站立——两传写李白全是动（召/召入/醉/放还/流夜郎），'
        '没有一条说他站在谁的阶下。玉阶在汉诗传统里是宫殿的台阶，'
        '但把它坐实成某座宫、某个人，本地史料无一字——诗内证据到「侵罗袜」为止，'
        '再往前一步就是编。'),
    'bg-yj-city': (
        '这座城诗里不出现，但要给这首诗找一个发生的城，史料里唯一够格的是长安——'
        '理由不是诗，是传：两传都把李白与「樂府新詞/樂章」拴在天寶初的长安上。'
        '旧传「天寳初，客遊會稽，與道士吳筠隱於剡中」——吴筠被召，'
        '新传补上因果「筠被召，故白亦至長安」。\n'
        '但「天寶初」就是两传能给的全部：不是年，是一个时代标签。'
        '乐府旧题不纪行旅，本传不系年——长安是最有依据的猜想，'
        '猜想不是断言。time.span/event.name/written_during 一个都不造。'),
    'bg-yj-world': (
        '「却下水晶簾，玲瓏望秋月」——进了屋，放下水精帘，隔着帘子望月亮。'
        '诗里的天下小到一个闺阁；这个人的天下大到一个词牌：'
        '玄宗要新乐词的时候，两唐书各自记下了同一场征召。\n'
        '旧传：「玄宗度曲，欲造樂府新詞，亟召白，白已臥於酒肆矣。召入，'
        '以水灑面，即令秉筆，頃之成十餘章」；新传：「帝坐沈香亭子，意有所感，'
        '欲得白為樂章；召入，而白已醉，左右以水靧面，稍解，援筆成文，'
        '婉麗精切無留思」——醉/召/洒水/立就，四个要素两个独立讲法全同：'
        '**皇帝的乐词需求就是李白一部分作品的真实生产场景**，这是本传能给的'
        '最硬的「为什么写」。但两传都只说「天寶初」，没有年标题级坐标——'
        '语境 KNOWN，年份照样不可得。'),
    'bg-yj-person': (
        '李白的定场诗不是他写的，是贺知章说的——而且两传各自在场：'
        '旧传「初賀知章見白，賞之曰：『此天上謫仙人也。』」；'
        '新传「往見賀知章，知章見其文，歎曰：『子，謫仙人也！』」——'
        '两源独立一致升 KNOWN：贺知章以「谪仙人」赏识过李白。\n'
        '但同一个人在两传里连**死在哪**都不一致：旧传「竟以飲酒過度，'
        '醉死於宣城」；新传「度牛渚磯至姑孰，悅謝家青山，欲終焉。及卒，葬東麓」'
        '（当涂青山）。宣城对当涂，两源直接分歧——不裁决，并列照登；'
        '「谪仙人」飘下来的仙人，连着陆点两传都没谈拢，这本身就是李白传写的诚实样子。\n'
        '「玲珑望秋月」二十个字的怨，放在这样一个人名下：'
        '他的诗一部分是皇帝要的，一部分是自己要的——这首哪边都不是，'
        '本地史料给不了判词，就不给判词。'),
}
CLAIMS = {
    'claim-bg-yj-scene': (
        'FACT', 'LIKELY',
        '白露/罗袜/下帘/望月全诗本文；玉阶=宫殿台阶为汉诗传统（非本地史料，标注为读法）；'
        '为谁立、立于何宫——两传无一字，不编。'),
    'claim-bg-yj-city': (
        'FACT', 'LIKELY',
        '长安关联由两传「天寶初」段给出（入京因果链逐字：筠被召故白至长安）；'
        '「天宝初」是时代标签不是年份——模糊时代照登不铸造；'
        '诗本身乐府题零城串，长安为最有依据的猜想、非断言。'),
    'claim-bg-yj-world': (
        'FACT', 'KNOWN',
        '御前醉草乐词语境——旧传「水灑面成十餘章」段与新传「靧面援筆成文」段'
        '两源独立一致（醉/召/洒水/立就四要素全同）升 KNOWN；此 KNOWN 只覆盖语境，'
        '两传均无年标题级坐标（只说天宝初）→ 诗 time.span/event.name/'
        'written_during 零铸造、零 relation；语境年不可得即诗年不可得。'),
    'claim-bg-yj-person': (
        'FACT', 'KNOWN',
        'KNOWN 两处之一：贺知章谪仙人之赏——旧传「此天上謫仙人也」与新传'
        '「子，謫仙人也」两源独立一致；**两传分歧处不升任何等级**：'
        '卒地（旧传醉死宣城/新传葬当涂青山）并列照登不裁决；'
        'certainty 不覆盖任何系年与卒地。'),
}
CITATIONS = [
    ('claim-bg-yj-scene', 'source-ws-t300-308',
     '页面 玉階怨（header title+author 两字段+第1、2句，四段以「……」相連——'
     '乐府旧题之页内直证+开场台阶；页内实测无 {{另|}} 异文，「查过、干净」；'
     '全文另见 V018 claim-t300-308-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-yj-city', 'source-quantangshi-164',
     '页面 全唐詩/卷164（本诗锚点+转引用桩 {{:玉階怨 (李白)}}；'
     '卷首 Collection header 的 noauthor 字段为空——卷页无作者标注、无正文，'
     '正文证据在诗页；同 V022/V025–V035 桩教训）',
     QT_STUB),
    ('claim-bg-yj-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传天宝初段（天寳初/会稽吴筠——模糊时代标签原文，旧传侧）',
     JTS_TB),
    ('claim-bg-yj-city', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传天宝初段（筠被召故白亦至长安——入京因果，新传侧；'
     '与旧传同段并证「天宝初」为两传共同的模糊标签）',
     XTS_TB),
    ('claim-bg-yj-world', 'source-ws-t300-308',
     '页面 玉階怨（第3、4句逐字——闺阁的小天下与下方御前的大场景并读）',
     join(WS_L3, WS_L4)),
    ('claim-bg-yj-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传乐府新词段（玄宗度曲欲造乐府新词/水灑面/'
     '頃之成十餘章——两源合龙第一源）', JTS_LEAF),
    ('claim-bg-yj-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传乐章段（沈香亭欲得乐章/水靧面/援筆成文——'
     '两源合龙第二源；醉/召/洒水/立就四要素与旧传全同，措辞各自逐字）', XTS_LQ),
    ('claim-bg-yj-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白传（谪仙人段+传统卒地段；两段以「……」相連，'
     '出处同卷同传——谪仙人两源合龙旧传侧/卒地分歧旧传侧）', join(JTS_YY, JTS_SZ)),
    ('claim-bg-yj-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传（谪仙人段+青山卒段；两段以「……」相連，'
     '出处同卷同传——谪仙人两源合龙新传侧/卒地分歧新传侧，与旧传并列不裁决）',
     join(XTS_HZY, XTS_QS)),
]
BG_LINES = {'bg-yj-scene': (1,), 'bg-yj-city': (2,), 'bg-yj-world': (3,), 'bg-yj-person': (4,)}
BG_AUDIENCE = {'bg-yj-scene': 'PRIMARY', 'bg-yj-city': 'JUNIOR',
               'bg-yj-world': 'SENIOR', 'bg-yj-person': 'PRIMARY'}
BG_TITLES = {'bg-yj-scene': '眼前：一级台阶上的站立',
             'bg-yj-city': '这座城：天宝初不是年份',
             'bg-yj-world': '这个天下：皇帝要新乐词的时候',
             'bg-yj-person': '这个人：谪仙人的着陆点'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 17 首·绝句第二例）；史实句均有逐字引证；'
                 'background_line 绝句形制：每层一行（1/2/3/4）；乐府题不纪行旅+'
                 '创作语境只有「天寶初」模糊标签→time.span/event.name/written_during '
                 '全缺席、零 relation；KNOWN 两处：御前醉草乐词语境（两源四要素全同）'
                 '+贺知章谪仙人之赏（两源）；卒地两传分歧并列不裁决。' for k in BG}


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
    A("""-- V036：李白《玉階怨》(work-t300-308) 四层背景（阶段 D 第 17 首·绝句第二例）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-308 与其 text-work-t300-308-ws、
--       source-ws-t300-308 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——不另开行）。本迁移另开 1 个 source（全唐詩卷164，见下）。
--
-- 数据源（可复现）：emit_v036.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/玉階怨__李白_.txt（页内实测无 {{另}}——「查过、干净」）、
--   舊唐書卷190下（李白传——乐府新词段/天宝初段/谪仙人段/醉死宣城段）、
--   新唐書卷202（李白传——乐章段/天宝初段/谪仙人段/葬青山段；与 V032 已用切片零重叠，
--   传区间归属生成时断言）、全唐詩卷164（锚点+转引用桩，noauthor 空——V035 卷126 判例）。
--
-- 做：1 个新 source（source-quantangshi-164，PENDING——桩页教训同款）+
--   4 BACKGROUND content/claim/background + 9 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 行 background_line（**绝句形制：每层一行** scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-308-ws 的 4 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「乐府题不纪行旅 + 语境只有模糊时代标签 + 卒地两传分歧」）：
--   * 乐府属性=诗页 title 直证；为谁立于何宫——两传无一字，明说不编；
--   * 「天寶初」两传同款模糊标签：不是年份，不做年表式演算——系年第十一次判决；
--   * 御前醉草乐词=两源独立一致（醉/召/洒水/立就四要素全同）升 KNOWN，
--     但只覆盖语境不外溢到诗（V033/V034/V035 事件判例的语境版：语境比事件更软，
--     连年标题级坐标都没有）；
--   * 贺知章谪仙人之赏=两传各自在场升 KNOWN；
--   * 卒地分歧（醉死宣城/葬当涂青山）——两源直接分歧并列照登不裁决，
--     升 KNOWN 的两处都不覆盖卒地；
--   * KNOWN 共两处，其余照 LIKELY。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 35，不含 36
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-yj-%';              -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-164';     -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-308-ws';  -- 恰 4（绝句）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-yj-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-308';                                  -- 4（绝句每层一行）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-yj-world','claim-bg-yj-person');
--     -- KNOWN / KNOWN（world=醉草语境不外溢；person=谪仙人两源，均不覆盖系年与卒地）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-yj-scene','claim-bg-yj-city');
--     -- LIKELY / LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-308'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-308';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-yj-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V036_rollback.sql（按 id 全枚举删除；不动 V018 的行，不动共用来源行；
--   本迁移自开的 source-quantangshi-164 随回滚删除）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新 source（1 个；桩页如实标注，PENDING 照 V031/V035 判例） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-164',
              'title': '《全唐詩》全唐詩/卷164（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷164（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷164',
              'rights_note': '维基文库录入本，公有领域古籍。卷首 Collection header 的 noauthor '
                             '字段为空——卷页无作者标注（与卷160 的孟浩然标注不同，同卷126/卷164 '
                             '无标注情形；本卷多数为李白诗，但标注缺失就按缺失声明）。本诗条目只有'
                             '锚点+转引用桩（异名消歧「玉階怨 (李白)」），正文在诗页。'
                             '本行由 emit_v036.py 对快照逐字定位。核验状态保持 PENDING。',
              'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
              'reliability': 'HIGH'}],
            'x.id = t.id'))

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
    brows = [{'id': k, 'work_id': 'work-t300-308',
              'layer': {'bg-yj-scene': 'SCENE', 'bg-yj-city': 'CITY',
                        'bg-yj-world': 'WORLD', 'bg-yj-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（绝句：每层一行） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-308-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 36, 'Li Bai Yu-jie-yuan background layers (stage-D poem 17, second quatrain): the two Tang histories jointly supply a creation context instead of a year -- JTS records the emperor fixing a tune and wanting new yuefu lyrics, Bai drunk at the wine-shop, water splashed on his face, a dozen-plus pieces composed at once, XTS independently tells the same scene at the Incense-Pavilion with face-washed and brush flowing (drunk / summoned / water / composed-on-the-spot: all four elements agree across two sources) -- KNOWN for the context only; both biographies date it merely kai-yuan-era tian-bao chu, a vague era label with no year-heading coordinate, so the dating verdict for the eleventh poem is: yuefu title records no journey AND the creation context itself has no year -- no year-table arithmetic, time.span/event.name/written_during absent, zero relations; He Zhizhang-s Banished-Immortal praise quoted verbatim from both biographies -- second KNOWN; a registered divergence: JTS says he died drunk at Xuancheng, XTS says he loved Qing-shan at Dangtu and was buried at its east foot -- two sources directly disagree on the place of death, side by side with no ruling, and neither KNOWN covers it; slices deliberately avoid every biography passage V032 already cited (Han-lin recommendation, Gao Lishi boot, Prince Yong, exile, Cui Zongzhi) and are range-checked into the Li Bai biography block at generation time; one new source: quan-tang-shi juan 164 page (anchor plus disambiguated transclusion stub Yu-jie-yuan (Li Bai); Collection header noauthor field empty -- no author attribution on the volume page, said honestly; PENDING per V031/V035 precedent); background_line uses the quatrain shape: one line per layer (1/2/3/4)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 36);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V036 精确回滚：只删 V036 插入的行（id 全枚举）。',
         '-- work-t300-308 本体、其 text_line 4 行与 source-ws-t300-308 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）不删；',
         '-- V036 自开的 source-quantangshi-164 随回滚删除；零 relation。',
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
    dels('poetry_source', 'id', ['source-quantangshi-164'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 36;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_L1, WS_L2, WS_L3, WS_L4, WS_TITLE, WS_AUTHOR,
              JTS_LEAF, JTS_TB, JTS_YY, JTS_SZ, XTS_LQ, XTS_TB, XTS_HZY, XTS_QS, QT_STUB]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 两传分歧双在场断言：卒地两处必须同现在 cited 且各在其侧引文里
    if '醉死於宣城' not in cited or '葬東麓' not in cited:
        bad.append('卒地分歧两处须逐字并证')
    p_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-yj-person' and s == 'source-jiutangshu-wenyuan')
    p_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-yj-person' and s == 'source-xintangshu-wenyi')
    if '醉死於宣城' not in p_jts or '醉死於宣城' in p_xts or '葬東麓' not in p_xts or '葬東麓' in p_jts:
        bad.append('卒地两处须各归其传侧引文，不得互串')
    # 两源合龙断言：四要素关键词在两源侧引文都必须在场（醉/召/洒水/立就 的原文锚）
    w_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-yj-world' and s == 'source-jiutangshu-wenyuan')
    w_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-yj-world' and s == 'source-xintangshu-wenyi')
    if '欲造樂府新詞' not in w_jts or '欲得白為樂章' not in w_xts:
        bad.append('御前乐词两源侧关键词不齐')
    if '以水灑面' not in w_jts or '以水靧面' not in w_xts:
        bad.append('洒水要素两源侧原文（灑/靧 各自逐字）不齐')
    # 模糊标签不许被写成具体年份：引文字段里不得出现年号+数字年
    for c, _, _, ex in CITATIONS:
        if re.search(r'天寶[一二三四五六七八九十]+年|開元[一二三四五六七八九十]+年', ex):
            bad.append(f'引文字段出现具体年号纪年——语境只许「天寶初」模糊标签: {c}')
    # 绝句形制：每层恰 1 行，合计 4
    if sum(len(v) for v in BG_LINES.values()) != 4 or any(len(v) != 1 for v in BG_LINES.values()):
        bad.append('绝句 background_line 必须是每层恰 1 行（4 层共 4 行）')
    if len(re.findall(r"text-work-t300-308-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V036 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V036 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-308' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V036 有意不给诗铸 {pk}，但该主语组合出现了')
    ev_claims = re.findall(r"SELECT '([^']+)' AS subject_id, 'event\.name'", sql)
    if ev_claims:
        bad.append(f'V036 不给诗铸 event.name，但出现了主语: {ev_claims}')
    if "SELECT 'work-t300-308' AS subject_id" in sql:
        bad.append('V036 的 claim 主语应全部是 bg-yj-*，work-t300-308 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V036 不碰 poetry_text_line')
    if sql.count('INSERT INTO poetry_source') != 1:
        bad.append('V036 应恰有 1 个 poetry_source INSERT（source-quantangshi-164）')
    if "'source-quantangshi-164' AS id" not in sql:
        bad.append('新 source 应为 source-quantangshi-164')
    if "DELETE FROM poetry_source WHERE id IN ('source-quantangshi-164')" not in build_rollback():
        bad.append('回滚未删除 V036 自开的 source-quantangshi-164')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 15 切片逐字过审且全部进引文；'
              f'切片传区间归属已生成时复验；卒地分歧各归其侧断言；乐词四要素两源在场断言；'
              f'模糊标签拒具体纪年断言；绝句每层一行形制断言；(claim,source) 主键 '
              f'{len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；1 新 source+回滚同步断言；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
