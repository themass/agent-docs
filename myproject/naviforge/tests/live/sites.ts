import type { LiveSiteCase } from './assertions.js'

const COMMON_CONTROLS =
  /^(首页|热门|登录|注册|菜单|更多|全部|收藏|分享|举报|稍后再看|home|menu|more|login|sign in|save|share|report|watch later|more actions?)$/i

export const P0_LIVE_SITES: LiveSiteCase[] = [
  {
    id: 'bilibili-knowledge',
    name: 'Bilibili 知识频道',
    url: 'https://www.bilibili.com/c/knowledge/',
    detailUrl: /bilibili\.com\/video\//,
    forbiddenTitle: COMMON_CONTROLS,
    expected: 5,
    waitMs: 5_000,
  },
  {
    id: 'youtube-search',
    name: 'YouTube 搜索结果',
    url: 'https://www.youtube.com/results?search_query=browser+agent',
    detailUrl: /youtube\.com\/watch\?/,
    forbiddenTitle: COMMON_CONTROLS,
    expected: 5,
    waitMs: 8_000,
  },
  {
    id: 'douban-top250',
    name: '豆瓣电影 Top 250',
    url: 'https://movie.douban.com/top250',
    detailUrl: /movie\.douban\.com\/subject\//,
    forbiddenTitle: COMMON_CONTROLS,
    expected: 5,
    waitMs: 3_000,
  },
  {
    id: 'github-trending',
    name: 'GitHub Trending',
    url: 'https://github.com/trending',
    detailUrl: /github\.com\/[^/]+\/[^/?#]+\/?$/,
    forbiddenTitle: COMMON_CONTROLS,
    expected: 5,
    waitMs: 4_000,
  },
  {
    id: 'hacker-news',
    name: 'Hacker News',
    url: 'https://news.ycombinator.com/',
    detailUrl: /^https?:\/\//,
    forbiddenTitle:
      /^(new|past|comments|ask|show|jobs|submit|login|more|next|user|hide|discuss)$/i,
    expected: 5,
  },
  {
    id: 'steam-top-sellers',
    name: 'Steam 畅销商品',
    url: 'https://store.steampowered.com/search/?filter=topsellers',
    detailUrl: /store\.steampowered\.com\/app\//,
    forbiddenTitle: COMMON_CONTROLS,
    expected: 5,
    waitMs: 4_000,
  },
  {
    id: 'bbc-news',
    name: 'BBC News',
    url: 'https://www.bbc.com/news',
    detailUrl: /bbc\.com\/news\/(articles|videos|live)\//,
    forbiddenTitle: COMMON_CONTROLS,
    expected: 5,
    waitMs: 3_000,
  },
]

export function selectedLiveSites(filter = process.env.NAVIFORGE_LIVE_SITES): LiveSiteCase[] {
  if (!filter) return P0_LIVE_SITES
  const ids = new Set(filter.split(',').map((item) => item.trim()).filter(Boolean))
  return P0_LIVE_SITES.filter((site) => ids.has(site.id))
}
