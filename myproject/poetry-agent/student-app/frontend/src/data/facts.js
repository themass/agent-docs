/**
 * Spoken lines of a bundle, each with a stable id `{step}/{layer}/{index}` (index counts lines of that
 * layer within that step, narrator and poet lines together). This is the SAME numbering the agent uses
 * (student_agent/lesson.py), so a basis id returned by the agent points at the same line here.
 * A dramatization without its badge is never returned: the page refuses to show it, the agent refuses to say it.
 */
export function indexBundle(bundle) {
  const facts = new Map();
  const groups = [];                      // render order: [{step, layer, owner, bgId, seqs, assets, facts[]}]
  (bundle.steps || []).forEach((step, si) => {
    const counters = {};
    const parts = [...(step.layers || []).map((l, li) => [l, 'narrator', `steps[${si}].layers[${li}]`]),
      ...((step.roleplay?.layers) || []).map((l, li) => [l, 'poet', `steps[${si}].roleplay.layers[${li}]`])];
    for (const [layer, owner, layerPath] of parts) {
      const group = { step: step.step, layer: layer.layer, owner, bgId: layer.bg_id,
        seqs: (layer.line_seqs || []).map(Number), assets: layer.assets || [], facts: [] };
      (layer.lines || []).forEach((line, lineIdx) => {
        const idx = counters[layer.layer] || 0;
        counters[layer.layer] = idx + 1;                               // consumed even when skipped (matches the agent)
        const fact = { id: `${step.step}/${layer.layer}/${idx}`, text: line.text, kind: line.kind, owner,
          step: step.step, layer: layer.layer, claimId: line.basis?.claim_id || null,
          badge: line.badge || null, seqs: group.seqs,
          path: `${layerPath}.lines[${lineIdx}]`,                       // where it sits in the bundle (the asset registry's `usage` speaks in these)
          audio: line.audio || null };                                  // proposal: an `audio` asset id on the line itself; used when present
        if (line.kind === 'DRAMATIZATION' && !line.badge) return;
        facts.set(fact.id, fact);
        group.facts.push(fact);
      });
      groups.push(group);
    }
  });
  return { facts, groups };
}

export const groupsOf = (index, step, owner) => index.groups.filter(g => g.step === step && (!owner || g.owner === owner));
