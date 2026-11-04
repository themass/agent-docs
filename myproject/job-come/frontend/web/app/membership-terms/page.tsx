import type { Metadata } from "next";

import { LegalDocument, type LegalSection } from "@/components/legal/LegalDocument";
import { CONTACT_EMAIL } from "@/lib/legal";

export const metadata: Metadata = {
  title: "会员与退款条款",
  description: "舟卡月会员的内容、兑换方式、有效期与退款规则。",
};

const sections: LegalSection[] = [
  {
    title: "一、会员内容",
    paragraphs: [
      "月会员：人民币 25 元，有效期 30 天。会员期间下载简历不限次数。",
      "免费账号：每个账号终身可免费下载一次简历。下载成功后计入一次；失败的导出不计入。",
    ],
  },
  {
    title: "二、购买与兑换",
    paragraphs: [
      "会员通过兑换码开通。兑换码由舟卡发放，每个兑换码只能使用一次。",
      "每个兑换码只能兑换一次，兑换成功后立即生效。兑换码不可转让。",
    ],
  },
  {
    title: "三、有效期",
    paragraphs: [
      "会员未到期时兑换新的兑换码，新增的 30 天接在当前到期日之后，不会丢失剩余时间。",
      "会员到期后，会员权益即时失效，恢复为免费账号。到期后不会补发任何额外的免费次数或会员时长。",
    ],
  },
  {
    title: "四、退款规则",
    paragraphs: [
      "会员与兑换码属于虚拟服务。兑换码兑换成功前，可申请退款；兑换成功后不予退款。因舟卡系统故障导致会员无法使用的，按未使用的天数退还相应费用。",
      "如因我们的原因导致兑换码无法使用（例如经核实系系统错误），我们会在核实后处理，方式包括补发有效兑换码或延长会员期限，你也可以申请退还该兑换码对应的费用。",
      "如需申请处理，请联系 " + CONTACT_EMAIL + "，并提供购买截图和兑换码（请勿在公开场合发布兑换码）。",
    ],
  },
  {
    title: "五、价格调整",
    paragraphs: [
      "我们可能调整会员价格。调整不影响调整前已经购买的兑换码。",
    ],
  },
];

export default function MembershipTermsPage() {
  return <LegalDocument title="会员与退款条款" sections={sections} />;
}
