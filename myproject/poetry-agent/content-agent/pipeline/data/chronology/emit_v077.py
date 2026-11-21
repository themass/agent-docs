#!/usr/bin/env python3
"""阶段 D 第 58 首：生成 V077——劉方平《春怨》(work-t300-360, V018 已立) 四层背景。

**恰新建 source 一枚：source-quantangshi-768**——卷768 卷页源（V076 首立卷页源之第二枚）：
金昌緒《春怨》的底本卷页携带**编者附记小传**「金昌緒，餘杭人，詩一首。」+题级{{另}}锚
「=={{另|春怨|伊州歌}}===」+**inline 全文转录**（非空壳——与 V076 253 空壳成底本两态：
壳在册/inline 在录），非新源不能逐字承载（audit 断言恰一枚 source INSERT、回滚恰删此一枚；
source-ws-t300-360 / source-ws-t300-043 / source-zizhi-tongjian-events 复用零新建）。

**征引耗尽首枚（通鉴账让渡）**：同字两界二十二形态·让渡形态首见——本诗第二句有淚痕，
通鉴「淚痕」恰一（光啟二年丙午八八六僖宗奔鳳翔宿板下解袍賜王建「以其有淚痕故也」）——
**这一处已被 V056《怨情》逐字引走用讫**（域 ['V056'] 机器断言）：通鉴的泪痕账没有第二笔，
本迁移只登记耗尽事实、**在册句零重开硬断言**（「以其有淚痕故也」不入任何引文）——同字两界
第一次以「这一账前人先记走了」的形态出现。轮到梨花：通鉴「梨花」恰一（延載元年甲午六九四
太后出梨花一枝以示宰相、宰相皆以為瑞、杜景儉獨曰「陰陽不時、咎在臣等」——史的梨花是
反常到教宰相拜谢的灾异，诗的梨花是无人开门来看的满地落白）。

**同题两诗在册首枚**：选本同时收《春怨》两首——t300-360 劉方平（七绝）/t300-043 金昌緒
（五绝，「打起黃鶯兒」）——同题两诗各有 work/text/claim/source 全套在册（机器断言）；
题面「春怨」在全唐诗快照恰两卷：143（王昌齡锚+空壳——只计数）/768（金昌緒 inline 全文
逐字入引）——**同题三诗三命运**：刘底本卷251 抓取失败（在册外零第二枚）、金底本卷768
inline 在录、王锚壳在册。一作伊州歌两处独立见证（768 锚内 {{另|春怨|伊州歌}} + 金选本页
题面 {{*|一作伊州歌}}——题面{{*}}20 页闭域）只登记不裁决；768 与金选本页诗面互异
（{{另|啼時|幾時}} vs {{另|啼時|幾迴}}、却/卻）——异文跨面见证对第二枚。

**存储面即定読面第二枚（折叠族）**：V018 ws-raw 四行净文=本页 poem 块折叠面——{{另|欲|又}}
取头部主读「欲」、两物理行行尾随行空格全裁（生成时拼合双向断言）；notes 行尾**双随行空格
全库恰一页**（机器断言唯此页——照登）；{{唐詩三百首}} 走「}}」同行随尾挂法（145 页闭域，
与 V075 body 独立行挂法 59 页闭域对成挂法两式总账）；类目四行四元组（唐詩/七言絕句/閨怨詩/
詠春詩）**全库恰一页**（金选本页五言四元组亦恰一页——同题两页各占一个唯一类目面）。

PERSON 层：**零传记之人第三、四枚合页首枚**——劉方平/金昌緒在七史快照全零（机器断言）；
金有 verbatim 记在 768 编者附记（与 V076 王之渙附记同款装置：王之渙得「詩六首」、
金昌緒得「詩一首」）；刘无附记、快照「劉方平」恰两处全在锚/署名行（017「====巫山高
劉方平著====」——「著」式锚全书 55 处唯卷017（机器断言），只计数不入引 audit 硬卡；
018 署名行）——刘只留名、金留一首。KNOWN 零第卅三例（两首 V018 KNOWN text claim 在册
零重开不碰）。四句七绝 shape：**1/1/1/1 第九次**。

用法: python3 -I emit_v077.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/春怨__劉方平_.txt').read_text(encoding='utf-8')
WJ = pathlib.Path('/tmp/src-dl/ws-poems/春怨__金昌緒_.txt').read_text(encoding='utf-8')
V768 = pathlib.Path('/tmp/src-dl/quantangshi/vol768.txt').read_text(encoding='utf-8')
V143 = pathlib.Path('/tmp/src-dl/quantangshi/vol143.txt').read_text(encoding='utf-8')
V17 = pathlib.Path('/tmp/src-dl/quantangshi/vol017.txt').read_text(encoding='utf-8')
FETCH = pathlib.Path('/tmp/src-dl/quantangshi/fetch.log').read_text(encoding='utf-8')
V018 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V018__tang300_ws_verified.sql').read_text(encoding='utf-8')
TJ205 = pathlib.Path('/tmp/src-dl/tongjian/tj-205.txt').read_text(encoding='utf-8')
TJ256 = pathlib.Path('/tmp/src-dl/tongjian/tj-256.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_AUTHOR = slice_between(WS, '| author   = 劉方平', '| author   = 劉方平',
                          'ws 刘页 header author(署名直证——七史无传之人只在页header留名)')
WS_POEM_A = slice_between(WS, '紗窗日落漸黃昏，金屋無人見淚痕。 ', '金屋無人見淚痕。 ',
                          'ws 刘页 poem 物理行1存原样(行尾随行空格照登)')
WS_POEM_B = slice_between(WS, '寂寞空庭春{{另|欲|又}}晚，梨花滿地不開門。 ', '梨花滿地不開門。 ',
                          'ws 刘页 poem 物理行2存原样({{另|欲|又}}异读+行尾随行空格照登)')
WS_NOTE = slice_between(WS, '| notes    ={{Textquality|75%}}↑ [[全唐詩/卷251#春怨|全唐詩·卷251]]  ',
                        '全唐詩·卷251]]  ',
                        'ws 刘页 notes 整值(七五评级+↑底本回指同行+行尾双随行空格全库恰一页——回指目标卷251不在快照抓取失败在册)')
WS_300 = slice_between(WS, '}}{{唐詩三百首}}', '}}{{唐詩三百首}}',
                        'ws {{唐詩三百首}}「}}」同行随尾挂法(145页闭域——与V075 body独立行挂法59页闭域对成挂法两式)')
WS_CAT4 = slice_between(WS, '[[Category:唐詩]]\n[[Category:七言絕句]]\n[[Category:閨怨詩]]\n[[Category:詠春詩]]',
                        '[[Category:詠春詩]]',
                        'ws 刘页类目四行四元组(唐詩/七言絕句/閨怨詩/詠春詩——全库恰一页;整理者动作不升格V048)')
FETCH_251 = slice_between(FETCH, '全唐詩/卷251: 全唐詩/卷251\n全唐詩/卷251: 全唐詩/卷251\n卷251: FAILED both name forms\n全唐詩/卷253 -> vol253.txt 2088 chars',
                          '全唐詩/卷253 -> vol253.txt 2088 chars',
                          '抓取日志第一轮「卷251: FAILED both name forms」窗口(底本卷页不在快照的机器在案凭证——在册外零第二枚;两轮各记一条共恰二条,第二轮此处后继是卷256 FAILED,负证断言)')
WJ_TITLE = slice_between(WJ, '| title    = 春怨{{*|一作伊州歌}}', '一作伊州歌}}',
                         'ws 金页 header title(题面内嵌{{*}}一作伊州歌——题面{{*}}20页闭域;选本侧归属异议独立见证)')
WJ_NOTE = slice_between(WJ, '| notes    ={{Textquality|75%}} ↑ [[全唐詩/卷768#|', '全唐詩·卷768]]',
                        'ws 金页 notes 整值(七五评级+↑底本回指同行——回指目标卷768 在本快照在册,与刘页卷251抓取失败成对照)')
