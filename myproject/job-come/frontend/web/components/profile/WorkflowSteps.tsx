type Step = {
  id: string;
  label: string;
  done: boolean;
  active: boolean;
  disabled?: boolean;
  hint?: string;
};

type Props = {
  steps: Step[];
  onStepClick?: (stepId: string) => void;
};

/**
 * Four-step progress rail for the resume workflow.
 *
 * Design intent: the user should be able to answer "where am I, what's done, and
 * what can I click" at a glance. So the three states are encoded redundantly —
 * fill, connector colour, and icon — rather than by colour alone, which also
 * keeps it legible for colour-vision deficiency.
 *
 * The connector between two steps is filled only when the *earlier* step is
 * done, so the rail reads as progress rather than decoration.
 */
export function WorkflowSteps({ steps, onStepClick }: Props) {
  return (
    <ol className="scroll-area flex min-w-0 flex-1 flex-nowrap items-center overflow-x-auto">
      {steps.map((step, idx) => {
        const interactive = !step.disabled && Boolean(onStepClick);
        return (
          <li key={step.id} className="flex shrink-0 items-center">
            <button
              type="button"
              disabled={step.disabled}
              title={step.disabled ? step.hint : undefined}
              aria-current={step.active ? "step" : undefined}
              onClick={() => onStepClick?.(step.id)}
              className={`group inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium transition
                disabled:cursor-not-allowed disabled:opacity-45
                ${
                  step.active
                    ? "bg-brand-600 text-white shadow-xs"
                    : step.done
                      ? "text-success-700 hover:bg-success-50"
                      : interactive
                        ? "text-ink-500 hover:bg-ink-100 hover:text-ink-800"
                        : "text-ink-500"
                }`}
            >
              <span
                className={`flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full text-micro font-semibold transition ${
                  step.active
                    ? "bg-white/25 text-white"
                    : step.done
                      ? "bg-success-100 text-success-700"
                      : "bg-ink-100 text-ink-500 group-hover:bg-ink-200"
                }`}
                aria-hidden
              >
                {step.done && !step.active ? (
                  <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  idx + 1
                )}
              </span>
              <span className="whitespace-nowrap">{step.label}</span>
            </button>

            {idx < steps.length - 1 ? (
              <span
                aria-hidden
                className={`mx-0.5 h-px w-4 shrink-0 rounded-full transition sm:w-5 ${
                  step.done ? "bg-success-200" : "bg-surface-border"
                }`}
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
