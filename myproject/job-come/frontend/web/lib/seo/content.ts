/**
 * The site's indexable content pages, as data.
 *
 * Every one of these routes is server-rendered with real body text — which is the
 * whole point. The product routes (`/resume-agent` and friends) are client workbenches
 * behind auth: a crawler fetches them and sees metadata plus an empty shell, so no
 * amount of metadata on those pages produces a ranking. A guide, by contrast, answers
 * a question somebody types into a search box, and it is the only kind of page here
 * that can rank.
 *
 * Guides live here as data rather than as one route file each on purpose: adding an
 * article becomes a data edit (`app/guides/[slug]/page.tsx` renders any entry, and
 * `app/sitemap.ts` picks it up automatically), so the cost of publishing the tenth
 * guide is the same as the first. Content quality still gates it — see the note on
 * `FAQ` below.
 *
 * Claims in here are checked against the backend, same rule as `/resume-format`:
 * parse support comes from `document_extractor` (PDF/DOCX/TXT natively, images and
 * scanned PDFs through vision, `.doc` classified but empty), output from
 * `resume_render_engine` (PDF/DOCX/HTML, three templates), and the confirmation gate
 * from the profile patch path. Nothing here promises a feature that is not in `src/jc`.
 */

export type GuideSection = {
  heading: string;
  /** Most sections open with prose; bullet-only sections omit it. */
  paragraphs?: string[];
  points?: string[];
};

export type Guide = {
  slug: string;
  /** Search-result title. Keyword phrase leads; the site template appends the brand. */
  title: string;
  description: string;
  keywords: string[];
  /** One-line answer shown above the fold; also reused in the FAQ block when applicable. */
  lead: string;
  sections: GuideSection[];
  /**
   * Phrased the way people actually search, because the question string is what
   * search engines match against. Every answer here must stay visible in the page
   * body — FAQ markup that is not in the body is a structured-data violation.
   */
  faq: { q: string; a: string }[];
  /** Related guide slugs, rendered as cross-links (internal links are how authority moves). */
  related?: string[];
};

