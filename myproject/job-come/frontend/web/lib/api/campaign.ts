import { apiJson } from "./client";
import type { CampaignStats } from "./jobs";

export function tagCampaignJob(
  profileId: string,
  jobId: string,
  tag: "warmup" | "target",
): Promise<CampaignStats> {
  return apiJson(`/campaign/profiles/${profileId}/jobs/${jobId}/tag?tag=${tag}`, {
    method: "POST",
  });
}

export { getCampaignStats, type CampaignStats } from "./jobs";
