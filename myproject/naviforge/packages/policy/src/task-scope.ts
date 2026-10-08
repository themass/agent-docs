export type TaskScope = {
  page: 'current' | 'unrestricted'
  navigation: 'forbidden' | 'allowed'
}

const WANTS_WEB_SEARCH =
  /同类型|同类|类似项目|竞品|还有谁|alternatives?|similar (?:to|projects?)|github|gitlab|对比|区别|compare|difference|两个.{0,12}(项目|仓库|库)/i

const SCRIPT_TASK =
  /(?:生成|写|输出|给我).{0,16}(python|py|脚本|scraper|爬虫)|(?:python|py|脚本).{0,24}(抓取|爬取|crawl|scrape|采集)|(?:抓取|爬取).{0,16}(python|脚本)/i

/** Resolve explicit user scope into an execution constraint, not just prompt prose. */
export function resolveTaskScope(task: string): TaskScope {
  if (SCRIPT_TASK.test(task.trim())) {
    return { page: 'unrestricted', navigation: 'allowed' }
  }
  const isCurrentPage = /当前页面|当前页|this page|top\s*\d+|前\s*\d+|找出.*top/i.test(task)
  const explicitlyNavigates =
    /打开|跳转|前往|去热门|排行榜|navigate|go to/i.test(task) || WANTS_WEB_SEARCH.test(task)
  return isCurrentPage && !explicitlyNavigates
    ? { page: 'current', navigation: 'forbidden' }
    : { page: 'unrestricted', navigation: 'allowed' }
}
