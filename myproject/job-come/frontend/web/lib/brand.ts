/** User-facing product assistant name (JobCome → 舟卡). */
export const ZHOUKA_NAME = "舟卡";

/** Avatar mark in the agent chrome (JC = JobCome / 舟卡). */
export const PRODUCT_MARK = "JC";

/** Product naming — keep tab titles short; put features in meta description. */
export const PRODUCT_NAME = "舟卡";
export const PRODUCT_NAME_EN = "JobCome";

/** Browser tab: brand lockup only (no feature laundry list). */
export const DOCUMENT_TITLE = `${PRODUCT_NAME} · ${PRODUCT_NAME_EN}`;

/** Inner routes: `简历优化 · 舟卡` via Next `title.template`. */
export const DOCUMENT_TITLE_TEMPLATE = `%s · ${PRODUCT_NAME}`;

/** Auth / hero eyebrow — emotional, matches 舟 (voyage) brand. */
export const PRODUCT_TAGLINE = "走好下一段职业航程";

/** SEO, link previews — capabilities belong here. */
export const DOCUMENT_DESCRIPTION =
  "舟卡（JobCome）帮助知识工作者整理职业档案、优化简历、匹配岗位、模拟面试与复盘，从容走向下一份更好的工作。";

/** "关于" page copy and contact info. */
export const ABOUT_COMPANY_NAME = "sspacee";
export const ABOUT_COMPANY_INTRO =
  "舟卡（JobCome）是 sspacee 打造的专业简历优化官：帮你梳理职业经历、按岗位重新包装表达、对齐目标公司的招聘语言，陪你把每一次投递都准备到位，剑指 Offer。";
export const ABOUT_CONTACT_EMAIL = "justbegin010@gmail.com";
export const ABOUT_CONTACT_EXTRA: string | null = null; // 可选：客服电话 / 工作时间 / 公司地址等
