import assert from 'node:assert/strict'

import {
  dominantPathPrefix,
  extractContent,
  pathToRecordSelector,
  profileFor,
  proposeProfile,
  resolveRecordHref,
  urlPattern,
  type Candidate,
  type SiteProfile,
} from './content-extract.js'

function card(input: Partial<Candidate> & { index: number; path: string }): Candidate {
  return {
    tag: 'a',
    texts: [],
    linkTexts: [],
    hasMedia: true,
    inChrome: false,
    inBanner: false,
    visible: true,
    rect: { top: input.index * 100, left: 0, width: 220, height: 140 },
    ...input,
  }
}

// --- url shape generalization -----------------------------------------------

assert.equal(urlPattern('/video/BV1H7M26dEEA', 'https://www.bilibili.com'), 'www.bilibili.com/video/*')
assert.equal(
  urlPattern('/blackboard/era/activity.html', 'https://www.bilibili.com'),
  'www.bilibili.com/blackboard/era/activity.html'
)
assert.equal(urlPattern('/watch?v=abc123', 'https://www.youtube.com'), 'www.youtube.com/watch?v')
assert.equal(urlPattern('/item/728391.html', 'https://shop.example.com'), 'shop.example.com/item/*')

assert.equal(
  resolveRecordHref('/login?return_to=%2Fmsitarzewski%2Fagency-agents', 'https://github.com'),
  'https://github.com/msitarzewski/agency-agents'
)

// --- video feed: promo banner and activity outlier must not become TOP1 -----

const feedPath = 'div.feed>div.card>a'
const videoFeed: Candidate[] = [
  card({
    index: 1,
    path: 'div.header>div.nav>a',
    href: '/v/popular',
    texts: ['热门'],
    inChrome: true,
    hasMedia: false,
  }),
  card({
    index: 2,
    path: 'div.banner>div.slot>a',
    href: '/video/BV1Promo000',
    texts: ['限时活动 领取会员'],
    inBanner: true,
  }),
  card({
    index: 3,
    path: feedPath,
    href: '/blackboard/era/activity.html',
    texts: ['春季创作激励计划'],
  }),
  card({
    index: 4,
    path: feedPath,
    href: '/video/BV1H7M26dEEA',
    label: '稍后再看',
    texts: ['[87]<a >三分钟看懂扩散模型 />', '三分钟看懂扩散模型', '12:04', '18.6万', 'AI 研究所'],
    linkTexts: ['AI 研究所'],
  }),
  card({
    index: 5,
    path: feedPath,
    href: '/video/BV1gKuF6rEqy',
    texts: ['从零实现一个浏览器 Agent', '24:31', '9.2万'],
    linkTexts: ['码农小林'],
  }),
  card({ index: 6, path: feedPath, href: '/video/BV1aa111111', texts: ['第三个视频标题', '08:12'] }),
  card({ index: 7, path: feedPath, href: '/video/BV1bb222222', texts: ['第四个视频标题', '05:40'] }),
  card({ index: 8, path: feedPath, href: '/video/BV1cc333333', texts: ['第五个视频标题', '11:03'] }),
  card({ index: 9, path: feedPath, href: '/video/BV1dd444444', texts: ['第六个视频标题', '03:22'] }),
]

const bili = extractContent(videoFeed, { url: 'https://www.bilibili.com/', n: 4 })
assert.equal(bili.strategy, 'profile')
assert.equal(bili.profileId, 'bilibili-video')
assert.deepEqual(
  bili.items.map((item) => item.title),
  ['三分钟看懂扩散模型', '从零实现一个浏览器 Agent', '第三个视频标题', '第四个视频标题'],
  'banner, nav and activity links are excluded; placeholder label falls back to card text'
)
assert.equal(bili.items[0]?.url, 'https://www.bilibili.com/video/BV1H7M26dEEA')
assert.equal(bili.items[0]?.fields.duration, '12:04')
assert.equal(bili.items[0]?.fields.views, '18.6万')
assert.equal(bili.items[0]?.fields.author, 'AI 研究所')

// Label/views must never win over a real title in the card text pool.
const metricLabel = extractContent(
  [
    card({
      index: 1,
      path: feedPath,
      href: '/video/BV1metricTitle1',
      label: '18.6万',
      texts: ['18.6万', '真正的视频标题不应该被播放量盖住', '12:04'],
    }),
    card({
      index: 2,
      path: feedPath,
      href: '/video/BV1metricTitle2',
      label: '9.2万播放',
      texts: ['另一条正常标题', '08:00', '9.2万播放'],
    }),
  ],
  { url: 'https://www.bilibili.com/', n: 2 }
)
assert.equal(metricLabel.items[0]?.title, '真正的视频标题不应该被播放量盖住')
assert.equal(metricLabel.items[1]?.title, '另一条正常标题')

