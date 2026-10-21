"use client";

import type { ReactNode } from "react";

import { ReopenProfileButton } from "@/components/profile/ReopenProfileButton";
import { WorkflowSteps } from "@/components/profile/WorkflowSteps";
import type { Profile } from "@/lib/api/profile";
import type { WorkflowStep } from "@/lib/resume-workflow";

type Props = {
  steps: WorkflowStep[];
  profile: Profile | null;
  onStepClick?: (stepId: WorkflowStep["id"]) => void;
  onReopened?: (profile: Profile) => void;
  profileSwitch?: ReactNode;
  trailing?: ReactNode;
};

/**
 * Row 1: full-width step rail. Row 2: context actions (left) + step CTAs (right).
 * Keeps progress and operations visually separate so neither fights for width.
 */
export function WorkflowHeader({
  steps,
  profile,
  onStepClick,
  onReopened,
  profileSwitch,
  trailing,
}: Props) {
  const hasContext = Boolean(profileSwitch || (profile && onReopened));
  const hasTrailing = Boolean(trailing);

  return (
    <div className="workflow-rail-wrap flex flex-col gap-2">
      <div className="rounded-xl border border-surface-border bg-surface p-1 shadow-xs">
        <WorkflowSteps steps={steps} onStepClick={onStepClick} />
      </div>

      {hasContext || hasTrailing ? (
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            {profileSwitch}
            {profile && onReopened ? (
              <ReopenProfileButton profile={profile} onReopened={onReopened} />
            ) : null}
          </div>
          {hasTrailing ? (
            <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
              {trailing}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
