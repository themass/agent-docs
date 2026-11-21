import { AsyncView } from '../components/async-view';
import { PageHeader } from '../components/ui';
import { CreateTaskForm } from './create-task-form';
import { TaskList, useWorkList } from './task-list';

export function WorkbenchPage() {
  const works = useWorkList();
  return (
    <>
      <PageHeader
        title="工作台"
        lead="创建内容任务,查看任务列表。Agent 只产出可审核的 DRAFT 候选,是否采用由人决定。"
      />
      <AsyncView result={works} loadingLabel="正在加载作品…" errorTitle="作品列表加载失败">
        {items => (
          <div className="split">
            <TaskList works={items} />
            <CreateTaskForm works={items} />
          </div>
        )}
      </AsyncView>
    </>
  );
}

/** 「任务与运行」入口:同一个任务列表,强调进入任务详情观察运行。 */
export function TasksIndexPage() {
  const works = useWorkList();
  return (
    <>
      <PageHeader title="任务与运行" lead="选择一个任务,进入详情观察运行、预算与事件流。新任务在“工作台”创建。" />
      <AsyncView result={works} loadingLabel="正在加载作品…" errorTitle="作品列表加载失败">
        {items => <TaskList works={items} />}
      </AsyncView>
    </>
  );
}