// Bare integers (danmaku/likes) must not become the title.
const danmakuAsTitle = extractContent(
  [
    card({
      index: 1,
      path: feedPath,
      href: '/video/BV1danmakuCount1',
      texts: ['1821', '118.3万', '03:19', '真正该显示的视频名字'],
    }),
    card({
      index: 2,
      path: feedPath,
      href: '/video/BV1danmakuCount2',
      texts: ['2812', '68.8万', '14:36'],
    }),
  ],
  { url: 'https://www.bilibili.com/', n: 2 }
)
assert.equal(danmakuAsTitle.items[0]?.title, '真正该显示的视频名字')
assert.equal(danmakuAsTitle.items[0]?.fields.count, '1821')
assert.match(danmakuAsTitle.items[1]?.title ?? '', /未命名 · BV1danmakuCount2/)

// The same page without any site profile must reach the same answer by
// induction alone — this is what makes the bilibili fix reusable.
const induced = extractContent(videoFeed, { url: 'https://video.example.com/', n: 4 })
assert.equal(induced.strategy, 'induced')
assert.deepEqual(
  induced.items.map((item) => item.title),
  ['三分钟看懂扩散模型', '从零实现一个浏览器 Agent', '第三个视频标题', '第四个视频标题'],
  'dominant link shape drops the activity outlier without site knowledge'
)

// --- shortfall is reported, never padded ------------------------------------

const short = extractContent(videoFeed, { url: 'https://video.example.com/', n: 20 })
assert.equal(short.found, 6)
assert.match(short.shortfall ?? '', /仅找到 6\/20/)

// --- movie site --------------------------------------------------------------

const moviePath = 'div.list>li.item>a'
const movies = extractContent(
  [
    card({
      index: 1,
      path: moviePath,
      href: '/detail/91827',
      texts: ['星际穿越', '2014', '9.4', '科幻'],
    }),
    card({
      index: 2,
      path: moviePath,
      href: '/detail/91828',
      texts: ['三体 第二季', '更新至第12集', '8.7'],
    }),
    card({ index: 3, path: moviePath, href: '/detail/91829', texts: ['沙丘', '2021', '8.0'] }),
    card({ index: 4, path: moviePath, href: '/detail/91830', texts: ['奥本海默', '2023', '8.9'] }),
  ],
  { url: 'https://movie.example.com/', n: 3 }
)
assert.deepEqual(
  movies.items.map((item) => item.title),
  ['星际穿越', '三体 第二季', '沙丘']
)
assert.equal(movies.items[0]?.fields.rating, '9.4')
assert.equal(movies.items[0]?.fields.date, '2014')
assert.equal(movies.items[1]?.fields.episode, '更新至第12集')

// --- e-commerce grid ---------------------------------------------------------

const shopPath = 'div.grid>div.sku>a'
const shop = extractContent(
  [
    card({
      index: 1,
      path: shopPath,
      href: '/item/728391.html',
      texts: ['机械键盘 87 键 客制化', '¥399.00', '4.9'],
      linkTexts: ['极客数码旗舰店'],
    }),
    card({
      index: 2,
      path: shopPath,
      href: '/item/728392.html',
      texts: ['人体工学椅 网布透气', '¥1299.00'],
      linkTexts: ['家居优选'],
    }),
    card({ index: 3, path: shopPath, href: '/item/728393.html', texts: ['4K 显示器 27 英寸', '¥2099.00'] }),
  ],
  { url: 'https://shop.example.com/', n: 2 }
)
assert.equal(shop.items[0]?.fields.price, '¥399.00')
assert.equal(shop.items[0]?.fields.author, '极客数码旗舰店')
assert.equal(shop.items[0]?.title, '机械键盘 87 键 客制化')

// --- news list ---------------------------------------------------------------

