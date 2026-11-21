import type { ReactNode } from 'react';
import type { StudioClaim } from '../api/types';
import { BASIS_LABEL, basisOfClaim, type Basis } from '../lib/trust';
import { CERTAINTY_LABEL, CLAIM_KIND_LABEL, labelOr } from '../lib/labels';

/**
 * 可信三态(DESIGN.md §4)的内联渲染:
 * 史实=靛青下划线,解释=青绿左线,演绎=朱砂底+“演绎”前缀,未考=灰虚线。
 * 每种态都带隐藏文字前缀,读屏与高对比模式下不依赖颜色。
 */
export function BasisText({
  basis,
  verified = true,
  children,
}: {
  basis: Basis | null;
  /** 仅对史实有意义:没有已核验出处的“史实”要显示“待核”。 */
  verified?: boolean;
  children: ReactNode;
}) {
  if (basis === null) {
    return (
      <span className="basis-text basis-text--unbound">
        {children}
        <span className="basis-tag basis-tag--unbound"> 未绑定 claim</span>
      </span>
    );
  }
  if (basis === 'drama') {
    return (
      <span className="basis-text basis-text--drama">
        <span className="basis-prefix">演绎 </span>
        {children}
      </span>
    );
  }
  if (basis === 'fact' && !verified) {
    return (
      <span className="basis-text basis-text--fact-unverified">
        <span className="sr-only">史实(出处未核验):</span>
        {children}
        <span className="basis-tag basis-tag--unknown"> 出处待核</span>
      </span>
    );
  }
  return (
    <span className={`basis-text basis-text--${basis}`}>
      <span className="sr-only">{BASIS_LABEL[basis]}:</span>
      {children}
      {basis === 'unknown' ? <span className="basis-tag basis-tag--unknown"> 不可考/待核</span> : null}
    </span>
  );
}

/** 图例:告诉编辑每种标记的含义,避免只靠颜色理解。 */
export function BasisLegend() {
  return (
    <dl className="legend" aria-label="可信三态图例">
      <div>
        <dt>
          <span className="basis-text basis-text--fact">史实</span>
        </dt>
        <dd>靛青下划线。点击可看出处。</dd>
      </div>
      <div>
        <dt>
          <span className="basis-text basis-text--interp">解释</span>
        </dt>
        <dd>青绿左线。这是理解,不是史料。</dd>
      </div>
      <div>
        <dt>
          <span className="basis-text basis-text--drama">
            <span className="basis-prefix">演绎 </span>示例
          </span>
        </dt>
        <dd>朱砂底加“演绎”前缀。不得当作史实。</dd>
      </div>
      <div>
        <dt>
          <span className="basis-text basis-text--unknown">不可考</span>
        </dt>
        <dd>灰虚线。写“不可考/待核”,不画成空白。</dd>
      </div>
    </dl>
  );
}

export function ClaimMeta({ claim }: { claim: StudioClaim }) {
  return (
    <span className="claim-meta">
      {labelOr(CLAIM_KIND_LABEL, claim.claim_kind)} · {labelOr(CERTAINTY_LABEL, claim.certainty)}
    </span>
  );
}

export { basisOfClaim };
