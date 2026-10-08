import { redirect } from "next/navigation";

export default async function MockRedirectPage({
  searchParams,
}: {
  searchParams: Promise<{ job_id?: string }> | { job_id?: string };
}) {
  const sp = await Promise.resolve(searchParams);
  const q = sp.job_id ? `?job_id=${encodeURIComponent(sp.job_id)}` : "";
  redirect(`/coach-agent${q}`);
}
