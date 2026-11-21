import { isRecord } from '../lib/guards';

function scalar(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

/** 紧凑展示错误 details:校验错误列表、缺失项数组、键值对。不渲染原始 JSON 大块。 */
export function ErrorDetails({ details }: { details: unknown }) {
  if (details === undefined || details === null) return null;
  if (Array.isArray(details)) {
    if (details.length === 0) return null;
    return (
      <ul className="error-details">
        {details.map((item, index) => {
          if (isRecord(item) && typeof item.message === 'string') {
            const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
            return (
              <li key={index}>
                {loc ? <code>{loc}</code> : null} {item.message}
              </li>
            );
          }
          return <li key={index}>{scalar(item)}</li>;
        })}
      </ul>
    );
  }
  if (isRecord(details)) {
    const entries = Object.entries(details);
    if (entries.length === 0) return null;
    return (
      <dl className="error-details error-details--kv">
        {entries.map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{Array.isArray(value) ? value.map(scalar).join('、') : scalar(value)}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return <p className="error-details">{scalar(details)}</p>;
}
