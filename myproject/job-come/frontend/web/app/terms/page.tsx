import type { Metadata } from "next";

import { LegalDocument, type LegalSection } from "@/components/legal/LegalDocument";
import { CONTACT_EMAIL, OPERATOR_NAME } from "@/lib/legal";

export const metadata: Metadata = {
  title: "用户协议",
  description: "使用舟卡服务前请阅读的条款。",
};

const sections: LegalSection[] = [
  {
    title: "一、协议的成立",
    paragraphs: [
      `本协议由你与 ${OPERATOR_NAME}（以下称“我们”）订立。你注册账号或使用舟卡服务，即表示你已阅读并同意本协议及《隐私政策》《会员与退款条款》。`,
    ],
  },
  {
    title: "二、服务内容",
    paragraphs: [
      "舟卡提供简历整理与优化、AI 对话辅助、简历导出（PDF、Word、HTML）以及相关的求职辅助工具。我们可能根据业务需要调整功能，重大调整会提前告知。",
    ],
  },
  {
    title: "三、账号",
    paragraphs: [
      "注册时请使用真实有效的邮箱。每个账号由你本人使用，妥善保管登录信息。免费下载次数按账号计算，请勿通过多个账号重复领取。",
    ],
  },
  {
    title: "四、你的内容",
    paragraphs: [
      "你应确保提交的内容真实，并且你有权提交。你授予我们为提供服务而存储、处理和展示这些内容的必要许可，此许可在你删除内容或注销账号后终止。",
    ],
  },
  {
    title: "五、AI 生成的内容",
    paragraphs: [
      "AI 生成的内容可能存在不准确或遗漏之处。请在使用前核对事实，不得编造、夸大工作经历、业绩或学历。因未经核实的内容产生的后果，由你自行承担。",
    ],
  },
  {
    title: "六、付费服务",
    paragraphs: [
      "会员服务的价格、有效期、兑换方式和退款规则以《会员与退款条款》为准。",
    ],
  },
  {
    title: "七、禁止行为",
    paragraphs: [
      "不得利用服务从事违法违规活动；不得攻击、干扰或绕过系统的安全机制；不得批量注册账号、倒卖账号或刷取免费额度；不得上传含有违法或侵权内容的材料。",
    ],
  },
  {
    title: "八、服务的变更与中断",
    paragraphs: [
      "因系统维护、第三方服务故障或不可抗力，服务可能暂时中断。我们会尽力减少影响。",
    ],
  },
  {
    title: "九、免责声明",
    paragraphs: [
      "舟卡是辅助工具，不保证你获得面试机会或录用。我们在法律允许的范围内，不对间接损失承担责任。",
    ],
  },
  {
    title: "十、协议的变更与终止",
    paragraphs: [
      "我们可能更新本协议。变更后继续使用服务即视为同意更新后的协议。如你不同意，可以停止使用并注销账号。",
    ],
  },
  {
    title: "十一、适用法律与争议解决",
    paragraphs: [
      `本协议适用中华人民共和国法律。因本协议产生的争议，双方应先友好协商；协商不成的，提交有管辖权的人民法院处理。如有问题，请联系 ${CONTACT_EMAIL}。`,
    ],
  },
];

export default function TermsPage() {
  return <LegalDocument title="用户协议" sections={sections} />;
}
