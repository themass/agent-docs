/** Extract HTML tables as row objects (Phase 4). */
export const CATALOG_TABLE_EXTRACT_JS = `(() => {
  const tables = [...document.querySelectorAll('table')]
  const out = []
  for (const table of tables.slice(0, 4)) {
    let headers = [...table.querySelectorAll('thead th')].map((c) =>
      (c.textContent || '').trim().slice(0, 80)
    )
    const bodyRows = [...table.querySelectorAll('tbody tr')]
    let dataRows = bodyRows.length ? bodyRows : [...table.querySelectorAll('tr')]
    if (!headers.length && dataRows.length) {
      const first = dataRows[0]
      headers = [...first.querySelectorAll('th,td')].map((c) =>
        (c.textContent || '').trim().slice(0, 80)
      )
      dataRows = dataRows.slice(1)
    }
    if (!headers.some(Boolean)) continue
    for (const tr of dataRows.slice(0, 48)) {
      const cells = [...tr.querySelectorAll('td,th')].map((c) =>
        (c.textContent || '').trim().slice(0, 240)
      )
      if (!cells.some((x) => x.length > 0)) continue
      const fields = {}
      headers.forEach((h, i) => {
        if (h) fields[h] = cells[i] ?? ''
      })
      const link = tr.querySelector('a[href]')
      const title = cells.find((c) => c.length > 1) || headers[0] || ''
      out.push({
        title: String(title).slice(0, 160),
        url: link ? link.href : undefined,
        fields,
      })
    }
    if (out.length) break
  }
  return out
})()`;
export function parseTableExtractPayload(raw) {
    if (!Array.isArray(raw))
        return [];
    const out = [];
    for (const item of raw) {
        if (!item || typeof item !== 'object')
            continue;
        const row = item;
        const title = typeof row.title === 'string' ? row.title : '';
        if (!title.trim())
            continue;
        const url = typeof row.url === 'string' ? row.url : undefined;
        const fields = row.fields && typeof row.fields === 'object' && !Array.isArray(row.fields)
            ? row.fields
            : undefined;
        out.push({ title, url, fields });
    }
    return out;
}