export const GUIDES: Guide[] = [
  {
    slug: "why-resume-rejected",
    title: "简历总被刷掉？先看这 12 个内容问题",
    description:
      "简历石沉大海多数不是格式问题，而是内容问题。逐条列出会让筛选者直接放下的写法：只写职责不写结果、时间线矛盾、术语自我声明、技能清单堆砌，以及每一种该怎么改。",
    keywords: ["简历被刷", "简历没回音", "简历筛选", "简历诊断", "简历问题"],
    lead: "简历没有回音，绝大多数时候不是它长得不好看，而是它没有回答筛选者唯一关心的问题：你做成过什么。下面是内容层面最常见的十二个问题，按严重程度排列。",
    sections: [
      {
        heading: "致命问题：会让整份简历失去可信度",
        points: [
          "工作时间线冲突：两段经历的时间重叠，或者项目日期落在公司任职期之外。一处矛盾会被放大成对整份简历真实性的怀疑。",
          "技术栈前后矛盾：技能栏写精通某框架，项目里却找不到任何相关描述。",
          "头衔或数据明显夸大：把参与说成主导、把团队结果写成个人结果。筛选者会在面试里追问细节，追不出来就等于当场否定。",
          "错别字和术语错误成串：这不属于风格问题，它直接说明这份文件有没有被检查过。",
        ],
      },
      {
        heading: "高风险问题：不致命，但让简历停在第二轮",
        points: [
          "所有描述都停留在职责层：「负责订单系统开发和维护」只说明岗位存在，不说明你做得怎样。这是最常见的一条，也是收益最大的一条。",
          "几乎没有量化信息：全篇没有一个数字、比例、范围或变化，筛选者无从判断你的量级。",
          "一堆「精通」而找不到项目证据：技能栏的自我声明不可信，能力要由项目经历反过来证明。",
          "频繁跳槽但没有解释：跳槽本身不是问题，没有交代选择逻辑才是。一句主动说明就能挡掉多数疑虑。",
          "用玩具项目填充经验不足：外卖系统、秒杀系统、商城、博客这类题目不是不能用，而是它们默认缺少真实场景、独特取舍、复杂问题和结果证明。",
        ],
      },
      {
        heading: "低级但显眼的问题",
        points: [
          "个人摘要太长，或者写满「热情、积极、责任心强」这类无法验证的自我评价。摘要的两行要说清定位、年限、方向和最强成果。",
          "格式细节不统一：日期写法、项目名称、列表符号在不同段落之间变化。",
          "简历前半页和目标岗位不对齐：筛选者平均只看几十秒，前半页对不上就很少有第二段阅读。",
        ],
      },
      {
        heading: "改的顺序",
        paragraphs: [
          "不要从排版开始改。先修致命问题（时间线、矛盾、夸大），再处理职责层描述——把每一条经历逼近「业务目标或技术挑战 → 你的关键动作 → 可感知的结果」这条链路，缺数据时明确留一个待补的填写位置，而不是编一个看起来合理的数字。",
          "最后才按目标岗位调整重点顺序和关键词。这一步是重新排序和高亮，不是改写事实。",
        ],
      },
    ],
    faq: [
      {
        q: "简历投了很多都没有回音，是格式问题吗？",
        a: "通常不是。格式影响的是筛选者愿不愿意多看几秒，而内容决定他看完之后要不要约面。先检查有没有只写职责不写结果的描述、有没有时间线矛盾、前半页是否和目标岗位对齐，这三项的影响远大于换模板。",
      },
      {
        q: "简历多久改一次比较合适？",
        a: "不是定期改，而是每次投递前按岗位改。同一份简历投不同岗位时，摘要、技能重点和项目排序应当不同；内容本身只在补齐了新结果时才更新。",
      },
      {
        q: "怎么知道自己简历的问题在哪？",
        a: "自己很难看出来，因为你知道所有背景，而筛选者不知道。可行的办法是找人只看前半页然后复述「这个人做过什么」，或者用工具按岗位逐条审计——重点看它能不能指出具体某一句为什么没有信息量。",
      },
    ],
    related: ["resume-quantification", "outsourcing-experience"],
  },
  {
    slug: "resume-quantification",
    title: "简历里写不出数字怎么办：量化改写的五种降级写法",
    description:
      "「优化了系统性能」这类句子没有信息量，但很多人确实拿不出精确数字。给出可执行的降级路径：用频率、规模、范围、效率变化或风险降低证明价值，以及哪些动词应当替换掉。",
    keywords: ["简历量化", "简历没有数据", "简历成果怎么写", "简历业绩", "简历改写"],
    lead: "「优化了系统性能」是一句零信息量的话。但如果确实拿不出精确数字，正确做法不是编一个，也不是维持原样，而是降级到仍然可验证的证据：频率、规模、范围、效率变化或风险降低。",
    sections: [
      {
        heading: "先换掉四个弱动词",
        paragraphs: [
          "「负责」「参与」「协助」「配合」这四个词描述的是你和工作的关系，不是工作本身。替换成描述动作的词：主导、设计、优化、重构、推动、落地。",
          "每条项目描述至少要说清三件事里的两件：说清了问题、说清了你的动作、说清了结果。三项全满足最好，满足两项就够投递用。",
        ],
      },
      {
        heading: "量化的优先级：从最容易验证到最弱",
        points: [
          "性能类：延迟、吞吐、成功率、可用性、错误率。这类最容易验证，也最容易追问出细节。",
          "业务类：转化率、成交额、留存、订单量、收入、客诉量。",
          "效率类：人天、发布时长、排障时间、交付周期、减少的手工步骤。",
          "规模类：用户数、接口调用量、数据量、覆盖的服务或团队范围。",
          "风险类：事故次数、故障恢复时间、重复问题、误操作概率。",
        ],
      },
      {
        heading: "没有精确数字时的五种降级写法",
        points: [
          "用范围代替点值：「覆盖 20 到 30 个业务接口」比「覆盖多个接口」强得多。",
          "用频率和粒度：高频或低频、分钟级或小时级或天级、单团队或多团队或全公司、核心链路或基础设施。",
          "用状态迁移：从人工到自动化、从无法追踪到全链路可观测、从单点脚本到团队标准流程。这类表述不需要数字，但同样可验证。",
          "用消除的风险：消除了某一类线上问题、把某个环节的故障率压到不再复发。",
          "用建立的产物：可复用的规范、组件、看板、自动化脚本，并说明谁在用。",
        ],
      },
      {
        heading: "一条完整改写的样子",
        paragraphs: [
          "套路是一句话填三个槽：为了〔业务目标或技术挑战〕，我〔关键动作〕，最终带来〔可量化或可感知的结果〕。",
          "例如把「负责订单系统开发」改成：为解决大促期间订单查询缓慢的问题，主导设计并落地基于缓存的查询方案，把平均响应时间从 800ms 降到 120ms，并支撑住峰值流量。如果最后一个数字你确实不知道，就写成「支撑住大促峰值流量（峰值 QPS 待补）」——把空缺留在纸面上，比填一个猜的数字安全得多。",
        ],
      },
    ],
    faq: [
      {
        q: "工作内容太基础，没有任何可量化的东西怎么办？",
        a: "换成状态迁移和风险消除来写：你消除了哪类重复劳动、把哪个手工环节变成自动化、让哪类问题不再复发。如果这些也说不出来，说明这段经历需要的是追问而不是改写——先问清「没有你的这项工作会造成什么问题」，答案往往就是可写的内容。",
      },
      {
        q: "自己估的数字能写吗？",
        a: "只能写你能在面试里解释来源的数字。写了就要能回答「这个数怎么来的、统计口径是什么」。解释不了的数字等于给自己埋一个当场失分的追问，宁可用范围或状态迁移代替。",
      },
    ],
    related: ["why-resume-rejected"],
  },
  {
    slug: "outsourcing-experience",
    title: "外包经历、频繁跳槽、空窗期在简历里怎么写",
    description:
      "这三条在国内投递里会被额外审视。问题通常不在经历本身，而在于没有解释：外包要写清项目价值和职责边界，跳槽要交代选择逻辑，空窗期要简短说明而不长篇自辩。",
    keywords: ["外包经历简历", "外包转正", "频繁跳槽简历", "简历空窗期", "华为 OD"],
    lead: "这三条确实会被额外审视，但被审视的原因很少是经历本身，通常是它没有被解释。筛选者要的是一个能自洽的说法，没有说法时他自己会补一个最差的版本。",
    sections: [
      {
        heading: "外包经历",
        paragraphs: [
          "外包经历不是原罪，真正的问题是项目价值、职责边界和成长路径没讲清楚。写法上有三条原则。",
        ],
        points: [
          "重点写项目，不要放大公司标签。你服务于哪个甲方系统、承担哪部分交付、边界到哪里，比驻场在哪家外包公司重要。",
          "写清你独立负责的部分。「配合甲方团队完成」读起来像在场证明；「承接其中某模块的设计与交付，评审通过并上线」读起来像产出。",
          "如果从外包转到甲方或平台团队，这是正向信号，主动写出来并说明转折的原因，不要等筛选者自己去猜。",
        ],
      },
      {
        heading: "频繁跳槽",
        paragraphs: [
          "判断标准不是次数，而是有没有可复述的逻辑。三段各做一年，如果每次都是明确的能力补齐或方向收敛，读起来是规划；如果只是「平台更好」这种通用理由，读起来是稳定性风险。",
          "做法是用一句话交代主线：这几段分别在补什么能力，现在的目标岗位是这条线的下一步。把解释放在摘要里，比等筛选者在面试里质疑要主动得多。",
        ],
      },
      {
        heading: "空窗期",
        points: [
          "可以简短解释，不要长篇自辩。创业、进修、家庭原因、被裁都写在时间线上即可，一行说明足够。",
          "把空窗期转成积累的证据：期间的证书、系统性学习、独立项目，比任何辩解都有说服力。",
          "不要伪造时间线来填补空窗。时间线冲突是致命问题，一旦被看出，前面所有真实内容都会一起被怀疑。",
        ],
      },
      {
        heading: "玩具项目怎么处理",
        paragraphs: [
          "外卖、秒杀、商城、博客、在线教育平台这类项目在简历里出现的风险不在题目本身，而在于它默认缺少四样东西：真实场景、独特取舍、复杂问题、结果证明。",
          "如果确实只有这类项目可写，就至少拿出一个真实亮点：做过压测和容量设计、处理过限流或缓存或一致性的具体细节、能讲清为什么选这个方案而不是另一个、做完之后带来什么变化。",
        ],
      },
    ],
    faq: [
      {
        q: "外包经历要不要写在简历上？",
        a: "要写，不要隐藏。空出一段时间比外包经历更难看。写法上把重心放在交付的项目和你的职责边界上，并说明后来转向甲方或平台团队的路径。",
      },
      {
        q: "频繁跳槽会被直接筛掉吗？",
        a: "不一定，但没有解释时风险最高。摘要里用一句话交代这几段的选择逻辑，把「不稳定」的默认推断换成「有主线」的读法，比留白让筛选者自己猜要好。",
      },
    ],
    related: ["why-resume-rejected", "mock-interview-preparation"],
  },
  {
    slug: "mock-interview-preparation",
    title: "模拟面试怎么准备：把简历上的每句话讲到能被追问三层",
    description:
      "面试问题几乎都从简历上长出来。可用的准备顺序：对每条经历预设三层追问、补齐写不出来的部分、按岗位练表达、把回答里暴露的问题归档回改简历。",
    keywords: ["模拟面试", "面试准备", "简历追问", "项目深挖", "面试复盘"],
    lead: "面试官的问题几乎全部来自你简历上写下的句子。所以模拟面试的正确用法不是练表达流畅度，而是提前发现简历里哪些话经不起三层追问——那些地方要么在面试前补齐，要么改回能承担的程度。",
    sections: [
      {
        heading: "准备顺序：从简历出发，不从题库出发",
        paragraphs: [
          "题库只解决「没准备过的问题」，但面试里最伤的是「我自己写过却答不出的东西」。先对简历逐条做三层追问演练，再考虑题库。",
        ],
        points: [
          "第一层：这个系统做什么、服务谁、解决什么问题。答不出说明项目缺少上下文，简历上那句「性能提升」也就无法评估含金量。",
          "第二层：为什么选这个方案，另一个方案为什么不行。答不出说明描述里没有你的判断，读起来像任务日志。",
          "第三层：这个结果怎么测的、口径是什么、有没有反例。答不出说明数字不可靠，下次别再写。",
        ],
      },
      {
        heading: "回答结构里的一个常被漏掉的槽位",
        paragraphs: [
          "讲技术方案时，多数人停在「我评估了 A 和 B，选了 A，效果好」。 senior 和 junior 的差别常常在中间那一个槽位：选 A 之后你用什么措施控制它带来的风险。",
          "完整的一句是：为解决〔问题〕，评估了〔方案 A〕与〔方案 B〕，选择〔A〕因为〔理由〕，并通过〔补偿措施〕控制风险，最终〔结果〕。这个槽位同时也标出了面试官下一步会追问的地方。",
        ],
      },
      {
        heading: "把面试结果回灌到简历",
        paragraphs: [
          "一次模拟面试的价值不在分数，在问题清单。哪条经历被追问卡住、哪个数字说不清来源、哪个项目讲不清上下文——这三类问题直接对应简历上要改的三处。",
          "所以下一轮准备的顺序应该是：先按面试暴露的问题改简历，再针对改后的版本重新练。只刷题库而不改简历，下次还是在同一个地方卡住。",
        ],
      },
    ],
    faq: [
      {
        q: "模拟面试有作用吗，还是只是走个流程？",
        a: "有用的前提是它按你的简历出题，并且结束后给出具体哪句话被追问卡住。按通用题库出题的模拟练习只能练表达，练不出简历里的问题。",
      },
      {
        q: "面试前多久开始准备比较合适？",
        a: "投递前就该开始，而不是拿到面试通知之后。理想节奏是每次投递前用目标岗位做一轮模拟，把卡住的地方改回简历里；面试前一天只练口头表达，不再改内容。",
      },
    ],
    related: ["resume-quantification"],
  },
];

export const guideBySlug = new Map(GUIDES.map((g) => [g.slug, g]));

/** Absolute URL for a guide, for canonical links and breadcrumbs. */
export function guideUrl(slug: string): string {
  return `/guides/${slug}`;
}
