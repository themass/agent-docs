import { PageHeader } from '../components/ui';

export function NotFoundPage({ path }: { path: string }) {
  return (
    <>
      <PageHeader title="页面不存在 (404)" />
      <div className="state state--empty">
        <p className="state__title">没有找到 {path}</p>
        <p className="state__body">地址可能输入有误,或该页面已移除。</p>
        <div className="state__action">
          <a className="btn btn--secondary" href="#/workbench">
            回到工作台
          </a>
        </div>
      </div>
    </>
  );
}
