import type { WorkflowStep } from "@/lib/resume-workflow";

type Props = {
  steps: WorkflowStep[];
  onStepClick?: (stepId: WorkflowStep["id"]) => void;
};

function stepAriaLabel(step: WorkflowStep): string {
  if (step.disabled && step.hint) {
    return `${step.label}（${step.hint}）`;
  }
  return step.label;
}

/**
 * Four-step progress rail — equal-width cells so the bar uses the full pane width
 * instead of bunching on the left with empty space on the right.
 */
export function WorkflowSteps({ steps, onStepClick }: Props) {
  return (
    <ol className="workflow-rail" aria-label="简历流程步骤">
      {steps.map((step, idx) => {
        const state = step.active ? "active" : step.done ? "done" : "idle";
        const canClick = Boolean(onStepClick) && !step.disabled;
        return (
          <li key={step.id} className="workflow-rail__cell">
            <button
              type="button"
              disabled={step.disabled}
              aria-label={stepAriaLabel(step)}
              aria-current={step.active ? "step" : undefined}
              onClick={() => {
                if (canClick) onStepClick?.(step.id);
              }}
              className={`workflow-rail__btn workflow-rail__btn--${state}`}
            >
              <span className="workflow-rail__index" aria-hidden>
                {step.done && !step.active ? (
                  <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  idx + 1
                )}
              </span>
              <span className="workflow-rail__label" aria-hidden>{step.label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
