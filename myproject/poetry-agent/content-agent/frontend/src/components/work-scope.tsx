import { useEffect, type ReactNode } from 'react';
import { listWorks } from '../api/client';
import type { WorkSummary } from '../api/types';
import { navigate, useRoute } from '../lib/router';
import { useAsync } from '../lib/use-async';
import { AsyncView, EmptyView } from './async-view';
import { ContentStatusMark } from './ui';

export const WORK_STORAGE_KEY = 'poetry-studio.work';

function storedWork(): string {
  try {
    return window.localStorage.getItem(WORK_STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

/** 选中作品的优先级:URL ?work= → localStorage → 列表第一项。 */
export function resolveWork(works: WorkSummary[], fromQuery: string): WorkSummary | undefined {
  return (
    works.find(w => w.work_id === fromQuery) ?? works.find(w => w.work_id === storedWork()) ?? works[0]
  );
}

function WorkPicker({ works, selected }: { works: WorkSummary[]; selected: WorkSummary }) {
  const route = useRoute();
  useEffect(() => {
    try {
      window.localStorage.setItem(WORK_STORAGE_KEY, selected.work_id);
    } catch {
      // 忽略
    }
  }, [selected.work_id]);
  return (
    <div className="toolbar" role="group" aria-label="作品选择">
      <label htmlFor="work-picker" className="toolbar__label">
        作品
      </label>
      <select
        id="work-picker"
        value={selected.work_id}
        onChange={event => navigate(route.path, { ...route.query, work: event.target.value }, true)}
      >
        {works.map(work => (
          <option key={work.work_id} value={work.work_id}>
            {work.title}({work.work_id})
          </option>
        ))}
      </select>
      <ContentStatusMark status={selected.status} />
    </div>
  );
}

/**
 * 需要先选作品的页面(覆盖、内容、预检)用它包裹。
 * 作品列表自己有 loading / empty / error 三态。
 */
export function WorkScope({ children }: { children: (work: WorkSummary) => ReactNode }) {
  const route = useRoute();
  const result = useAsync(signal => listWorks(signal), []);
  return (
    <AsyncView
      result={result}
      loadingLabel="正在加载作品列表…"
      errorTitle="作品列表加载失败"
      empty={page =>
        page.items.length === 0 ? (
          <EmptyView title="还没有作品">BFF 返回了空的作品列表。请确认 Java 内容库(或本地 Mock)里有作品数据。</EmptyView>
        ) : null
      }
    >
      {page => {
        const selected = resolveWork(page.items, route.query.work ?? '');
        if (!selected) return null;
        return (
          <>
            <WorkPicker works={page.items} selected={selected} />
            <div key={selected.work_id}>{children(selected)}</div>
          </>
        );
      }}
    </AsyncView>
  );
}
