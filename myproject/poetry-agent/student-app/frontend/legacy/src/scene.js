/**
 * Bundle + preview feed -> view model. Plain JS, shared by the browser page and the node check, so
 * what the page shows is what has been checked. No fetching in here.
 *
 * The gate matters more than the rendering: while the base says DRAFT the student view model is
 * refused. A preview has to announce itself as a preview, otherwise it becomes a lie at scale.
 */
import { resolve, SceneMachine } from '../../dist/runtime/index.js';

const STEP_LABEL = { read: '读', arrive: '到', meet: '见', return: '回', recite: '诵' };

export function publishGate(bundle, preview) {
  const blocked = [];
  for (const [key, value] of Object.entries(preview.status || {})) if (value !== 'PUBLISHED') blocked.push(key);
  if (!bundle.coverage_notice) blocked.push('coverage_notice missing');
  return { open: blocked.length === 0, blocked };
}

export function buildScene(bundle, preview, budget = {}) {
  const gate = publishGate(bundle, preview);
  const machine = new SceneMachine(bundle);
  const lineBySeq = new Map(preview.lines.map(l => [l.seq, l.text]));
  const bgById = new Map(preview.backgrounds.map(b => [b.id, b]));
  const bgByLayer = new Map(preview.backgrounds.map(b => [b.layer, b]));
  const annBySeq = new Map();
  for (const a of preview.annotations) {
    if (!annBySeq.has(a.lineSeq)) annBySeq.set(a.lineSeq, []);
    annBySeq.get(a.lineSeq).push(a);
  }
  const bgFor = layer => bgById.get(layer.bg_id) || bgByLayer.get(layer.bg_id);

  const steps = bundle.steps.map(step => {
    const layers = [];
    const push = layer => {
      const bg = bgFor(layer);
      layers.push({
        layer: layer.layer, bgId: layer.bg_id,
        title: bg ? titleOf(bg) : layer.bg_id,
        body: bg ? bg.body : '',
        linkedLines: preview.relations.filter(r => r.backgroundId === layer.bg_id)
          .map(r => ({ seq: r.lineSeq, text: lineBySeq.get(r.lineSeq) || '' })),
        declaredInBase: (layer.line_seqs || []).every(s => lineBySeq.has(s)),
        assets: (layer.assets || []).map(id => resolve(id, bundle.assets, budget)),
        spoken: (layer.lines || []).map(l => ({ text: l.text, kind: l.kind,
          badge: l.badge || null, claimId: l.basis ? l.basis.claim_id : null })),
      });
    };
    (step.layers || []).forEach(push);
    if (step.roleplay) step.roleplay.layers.forEach(push);
    return { id: step.step, label: STEP_LABEL[step.step], layers,
             demoAudio: step.demo_audio || null, agentHelp: step.agent_help || null };
  });

  return {
    workId: bundle.work_id, textVersion: bundle.text_version_id,
    scriptId: `${bundle.script_id}@${bundle.script_version}`,
    scriptId: `${bundle.script_id}@${bundle.script_version}`,
    gate,
    lines: preview.lines.map(l => ({
      seq: l.seq, text: l.text,
      annotations: annBySeq.get(l.seq) || [],
      linkedBy: preview.relations.filter(r => r.lineSeq === l.seq).map(r => r.backgroundId),
    })),
    steps,
    coverageNotice: bundle.coverage_notice,
    unknownDatesNotice: bundle.unknown_dates_notice || null,
    dramatisations: countDramatisations(bundle),
    machine,
  };
}

function titleOf(bg) {
  const first = (bg.body || '').split(/[。！？\n]/)[0];
  return first.length > 24 ? first.slice(0, 24) + '…' : first;
}

function countDramatisations(bundle) {
  let n = 0;
  const scan = layers => (layers || []).forEach(l => (l.lines || []).forEach(x => { if (x.kind === 'DRAMATIZATION') n++; }));
  for (const s of bundle.steps) { scan(s.layers); if (s.roleplay) scan(s.roleplay.layers); }
  return n;
}
