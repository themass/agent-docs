import assert from 'node:assert/strict'

import {
  isCatalogCrawlTask,
  isSiteCatalogSopTask,
  parallelSubtaskGuidanceNotes,
  requestedList,
  shouldHintParallelSubtasks,
} from './task-classifier.js'

assert.equal(requestedList('抓取每个分类的前2页的所有视频'), null, '前N页 is not top-N list')
assert.equal(requestedList('分析这个网站的所有视频分类地址，抓取每个分类的前2页'), null)
assert.deepEqual(requestedList('提取前5个视频名称'), { n: 5, mark: false })

assert.ok(
  isCatalogCrawlTask('分析这个网站的所有视频分类地址，我想要抓取每个分类的前2页的所有视频的名称和播放地址')
)
assert.ok(isCatalogCrawlTask('抓取所有博客栏目前3页的文章标题'))
assert.ok(!isCatalogCrawlTask('提取前5个视频名称'))

assert.ok(
  isSiteCatalogSopTask('抓取当前页面下所有的视频源地址和名称'),
  'catalog SOP not parallel fragment'
)
assert.ok(shouldHintParallelSubtasks('抓取当前页面下所有的视频源地址和名称'))
assert.ok(parallelSubtaskGuidanceNotes('抓取当前页面下所有的视频源地址和名称').some((l) => l.includes('mediaUrl')))
assert.ok(!isSiteCatalogSopTask('介绍当前页面是做什么的'))

console.log('task-classifier self-check ok')
