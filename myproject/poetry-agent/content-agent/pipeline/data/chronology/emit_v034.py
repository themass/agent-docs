#!/usr/bin/env python3
"""阶段 D 第 15 首：生成 V034——王翰《涼州詞二首 一》(work-t300-106, V018 已立) 四层背景。

修订版（2026-11-20 缺口卷补齐后）：初稿判「张说罢知政事的年份本地核不到」，依据是
通鉴卷 211（覆盖 723–726）是维基文库残缺卷（Textquality 50%，全卷零「張說」）。
缺口补齐后复扫发现**判断错了**：726 全年在通鉴卷 213——開元十四年（丙寅，公元七二六年）
标准形年标题下就有罢相条「但罷說中書令，餘如故」，逐字可得。更要命的是初稿的 WORLD
引文把「制說致仕」（开元十五年/727 条目）与「雖罷政事」（开元十六年/728 条目）接在
730 年标题后——恰犯了自己立的「不能张冠李戴」。迁移未执行，就地改正：
WORLD 引文改为**三个标准形年标题各带本年条目**（726 罢相条、727 致仕条、728 罢政事条），
归属以切片顺序硬断言。系年判决仍是零铸造，但理由升级：因果链的第一个绝对年份
（726 张说罢相）现在是本地 KNOWN 事件——**下限硬而诗年仍不可得**（V033 形状再现）。

「为什么写」第七次成立：新唐书本传把王翰一生的每一级台阶都挂在张说身上——「張說至，禮益加」
→「方說輔政，故召為秘書正字」→「**說罷宰相，翰出為汝州長史**」→「坐貶道州司馬，卒」。
一荣俱荣、一损俱损，全传四步三步系于一人。诗里的「葡萄美酒」「醉臥沙場」就写在这个
人物的起落底色上——豪气是张说时代长安的豪气，贬死是张说倒台后的贬死。

系年第九次判决：**全缺席，缺席原因是「乐府题不纪行旅，本传不系年」**——不再是「年份
核不到」：罢相年 726 已核到（通鉴标准形年标题），但乐府题不纪行旅，锚到事件也到不了诗。

两源之隔（单传诗人的松动情形，V033 判例的对偶）：王翰无独立本传于旧唐书，但旧传
张说品评段存「王翰之文，如瓊懷玉斝，雖爛然可珍，而多有玷缺」——两源独立一致处恰是
**张说与王翰的知遇关系**：新传记其果（礼遇/召用/出贬），旧传记其言（张说亲口品其文）。
KNOWN 升两处：知遇关系（两源）+ 726 罢相事件（通鉴编年体直书，V028/V033 事件判例）；
其余新传独得（豪健恃才/蒱酒/自视王侯/贬死）按 LIKELY 并列照登。

绝句第一例：诗只有 4 行，background_line 从「四层×两句」改绑「**每层一行**」
（scene→1 city→2 world→3 person→4），audit 加行数=4 断言。
ws 诗页干净（0 个 {{另}}，「查过、干净」不开 variants 行）；全唐詩卷156 本地缺——
无卷页桩，诚实缺一条 citation（V032 先例：有则引，无则写明无）。

缺席断言基础（V034 依赖）：tongjian tj-191–265 **75/75 全卷完整性已验证**
（2026-11-20 缺口补齐+错误页扫描零命中），「通鉴无王翰」在全量集合上复扫成立。

用法: python3 -I emit_v034.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/涼州詞__葡萄美酒夜光杯_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190上.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
TJ213 = pathlib.Path('/tmp/src-dl/tongjian/tj-213.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一，tj-213 六段为补齐后新验） ----------
WS_L1 = slice_between(WS, '葡萄美酒夜光杯，欲飲琵琶馬上催。', '葡萄美酒夜光杯，', 'ws第1句(美酒夜光杯)')
WS_L2 = slice_between(WS, '葡萄美酒夜光杯，欲飲琵琶馬上催。', '欲飲琵琶馬上催。', 'ws第2句(琵琶催发)')
WS_L3 = slice_between(WS, '醉臥沙場君莫笑，古來征戰幾人回。', '醉臥沙場君莫笑，', 'ws第3句(醉卧沙场)')
WS_L4 = slice_between(WS, '醉臥沙場君莫笑，古來征戰幾人回。', '古來征戰幾人回。', 'ws第4句(几人回)')
# header 三字段各为逐字切片（title 与 author 之间隔着 section 行，不并写——各段必须各自 verbatim）
WS_TITLE = slice_between(WS, '| title    = 涼州詞二首', '| title    = 涼州詞二首', 'ws header title(组诗二首)')
WS_SECTION = slice_between(WS, '| section  = 一', 'section  = 一', 'ws header section(其一)')
WS_AUTHOR = slice_between(WS, '| author   = 王翰', 'author   = 王翰', 'ws header author(署名直证)')
JTS_SHUO = slice_between(JTS, '王翰之文，如瓊懷玉斝，雖爛然可珍，而多有玷缺。', '而多有玷缺。」',
                         '旧传张说品文段(琼杯玉斝之喻——知遇关系第二源)')
XTS_HEAD = slice_between(XTS, '王翰，字子羽，并州晉陽人。少豪健恃才，及進士第，然喜蒱酒。',
                         '然喜蒱酒。', '新传首段(晋阳人/豪健恃才/蒱酒)')
XTS_JZ = slice_between(XTS, '張嘉貞為本州長史，偉其人，厚遇之。翰自歌以舞屬嘉貞，神氣軒舉自如。張說至，禮益加。',
                       '禮益加。', '新传张嘉贞/张说礼遇段(自歌以舞——旧源无)')
XTS_GW = slice_between(XTS, '復舉直言極諫，調昌樂尉，又舉超拔君類。方說輔政，故召為秘書正字，擢通事舍人、駕部員外郎。家畜聲伎，目使頤令，自視王侯，人莫不惡之。',
                       '人莫不惡之。', '新传辅政召用段(方说辅政故召——因果第一步)')
XTS_CHU = slice_between(XTS, '說罷宰相，翰出為汝州長史，徙仙州別駕。日與才士豪俠飲樂游畋，伐鼓窮歡，坐貶道州司馬，卒。',
                        '坐貶道州司馬，卒。', '新传出贬段(说罢宰相翰出——因果第二步+贬死)')
# tj-213 六段（2026-11-20 缺口补齐后新验；归属：各条目落在其年标题与下一年标题之间，audit 硬断言）
TJ14_TITLE = slice_between(TJ213, '=== 玄宗至道大聖大明孝皇帝中之上開元十四年（丙寅，公元七二六年）===',
                           '開元十四年（丙寅，公元七二六年）===', '通鉴213卷726年标题(标准形)')
TJ14_BA = slice_between(TJ213, '源乾曜等鞫張說，事頗有狀，上使高力士視說，力士還奏：「說蓬首垢面，席蒿，食以瓦器，惶懼待罪。」上意憐之。力士因言說有功於國，上以為然。庚申，但罷說中書令，餘如故。',
                        '餘如故。', '通鉴726罢相条(但罢说中书令——罢宰相正身，开元十四年条目)')
TJ15_TITLE = slice_between(TJ213, '=== 玄宗至道大聖大明孝皇帝中之上開元十五年（丁卯，公元七二七年）===',
                           '開元十五年（丁卯，公元七二七年）===', '通鉴213卷727年标题(标准形)')
TJ15_ZHI = slice_between(TJ213, '御史大夫崔隱甫、中丞宇文融，恐右丞相張說復用，數奏毀之，各為朋黨。上惡之，二月，乙巳，制說致仕，隱甫免官侍母，融出為魏州刺史。',
                         '融出為魏州刺史。', '通鉴727致仕条(制说致仕——是致仕非罢相，声明在locator)')
TJ16_TITLE = slice_between(TJ213, '=== 玄宗至道大聖大明孝皇帝中之上開元十六年（戊辰，公元七二八年）===',
                           '開元十六年（戊辰，公元七二八年）===', '通鉴213卷728年标题(标准形)')
TJ16_BA = slice_between(TJ213, '二月，壬申，以尚書右丞相致仕張說兼集賢院學士。說雖罷政事，專文史之任，朝廷每有大事，上常遣中使訪之。',
                        '上常遣中使訪之。', '通鉴728罢政事条(虽罢政事专文史——张说线收口)')

BG = {
    'bg-lz-scene': (
        '这首诗的开场是一桌酒席上最贵的一件器物：「葡萄美酒夜光杯」——'
        '葡萄酒盛在夜光杯里。第二句人就开始起身：「欲飲琵琶馬上催」——'
        '正要喝，琵琶弹起了催发的曲子。\n'
        '但这是诗里的酒席，不是史料里的酒席。本传能给的最近的一条是「家畜聲伎，'
        '目使頤令，自視王侯」——家里养着歌伎，使唤仆妾像动下巴一样随意，'
        '把自己看得和王侯一样——新传记他的豪奢是这种规格。至于这首诗写于哪一场酒，'
        '本传无一字，本地核不到就不编。'),
    'bg-lz-city': (
        '这座城不在诗里发生——《涼州詞》是乐府旧题。维基文库诗页就标着两层：'
        'title「涼州詞二首」+ section「一」（组诗第一首）。凉州是曲调的名字，'
        '不是王翰的脚步：本地史料里没有一行说他到过凉州或任何边地。'
        '所以这首诗的正确读法先要摆正：他是**在长安的繁华里写边塞的歌**——'
        '拟乐府的写法，唐人也明知是拟作。\n'
        '他一生实际走过的城在本传里排成一串：并州晋阳人（字子羽），进士及第后'
        '调昌乐尉，召为秘书正字、通事舍人、驾部员外郎都在长安，'
        '「說罷宰相，翰出為汝州長史，徙仙州別駕」——贬出长安后辗转汝州、仙州，'
        '「坐貶道州司馬，卒」——最后死在道州。从长安到道州，就是他的全部地图。'),
    'bg-lz-world': (
        '「醉臥沙場君莫笑，古來征戰幾人回」——诗里的沙场是乐府的沙场；'
        '这个人的沙场在朝堂，而且是当时最大的那一场：张说。这一场通鉴系了年。\n'
        '通鉴卷 213 给这条因果链钉了三个标准形年标题，各带本年条目：'
        '開元十四年（丙寅，公元七二六年）「庚申，但罷說中書令，餘如故」——这就是新传'
        '「說罷宰相」的正身；開元十五年（丁卯，公元七二七年）「二月，乙巳，制說致仕」'
        '——致仕，不是罢相；開元十六年（戊辰，公元七二八年）「說雖罷政事，專文史之任」'
        '——收口。三条逐年归属，初稿曾把后两条误挂七三〇标题下，已改正——'
        '致仕≠罢相，年份错一格就是张冠李戴。\n'
        '王翰的全部起伏都吊在这根线上：张说当国他被召进中枢，张说倒他外放贬死。'
        '因果链的第一个绝对年份现在是硬的（726 罢相，通鉴编年体直书升 KNOWN），'
        '但诗仍是乐府题——乐府不纪行旅，锚到事件也到不了诗。'
        'time.span、event.name、written_during 一个都不造。'),
    'bg-lz-person': (
        '王翰这个人的全部证词，新旧唐书各留一半，两半在「张说」身上合龙。\n'
        '新唐书（卷202 文艺中，他唯一完整的一传）写他的狂：「少豪健恃才，及進士第，'
        '然喜蒱酒」；张嘉贞厚遇他，他「自歌以舞屬嘉貞，神氣軒舉自如」；'
        '「家畜聲伎，目使頤令，自視王侯，人莫不惡之」；贬出后还「日與才士豪俠飲樂游畋，'
        '伐鼓窮歡」——天天和豪侠饮宴打猎，擂鼓尽欢——最后为这份排场获罪'
        '「坐貶道州司馬，卒」。\n'
        '旧唐书（卷190上，无王翰传）留下张说的原话：张说对徐坚品评后进文士——'
        '「王翰之文，如瓊懷玉斝，雖爛然可珍，而多有玷缺」——像玉杯，灿烂可爱，'
        '可惜疤多。这句话和「瓊杯」的比喻本身，就是知遇的实物证据：'
        '两源独立一致升 KNOWN 的第一点：张说认识、赏识并品评过王翰。\n'
        '因果链由新传单源给出：「方說輔政，故召為秘書正字」——因果一步；'
        '「說罷宰相，翰出為汝州長史」——因果二步（此步的年份由通鉴 726 条独立钉实）；'
        '贬死——结局。独得处（豪健、蒱酒、自视王侯、伐鼓穷欢、贬死）按 LIKELY 照登不升。\n'
        '「古来征战几人回」放在这样一个人身上，不是慷慨，是他整个人的口径：'
        '把命看得和一场酒一样轻——本传的每一个字都在给这句诗当注脚。'),
}
CLAIMS = {
    'claim-bg-lz-scene': (
        'FACT', 'LIKELY',
        '酒器/琵琶/催发全诗本文；家畜声伎/自视王侯为新传单源（LIKELY 照登）；'
        '写作酒席不编（本传无一字，本地核不到）。'),
    'claim-bg-lz-city': (
        'FACT', 'KNOWN',
        '乐府题属性由诗页 title+section 双字段逐字支撑（组诗其一）；'
        '行迹城串（晋阳→昌乐→长安→汝州→仙州→道州）全新传逐字；'
        '到过凉州/边地——本地史料零记载（通鉴 75/75 全量复扫零命中，2026-11-20），明说不编。'),
    'claim-bg-lz-world': (
        'FACT', 'KNOWN',
        '726 罢相条+727 致仕条+728 罢政事条，通鉴三个标准形年标题逐年归属逐字'
        '（干支对账 audit 检查4 覆盖）——罢相事件本体升 KNOWN（V028/V033 事件判例：'
        '编年体直书）；此 KNOWN **只覆盖事件，不外溢到诗**：乐府题不纪行旅→'
        '诗 time.span/event.name/written_during 零铸造、零 relation；'
        '致仕≠罢相的逐年声明在本 claim 与 locator 双重在场。'),
    'claim-bg-lz-person': (
        'FACT', 'KNOWN',
        'KNOWN 两处之一：张说知遇王翰——新传（礼遇/召用/出贬三处因果）与旧传张说品文语'
        '两源独立一致；新传独得处（性格/奢侈/贬死细节）与因果链措辞均 LIKELY 并列照登；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-lz-scene', 'source-ws-t300-106',
     '页面 涼州詞二首（header title+section+author 三字段+第1、2句，五段以「……」相連——'
     '乐府组诗其一之页内直证+开场酒席；页内实测无 {{另|}} 异文，「查过、干净」；'
     '全文另见 V018 claim-t300-106-text 引文）',
     join(WS_TITLE, WS_SECTION, WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-lz-city', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王翰传（首段——晋阳人/进士第；行迹城串起点，'
     '城串全程与终点在 PERSON 层引文段；乐府题属性之证在 SCENE 层引文段）', XTS_HEAD),
    ('claim-bg-lz-world', 'source-ws-t300-106',
     '页面 涼州詞二首（第3句逐字——沙场为乐府意象）', WS_L3),
    ('claim-bg-lz-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百十三·玄宗·三组「年标题+本年条目」（726 罢相/727 致仕/728 罢政事，'
     '六段以「……」相連，归属=各条目在本年标题与下一年标题之间；**致仕≠罢相**——'
     '罢宰相正身是 726「但罷說中書令」，727 制說致仕、728 雖罷政事各归本年，不冒名顶替）',
     join(TJ14_TITLE, TJ14_BA, TJ15_TITLE, TJ15_ZHI, TJ16_TITLE, TJ16_BA)),
    ('claim-bg-lz-person', 'source-ws-t300-106',
     '页面 涼州詞二首（第4句逐字——几人回之口吻与下方两传证词对读）', WS_L4),
    ('claim-bg-lz-person', 'source-jiutangshu-wenyuan',
     '卷一百九十上·文苑上·张说品文段（张说对徐坚语中「王翰之文」一句——'
     '旧传无王翰传，此为旧传侧唯一直证，知遇关系第二源）', JTS_SHUO),
    ('claim-bg-lz-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王翰传（首段+礼遇段+辅政召用段+出贬贬死段；'
     '四段以「……」相連，出处同卷同传——因果链三步与城串终点全在此四段）',
     join(XTS_HEAD, XTS_JZ, XTS_GW, XTS_CHU)),
]
BG_LINES = {'bg-lz-scene': (1,), 'bg-lz-city': (2,), 'bg-lz-world': (3,), 'bg-lz-person': (4,)}
BG_AUDIENCE = {'bg-lz-scene': 'PRIMARY', 'bg-lz-city': 'JUNIOR',
               'bg-lz-world': 'SENIOR', 'bg-lz-person': 'SENIOR'}
BG_TITLES = {'bg-lz-scene': '眼前：一桌核不到酒席的酒',
             'bg-lz-city': '这座城：凉州是曲名不是脚步',
             'bg-lz-world': '这个天下：吊在张说身上的起落',
             'bg-lz-person': '这个人：玉杯多玷'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 15 首·第一首绝句）；史实句均有逐字引证；'
                 'background_line 绝句形制：每层一行（1/2/3/4）；乐府题不系年→'
                 'time.span/event.name/written_during 全缺席、零 relation；'
                 '张说罢相 726 通鉴标准形年标题逐字（KNOWN 仅事件本体，不外溢到诗）；'
                 'KNOWN 两处：张说知遇（两源一致）+726 罢相（编年体直书）。' for k in BG}


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
    A("""-- V034：王翰《涼州詞二首 一》(work-t300-106) 四层背景（阶段 D 第 15 首·第一首绝句）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-106 与其 text-work-t300-106-ws、