const newsPath = 'div.news>div.row>a'
const news = extractContent(
  [
    card({
      index: 1,
      path: newsPath,
      href: '/article/20260810123',
      texts: ['某国宣布下调基准利率 25 个基点', '2小时前'],
      linkTexts: ['财经日报'],
      hasMedia: false,
    }),
    card({
      index: 2,
      path: newsPath,
      href: '/article/20260810124',
      texts: ['新一代模型发布，推理成本下降四成', '5小时前'],
      linkTexts: ['科技前线'],
      hasMedia: false,
    }),
    card({
      index: 3,
      path: newsPath,
      href: '/article/20260810125',
      texts: ['城市轨道交通新线开通运营', '2026-08-10'],
      hasMedia: false,
    }),
  ],
  { url: 'https://news.example.com/', n: 3 }
)
assert.equal(news.items[0]?.fields.date, '2小时前')
assert.equal(news.items[0]?.fields.author, '财经日报')
assert.equal(news.items[2]?.fields.date, '2026-08-10')

// --- youtube-style feed ------------------------------------------------------

const ytPath = 'div.contents>ytd-rich-item-renderer>a'
const youtube = extractContent(
  [
    card({
      index: 1,
      path: ytPath,
      href: '/watch?v=dQw4w9WgXcQ',
      label: 'Building a browser agent from scratch',
      texts: ['Building a browser agent from scratch', '18:42', '1.2M views', '3 days ago'],
      linkTexts: ['Agent Lab'],
    }),
    card({
      index: 2,
      path: ytPath,
      href: '/watch?v=abc123def45',
      texts: ['Diffusion models explained', '24:10', '840K views'],
      linkTexts: ['ML Weekly'],
    }),
    card({
      index: 3,
      path: ytPath,
      href: '/watch?v=zzz999yyy88',
      texts: ['Rust for TypeScript developers', '31:07'],
      linkTexts: ['Systems Corner'],
    }),
  ],
  { url: 'https://www.youtube.com/', n: 2 }
)
assert.equal(youtube.strategy, 'induced', 'youtube needs no bundled profile')
assert.equal(youtube.items[0]?.title, 'Building a browser agent from scratch')
assert.equal(youtube.items[0]?.fields.duration, '18:42')
assert.equal(youtube.items[0]?.fields.views, '1.2M views')
assert.equal(youtube.items[0]?.fields.date, '3 days ago')
assert.equal(youtube.items[0]?.fields.author, 'Agent Lab')

// --- learning loop: induce → propose → reuse ---------------------------------

const learned = proposeProfile('https://video.example.com/', induced)
assert.equal(learned?.id, 'learned-video.example.com')
assert.equal(learned?.detailUrl, '/video/[^/]+')
assert.equal(learned?.source, 'learned')
assert.equal(learned?.record, 'div.feed>div.card')
assert.ok(learned?.exclude?.includes('banner'), 'learned profile carries a generic exclude')

assert.equal(
  dominantPathPrefix(videoFeed.filter((item) => item.path === feedPath).map((item) => item.path)),
  'div.feed>div.card'
)
assert.equal(pathToRecordSelector(feedPath), 'div.feed>div.card')

// The proposal must actually work as a profile on the next visit.
const reused = extractContent(videoFeed, {
  url: 'https://video.example.com/',
  n: 4,
  profiles: [learned as SiteProfile],
})
assert.equal(reused.strategy, 'profile')
assert.equal(reused.profileId, 'learned-video.example.com')
assert.deepEqual(
  reused.items.map((item) => item.title),
  induced.items.map((item) => item.title),
  'a learned profile reproduces what induction found'
)

// A stale profile must never starve the result on a sibling page.
const stale = extractContent(videoFeed, {
  url: 'https://video.example.com/',
  n: 4,
  profiles: [{ ...(learned as SiteProfile), detailUrl: '/gone/[^/]+' }],
})
assert.equal(stale.strategy, 'induced', 'a profile matching nothing falls back to induction')
assert.equal(stale.items.length, 4)

const bundledStarve = extractContent(videoFeed, {
  url: 'https://movie.douban.com/top250',
  n: 3,
  profiles: [
    {
      id: 'douban-movie',
      host: ['douban.com'],
      detailUrl: '/subject/\\d+',
      record: '.missing-grid',
      source: 'bundled',
    },
  ],
})
assert.equal(bundledStarve.found, 0, 'bundled profile mismatch returns shortfall, not unfiltered nav')

assert.equal(
  proposeProfile('https://www.bilibili.com/', bili),
  undefined,
  'a profile-driven run never re-learns itself'
)
assert.equal(
  proposeProfile('https://news.example.com/', news),
  undefined,
  'a 3-record group is too thin to learn from'
)
assert.equal(
  proposeProfile('https://movie.example.com/', movies)?.detailUrl,
  '/detail/[^/]+'
)

// --- profile resolution ------------------------------------------------------

