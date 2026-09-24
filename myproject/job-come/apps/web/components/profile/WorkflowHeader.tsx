"use client";

import type { ReactNode } from "react";

import { ReopenProfileButton } from "@/components/profile/ReopenProfileButton";
import { WorkflowSteps } from "@/components/profile/WorkflowSteps";
import type { Profile } from "@/lib/api/profile";

type Step = {
  id: string;
  label: string;
  done: boolean;
  active: boolean;
  disabled?: boolean;
};

type Props = {
  steps: Step[];
  profile: Profile | null;
  onStepClick?: (stepId: string) => void;
  onReopened?: (profile: Profile) => void;
  profileSwitch?: ReactNode;
  trailing?: ReactNode;
};

export function WorkflowHeader({
  steps,
  profile,
  onStepClick,
  onReopened,
  profileSwitch,
  trailing,
}: Props) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <WorkflowSteps steps={steps} onStepClick={onStepClick} />
      {profileSwitch}
      <div className="ml-auto flex shrink-0 items-center gap-1.5">
        {profile && onReopened ? (
          <ReopenProfileButton profile={profile} onReopened={onReopened} />
        ) : null}
        {trailing}
      </div>
    </div>
  );
}