--       source-ws-t300-106 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行；source-zizhi-tongjian-events 是 V015 的行——都不另开行）。
--
-- 数据源（可复现）：emit_v034.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/涼州詞__葡萄美酒夜光杯_.txt（页内实测无 {{另}}——「查过、干净」）、
--   舊唐書卷190上（张说品文段——旧传无王翰传，唯一直证）、新唐書卷202（王翰完整本传）、
--   資治通鑑卷213（726/727/728 三个标准形年标题+本年罢相/致仕/罢政事条；
--   快照为 2026-11-20 缺口补齐+错误页全量重抓后版本，tj-191–265 75/75 完整性已验证）。
--   **全唐詩卷156 本地缺**——本诗无卷页桩，诚实缺一条 citation（V032 先例）。
--
-- 做：0 个新 source + 4 BACKGROUND content/claim/background +
--   7 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 行 background_line（**绝句形制：每层一行** scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-106-ws 的 4 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「乐府题不纪行旅」——年份边界已在缺口补齐后重划）：
--   * 乐府属性=诗页 title「涼州詞二首」+section「一」直证；到过凉州/边地本地史料零记载
--     （通鉴 75/75 全量复扫零命中）——明说拟乐府，不编边塞行旅；
--   * 张说罢知政事=通鉴卷213 開元十四年（丙寅，公元七二六年）条「但罷說中書令，餘如故」，
--     逐字可得，升 KNOWN——但 KNOWN 只覆盖事件本体，不外溢到诗；
--   * 逐年归属硬断言：727「制說致仕」（致仕≠罢相）、728「雖罷政事」各随本年标题；
--     初稿曾把这两条误挂 730 标题下（当时 tj-211/213 为坏页所致误判），执行前已改正；
--   * KNOWN 共两处（张说知遇王翰：两源独立一致；726 罢相：编年体直书 V028/V033 判例）；
--     新传独得处（豪健/蒱酒/声伎/贬死/因果链措辞）按 LIKELY 照登；
--   * 写作酒席不编（本传无一字）。
--
-- 干支对账：726=丙寅、727=丁卯、728=戊辰（tj-213 标准形年标题，audit 检查4 覆盖）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 33，不含 34
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-lz-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-106-ws';  -- 恰 4（绝句）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-lz-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-106';                                  -- 4（绝句每层一行）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-lz-city','claim-bg-lz-world','claim-bg-lz-person');
--     -- KNOWN / KNOWN / KNOWN（city=乐府题+城串有据；world=726 罢相事件，不外溢到诗；
--     --   person 的 KNOWN 仅知遇一处）
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-lz-scene';    -- LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-106'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-106';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-lz-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V034_rollback.sql（按 id 全枚举删除；不动 V018 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-106',
              'layer': {'bg-lz-scene': 'SCENE', 'bg-lz-city': 'CITY',
                        'bg-lz-world': 'WORLD', 'bg-lz-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-106-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 34, 'Wang Han Liang-zhou-ci background layers (stage-D poem 15, first quatrain): the biography supplies a full rise-and-fall causal chain but the poem itself gets no year -- every rung of Wang Han-s career hangs on Zhang Yue (summoned while Yue was in power, sent out when Yue was dismissed, died of a later demotion); the yuefu title is proven by the ws page header itself (title Liang-zhou-ci er-shou plus section yi: no.1 of a pair), and no local source puts Wang Han anywhere near Liang-zhou or the frontier (rescanned over the complete tong-jian snapshot tj-191 to tj-265, 75 of 75 volumes integrity-verified after the 2026-11-20 gap refill), so the poem is a Chang-an yuefu imitation, said so plainly; the dismissal year was re-checked after the gap refill and IS localizable -- tong-jian ju 213 carries it under the standard-form year heading Kaiyuan 14 (bing-yin, 726 CE): geng-shen, dan-ba-yue-zhong-shu-ling (Zhang Yue was merely dismissed as Zhong-shu-ling), and the two follow-up entries each keep their own year heading: Kaiyuan 15 (ding-mao, 727): zhi-yue-zhi-shi (retirement, NOT the dismissal) and Kaiyuan 16 (wu-chen, 728): sui-ba-zheng-shi; the first draft had wrongly hung the latter two under the 730 heading (a misjudgment caused by the then-broken ju-211 snapshot) -- corrected before execution, attribution asserted in the generator; KNOWN covers the dismissal event only and never the poem (dating still zero-cast: no time.span, no event.name, no written_during, zero relations -- yuefu titles record no journey); KNOWN raised at exactly two points (the Zhang-Yue-Wang-Han bond, JTS quote plus XTS chain, two independent sources; and the 726 dismissal as annalistic text, V028/V033 event precedent); background_line uses the quatrain shape: one line per layer (1/2/3/4)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 34);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V034 精确回滚：只删 V034 插入的行（id 全枚举）。',
         '-- work-t300-106 本体、其 text_line 4 行与 source-ws-t300-106 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi/tongjian-events）不删；V034 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 34;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_L1, WS_L2, WS_L3, WS_L4, WS_TITLE, WS_SECTION, WS_AUTHOR, JTS_SHUO, XTS_HEAD,
              XTS_JZ, XTS_GW, XTS_CHU,
              TJ14_TITLE, TJ14_BA, TJ15_TITLE, TJ15_ZHI, TJ16_TITLE, TJ16_BA]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # tj-213 逐年归属硬断言：罢相条随726标题、致仕条随727标题、罢政事条随728标题，
    # 且六段在 WORLD 引文里按 标题,条目,标题,条目,标题,条目 的顺序出现（顺序=归属）
    tj_ex = next(ex for c, s, _, ex in CITATIONS
                 if c == 'claim-bg-lz-world' and s == 'source-zizhi-tongjian-events')
    order = [TJ14_TITLE, TJ14_BA, TJ15_TITLE, TJ15_ZHI, TJ16_TITLE, TJ16_BA]
    pos = [tj_ex.find(s) for s in order]
    if -1 in pos or pos != sorted(pos):
        bad.append('tj-213 六段在 WORLD 引文中未按 年标题,条目 顺序出现（归属断言失败）')
    if tj_ex.find(TJ15_TITLE) - (tj_ex.find(TJ14_BA) + len(TJ14_BA)) != 2:
        bad.append('726 罢相条与 727 年标题之间应恰隔一个「……」连接符')
    # 绝句形制：每层恰 1 行，四行合计 4
    if sum(len(v) for v in BG_LINES.values()) != 4 or any(len(v) != 1 for v in BG_LINES.values()):
        bad.append('绝句 background_line 必须是每层恰 1 行（4 层共 4 行）')
    if len(re.findall(r"text-work-t300-106-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V034 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V034 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-106' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V034 有意不给诗铸 {pk}，但该主语组合出现了')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V034 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V034 零新 source，不该出现 INSERT INTO poetry_source')
    # 引文字段互斥断言（初稿教训）：730/七三零 不得出现在任何引文字段——
    # V034 的张说线只用 726/727/728 三年，一个 730 字符都不进证据层
    for c, _, _, ex in CITATIONS:
        for tok in ('七三零', '730', '開元十八年'):
            if tok in ex:
                bad.append(f'730 系字符混入引文字段（张说线已重划为 726/727/728）: {c} 含 {tok}')
    # KNOWN 升事件的形状断言：world 是事件 KNOWN（726），但绝不给诗铸 event.name——
    # 主语必须全部是 bg-lz-*，work-t300-106 名下零 claim 行（V033 先例复核）
    ev_claims = re.findall(r"SELECT '([^']+)' AS subject_id, 'event\.name'", sql)
    if ev_claims:
        bad.append(f'V034 不给诗铸 event.name，但出现了主语: {ev_claims}')
    if "SELECT 'work-t300-106' AS subject_id" in sql:
        bad.append('V034 的 claim 主语应全部是 bg-lz-*，work-t300-106 不该做主语')
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
              f'tj-213 六段逐年归属顺序硬断言；730 系字符不入引文字段已断言；'
              f'绝句每层一行形制断言；(claim,source) 主键 '
              f'{len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