assert.equal(profileFor('https://www.bilibili.com/')?.id, 'bilibili-video')
assert.equal(profileFor('https://space.bilibili.com/1')?.id, 'bilibili-video')
assert.equal(profileFor('https://movie.douban.com/top250')?.id, 'douban-movie')
assert.equal(profileFor('https://github.com/trending')?.id, 'github-repo')
assert.equal(profileFor('https://github.com/duongductrong/Snapzy'), undefined, 'repo home skips list profile')
assert.equal(profileFor('https://www.bbc.com/news')?.id, 'bbc-news')
assert.equal(profileFor('https://notbilibili.com/'), undefined)
assert.equal(profileFor('not a url'), undefined)

const githubTrending = extractContent(
  [
    card({
      index: 1,
      path: 'article>h2>a',
      href: '/login?return_to=%2Fmsitarzewski%2Fagency-agents',
      texts: ['agency-agents'],
      hasMedia: false,
    }),
    card({
      index: 2,
      path: 'article>h2>a',
      href: '/login?return_to=%2Fsemantica-agi%2Fsemantica',
      texts: ['semantica'],
      hasMedia: false,
    }),
    card({
      index: 3,
      path: 'article>h2>a',
      href: '/login?return_to=%2Fnvm-sh%2Fnvm',
      texts: ['nvm'],
      hasMedia: false,
    }),
    card({
      index: 4,
      path: 'article>h2>a',
      href: '/login?return_to=%2Faddyosmani%2Fagent-skills',
      texts: ['agent-skills'],
      hasMedia: false,
    }),
  ],
  { url: 'https://github.com/trending', n: 3 }
)
assert.equal(githubTrending.strategy, 'profile')
assert.equal(githubTrending.items[0]?.url, 'https://github.com/msitarzewski/agency-agents')

const doubanNav = extractContent(
  [
    card({
      index: 1,
      path: 'div#db-global-nav>div>div>div>a',
      href: 'https://www.douban.com/',
      texts: ['豆瓣'],
      hasMedia: false,
    }),
    card({
      index: 2,
      path: 'ol.grid-view>li>div>div>a',
      href: '/subject/1292052/',
      texts: ['肖申克的救赎', '9.7'],
      hasMedia: true,
    }),
    card({
      index: 3,
      path: 'ol.grid-view>li>div>div>a',
      href: '/subject/1291546/',
      texts: ['霸王别姬', '9.6'],
      hasMedia: true,
    }),
    card({
      index: 4,
      path: 'ol.grid-view>li>div>div>a',
      href: '/subject/1292720/',
      texts: ['阿甘正传', '9.5'],
      hasMedia: true,
    }),
  ],
  { url: 'https://movie.douban.com/top250', n: 3 }
)
assert.equal(doubanNav.strategy, 'profile')
assert.deepEqual(
  doubanNav.items.map((item) => item.title),
  ['肖申克的救赎', '霸王别姬', '阿甘正传']
)

// --- vod aggregator: external CPA promos must lose to same-origin /vod/view/ ---

const vodPath = 'div.list>div.item>a'
const vodFeed: Candidate[] = [
  card({
    index: 1,
    path: 'div.banner>a',
    href: 'https://vluydzksoneb.xn--e-q07as6t.com:9595/?blt021',
    texts: ['🔥PG电子爆款福利,注册即送888元🔥', '🔥开元棋牌🔥澳门官方送8888元'],
  }),
  card({
    index: 2,
    path: 'div.banner>a',
    href: 'https://47.47137278.vip/?cid=5318700',
    texts: ['🔥PG电子爆款福利,注册即送888元🔥'],
  }),
  card({
    index: 3,
    path: vodPath,
    href: '/vod/view/AAA',
    texts: ['真实视频一', '00:12:34', '高清'],
  }),
  card({
    index: 4,
    path: vodPath,
    href: '/vod/view/BBB',
    texts: ['真实视频二', '00:08:21', '高清'],
  }),
  card({
    index: 5,
    path: vodPath,
    href: '/vod/view/CCC',
    texts: ['真实视频三', '00:15:02', '高清'],
  }),
]
const vodResult = extractContent(vodFeed, { url: 'https://rfd0i4.jstv800.com/vod', n: 4 })
assert.equal(vodResult.strategy, 'induced')
assert.deepEqual(vodResult.items.map((item) => item.title), ['真实视频一', '真实视频二', '真实视频三'])
assert.ok(vodResult.items.every((item) => item.url?.includes('/vod/view/')))
assert.ok(vodResult.items.every((item) => !/PG电子|开元棋牌/.test(item.title)))

console.log('content-extract self-check ok')
