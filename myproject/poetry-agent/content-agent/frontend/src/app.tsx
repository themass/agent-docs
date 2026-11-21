import { useEffect } from 'react';
import { AnnouncerProvider } from './components/announcer';
import { ErrorBoundary } from './components/error-boundary';
import { Shell } from './components/shell';
import { AuthProvider } from './lib/actor';
import { navigate, useRoute } from './lib/router';
import { ContentPage } from './pages/content-page';
import { CoveragePage } from './pages/coverage-page';
import { NotFoundPage } from './pages/not-found-page';
import { PrecheckPage } from './pages/precheck-page';
import { ProposalDetailPage } from './pages/proposal-detail-page';
import { ProposalListPage } from './pages/proposal-list-page';
import { SourcesPage } from './pages/sources-page';
import { TaskDetailPage } from './pages/task-detail-page';
import { TasksIndexPage, WorkbenchPage } from './pages/workbench-page';

export function Routes() {
  const { segments, path } = useRoute();
  const [root, id] = segments;

  useEffect(() => {
    if (segments.length === 0) navigate('/workbench', undefined, true);
  }, [segments.length]);

  switch (root) {
    case undefined:
    case 'workbench':
      return <WorkbenchPage />;
    case 'tasks':
      return id ? <TaskDetailPage key={id} taskId={id} /> : <TasksIndexPage />;
    case 'proposals':
      return id ? <ProposalDetailPage key={id} proposalId={id} /> : <ProposalListPage />;
    case 'coverage':
      return <CoveragePage />;
    case 'sources':
      return <SourcesPage />;
    case 'content':
      return <ContentPage />;
    case 'precheck':
      return <PrecheckPage />;
    default:
      return <NotFoundPage path={path} />;
  }
}

export function App() {
  return (
    <ErrorBoundary>
      <AnnouncerProvider>
        <AuthProvider>
          <Shell>
            <Routes />
          </Shell>
        </AuthProvider>
      </AnnouncerProvider>
    </ErrorBoundary>
  );
}
