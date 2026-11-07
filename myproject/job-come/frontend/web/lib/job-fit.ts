import type { FitScore, Job } from "@/lib/api/jobs";

/**
 * A job with its fit score filled in. A job is saved before it is scored (parse, then fit), so a
 * job can exist without a score, and the list must be able to fill one in afterwards.
 */
export function withFit(job: Job, fit: FitScore): Job {
  return {
    ...job,
    fit_score: fit.score,
    fit_recommendation: fit.recommendation,
    fit_gaps: fit.gaps,
    fit_blockers: fit.blockers,
    evidence_profile_version: fit.evidence_profile_version,
    requirement_evidence: fit.requirement_evidence,
    fit_summary: fit.summary,
    elevate_hints: fit.elevate_hints,
    fit_dimensions: fit.dimensions,
    legitimacy: fit.legitimacy,
  };
}
