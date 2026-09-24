import type { DeepSpacePoi } from "../types";

export const deepSpacePois: DeepSpacePoi[] = [
  {
    id: "smacs-0723",
    name: "SMACS 0723 深场",
    englishName: "SMACS 0723",
    kind: "deep-field",
    distance: "约 46 亿光年（星系团光行时；背景星系更远）",
    coordinates: "RA 07h 23m, Dec -73° 27′（近似）",
    sourceMission: "JWST / NASA / ESA / CSA / STScI",
    archive: [
      {
        name: "MAST JWST archive",
        url: "https://archive.stsci.edu/",
        note: "JWST public observation products and metadata.",
      },
      {
        name: "NASA Webb First Images",
        url: "https://webb.nasa.gov/content/webbLaunch/whereIsWebb.html",
        note: "Public outreach imagery and explanatory materials.",
      },
    ],
    whyItMatters:
      "JWST 首批深场之一，展示了引力透镜和早期宇宙中极遥远星系。",
    visualizationPlan:
      "使用真实 JWST 图像作为深场 billboard，叠加引力透镜 arcs 和可点击红移标签。",
    observationFacts: [
      "这是星系团及其背景星系的观测图像。",
      "弧形结构来自星系团引力透镜效应。",
      "多波段红外数据被映射到可见色彩。",
    ],
    artisticEnhancements: [
      "3D 景深、星系云和飞船接近动画是可视化增强。",
      "真实红移距离与视觉层次并非一一等距映射。",
    ],
    color: "#9ab7ff",
  },
  {
    id: "carina-nebula",
    name: "船底座星云 Cosmic Cliffs",
    englishName: "Carina Nebula / Cosmic Cliffs",
    kind: "nebula",
    distance: "约 7,600 光年",
    coordinates: "NGC 3324, Carina",
    sourceMission: "JWST / Hubble",
    archive: [
      {
        name: "MAST HST/JWST",
        url: "https://archive.stsci.edu/",
        note: "Query JWST and HST observations for Carina Nebula regions.",
      },
    ],
    whyItMatters:
      "JWST 首批代表图像之一，展示恒星形成区尘埃边界和年轻恒星。",
    visualizationPlan:
      "真实 JWST 图像作地形化星云墙，近景用分层云片和粒子表现尘埃边缘。",
    observationFacts: [
      "近红外观测穿透尘埃，显示大量年轻恒星。",
      "图像颜色为多波段 false-color 合成。",
    ],
    artisticEnhancements: [
      "山脊深度、云层穿越和飞船尺度是艺术化增强。",
    ],
    color: "#ffb36b",
  },
  {
    id: "eagle-nebula",
    name: "创生之柱 / 鹰状星云 M16",
    englishName: "Pillars of Creation / Eagle Nebula",
    kind: "nebula",
    distance: "约 6,500 光年",
    coordinates: "M16, Serpens",
    sourceMission: "Hubble + JWST",
    archive: [
      {
        name: "Hubble Legacy Archive / MAST",
        url: "https://hla.stsci.edu/",
        note: "Classic visible-light Hubble products.",
      },
      {
        name: "MAST JWST",
        url: "https://archive.stsci.edu/",
        note: "JWST infrared observations for comparison mode.",
      },
    ],
    whyItMatters:
      "最经典的 Hubble 图像之一，JWST 版本能展示红外视角下的尘埃与恒星形成。",
    visualizationPlan:
      "Hubble/Webb 双波段切换；近景使用柱状体积云和背光恒星。",
    observationFacts: [
      "柱体是冷分子气体和尘埃区域。",
      "Hubble 与 Webb 看到的是不同波段下的同一区域。",
    ],
    artisticEnhancements: [
      "柱体厚度和可穿越空间是重建效果，不代表直接观测的 3D 几何。",
    ],
    color: "#f2b15f",
  },
  {
    id: "stephans-quintet",
    name: "斯蒂芬五重星系",
    englishName: "Stephan's Quintet",
    kind: "galaxy-group",
    distance: "约 2.9 亿光年（主要相互作用成员）",
    coordinates: "Pegasus",
    sourceMission: "JWST + Hubble",
    archive: [
      {
        name: "MAST HST/JWST",
        url: "https://archive.stsci.edu/",
        note: "Multi-mission observation products for Stephan's Quintet.",
      },
    ],
    whyItMatters:
      "展示星系相互作用、潮汐尾、激波和恒星形成，是解释星系演化的好目标。",
    visualizationPlan:
      "多层星系 billboard，潮汐尾用粒子带表示，面板解释其中一个星系为前景星系。",
    observationFacts: [
      "可见五个星系，但并非全部处于同一真实距离。",
      "相互作用星系中的气体和恒星形成被 JWST 红外数据揭示。",
    ],
    artisticEnhancements: [
      "星系间距离被压缩，潮汐结构粒子是讲解用可视化。",
    ],
    color: "#ffd5a3",
  },
  {
    id: "sagittarius-a",
    name: "人马座 A*",
    englishName: "Sagittarius A*",
    kind: "black-hole",
    distance: "约 26,000 光年",
    coordinates: "银河系中心，人马座方向",
    sourceMission: "EHT / NASA / ESO / Chandra / Hubble context",
    archive: [
      {
        name: "Event Horizon Telescope",
        url: "https://eventhorizontelescope.org/",
        note: "Black hole ring observation source.",
      },
      {
        name: "NASA Galactic Center resources",
        url: "https://www.nasa.gov/",
        note: "Context imagery and explanations for the Galactic Center.",
      },
    ],
    whyItMatters:
      "银河系中心超大质量黑洞，连接太阳系在银河中的位置与更大尺度宇宙结构。",
    visualizationPlan:
      "简化吸积盘、屏幕空间透镜和星场扭曲；科学面板强调这是模拟可视化。",
    observationFacts: [
      "EHT 观测到的是毫米波下的黑洞阴影附近结构。",
      "银河中心位置可由多波段观测共同约束。",
    ],
    artisticEnhancements: [
      "吸积盘亮度、飞船近距离视角和实时透镜均为艺术化重建。",
    ],
    color: "#ff7b42",
  },
];

export const deepSpaceById = new Map(deepSpacePois.map((poi) => [poi.id, poi]));
