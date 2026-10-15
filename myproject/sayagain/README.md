# SayAgain 文档中心

SayAgain 是面向全年龄段学习者的主题化英语教学产品。当前首发先验证“主题学词”教学闭环：原创风格化 3D 动漫学习伙伴 Milo 通过情境、指向、动作、听说读写练习、亲子陪伴和受控挑战，帮助学习者从理解和识别逐步走向简单使用。

> 本目录是产品、教学、设计和研究文档，不是运行时代码目录。

## 先读这三份

1. [当前决策](./00-overview/DECISIONS.md)：已经确认的产品边界，防止历史讨论干扰当前判断。
2. [教学框架](./01-education/EDU-TEACHING-FRAMEWORK-v0.2.md)：能力分层、教学原则、Milo 职责、亲子和 PK 边界。
3. [移动端 MVP PRD](./02-product/PRD-MOBILE-MVP-v0.2.md)：首发产品范围、流程、功能和验收标准。

## 文档地图

| 目录 | 类型 | 当前用途 |
|---|---|---|
| `00-overview/` | 总览/决策/路线 | 产品方向、版本路线、决策记录 |
| `01-education/` | 教学/课程 | 教学方法、能力层、课程大纲、单元脚本 |
| `02-product/` | 产品/PRD | 产品结构、需求和内容模型 |
| `03-design/` | 设计/原型 | UI 规范、原型说明、可点击原型 |
| `04-engineering/` | 技术 | 当前预留；教研和试学通过后建立技术方案 |
| `05-research/` | 研究 | 竞品、APK 静态研究和开源参考 |
| `06-planning/` | 计划 | 阶段计划、交付顺序和责任 |
| `99-templates/` | 模板 | 新增课程单元和活动的模板 |
| `90-archive/` | 历史 | 闲聊、探索稿和旧 PRD，不作为当前基线 |

## 当前有效文档

### 教学与课程

- [教学总纲](./01-education/EDU-TEACHING-FRAMEWORK-v0.2.md)
- [课程框架](./01-education/EDU-CURRICULUM-FRAMEWORK-v0.1.md)
- [教学方法论研究](./01-education/EDU-TEACHING-RESEARCH-v0.1.md)
- [课程路线图](./01-education/EDU-CURRICULUM-ROADMAP-v0.1.md)
- [A0《我的脸》教案](./01-education/units/UNIT-BODY-FACE-SCRIPT-v0.1.md)
- [A0 内容对象](./01-education/units/UNIT-BODY-FACE-CONTENT-v0.1.md)
- [A0 资产清单](./01-education/units/UNIT-BODY-FACE-ASSETS-v0.1.md)

### 产品与设计

- [移动端 MVP PRD](./02-product/PRD-MOBILE-MVP-v0.2.md)
- [产品结构](./02-product/PRODUCT-STRUCTURE-v0.1.md)
- [原型规格](./03-design/DESIGN-PROTOTYPE-SPEC-v0.1.md)
- [设计系统](./03-design/DESIGN-SYSTEM-v0.1.md)
- [可点击原型](./03-design/prototype/index.html)

### 研究与计划

- [百词斩静态研究](./05-research/baicizhan/RESEARCH-BAICIZHAN-REVERSE-ANALYSIS-v0.1.md)
- [开源 Android 参考](./05-research/RESEARCH-OPEN-SOURCE-ANDROID-v0.1.md)
- [教学产品实施计划](./06-planning/PLAN-DELIVERY-v0.1.md)

## 下一步

先评审 A0《我的脸》和教学框架，再编写 B1《找一找动物》；两者通过后重做原型，组织家庭试学，最后进入技术选型和方案设计。

## 命名规范

新文档使用：`TYPE-DESCRIPTIVE-NAME-vX.Y.md`。

- `EDU` 教学；`PRD` 需求；`PRODUCT` 产品结构；`DESIGN` 设计；`ENG` 技术；`RESEARCH` 研究；`PLAN` 计划；`DISCUSSION` 讨论。
- `v0.x` 草稿/评审；`v1.0` 冻结基线；文档正文使用中文，文件名使用英文和稳定 ASCII。
- 每份主文档开头标注状态、日期、上游文档和是否为当前事实源。
