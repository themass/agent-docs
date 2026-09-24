type Step = {
  id: string;
  label: string;
  done: boolean;
  active: boolean;
  disabled?: boolean;
};

type Props = {
  steps: Step[];
  onStepClick?: (stepId: string) => void;
};

export function WorkflowSteps({ steps, onStepClick }: Props) {
  return (
    <ol className="flex min-w-0 flex-1 flex-nowrap items-center gap-1 overflow-x-auto text-[11px]">
      {steps.map((step, idx) => (
        <li key={step.id} className="flex shrink-0 items-center">
          <button
            type="button"
            disabled={step.disabled}
            onClick={() => onStepClick?.(step.id)}
            className={`inline-flex items-center gap-1 rounded-full px-2 py-1 font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              step.active
                ? "bg-brand-600 text-white shadow-sm"
                : step.done
                  ? "bg-brand-50 text-brand-700 ring-1 ring-brand-100 hover:bg-brand-100"
                  : "bg-white text-slate-500 ring-1 ring-surface-border hover:bg-slate-50"
            }`}
          >
            <span
              className={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] ${
                step.active ? "bg-white/20" : step.done ? "bg-brand-100 text-brand-700" : "bg-slate-100"
              }`}
            >
              {step.done && !step.active ? (
                <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                idx + 1
              )}
            </span>
            {step.label}
          </button>
          {idx < steps.length - 1 ? (
            <span className="mx-1 hidden h-px w-3 bg-surface-border sm:block" aria-hidden />
          ) : null}
        </li>
      ))}
    </ol>
  );
}
