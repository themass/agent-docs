export async function submitDraft(proposal, apiBase) {
  if (proposal.status !== 'DRAFT') throw new Error('only DRAFT proposals can be submitted');
  if (!apiBase) return { submitted: false, reason: 'api_not_configured' };
  const response = await fetch(`${apiBase.replace(/\/$/, '')}/api/poetry/v1/draft/proposals`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(proposal)
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`draft API ${response.status}: ${body}`);
  return { submitted: true, response: body };
}
