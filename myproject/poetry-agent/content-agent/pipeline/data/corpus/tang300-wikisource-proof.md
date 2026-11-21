# 三百首 × 维基文库《全唐詩》逐字复核

- 快照目录 /tmp/src-dl/quantangshi；转引用子页未抓取（加 --fetch-children 再跑）

| 档 | 数量 |
|---|---|
| TRANSCLUDE | 151 |
| WS_MISS | 120 |
| WS_RAW_EXACT | 30 |
| WS_VARIANT | 29 |
| NOT_FETCHED | 28 |
| WS_FOLD_EXACT | 8 |

WS_RAW_EXACT = 与维基文库正文码位逐字一致（独立转录，真·第二证过）；
WS_FOLD_EXACT = 折叠异体字后一致（异体差异保留登记，入库正文以本页为准）；
WS_VARIANT = 找到同一诗但真异文，逐条看；TRANSCLUDE = 卷页是转引用壳，还没抓子页；
NOT_FETCHED = 映射卷的快照还没抓到；
WS_MISS = 映射卷里没这首诗（含御定卷号错记、本地无卷号两类）——加 --search 按正文检索真页重判。
