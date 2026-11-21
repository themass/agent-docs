/**
 * What the agent would answer, computed from the bundle already on the device. Used when the agent
 * service is unreachable, so asking for a layer / a hint / the basis still works offline.
 * It deliberately cannot do two things: reword (that is a model's job) and evaluate a retell (the points
 * live with the agent). Both fall back to "compare with these lines yourself".
 */
export function localTurn({ action, step, args = {}, index, pack }) {
  const guide = (say, extra = {}) => ({ role: 'guide', say, basis: [], badge: 'NONE', next: 'no_action', source: 'local', ...extra });
  const speak = (role, facts) => ({ role, say: facts.map(f => f.text).join(''),
    basis: facts.map(f => ({ kind: 'script', id: f.id, claim_id: f.claimId })), badge: badgeOf(role, facts), next: 'no_action', source: 'local' });
  const owner = step === 'meet' ? 'poet' : 'narrator';
  const pool = [...index.facts.values()].filter(f => f.owner === owner);

  if (action === 'open_layer' && args.layer) {
    const hits = pool.filter(f => f.step === 'arrive' && f.layer === args.layer);
    return hits.length ? speak('narrator', hits.slice(0, 2)) : guide('这一层暂时没有更多内容。');
  }
  if (action === 'basis' || action === 'rephrase') {
    const fact = (args.ref && index.facts.get(args.ref)) || pool.find(f => f.step === step) || pool[0];
    if (!fact) return guide('你想问哪一句？点一下那一句。');
    if (action === 'rephrase') return speak(fact.owner, [fact]);
    if (fact.kind === 'DRAMATIZATION') return { ...speak('narrator', []), say: '这是教学演绎，不是史料。', basis: [{ kind: 'script', id: fact.id }], badge: 'DRAMATIZATION', source: 'local' };
    return { ...speak('narrator', []), say: `这一条属于${fact.kind === 'FACT' ? '史实' : '对这件事的理解'}，出处在诗词页的“出处与说法”里。`,
      basis: [{ kind: 'script', id: fact.id, claim_id: fact.claimId }], badge: badgeOf('narrator', [fact]), source: 'local' };
  }
  if (action === 'hint' && args.line_seq) {
    const notes = (pack?.annotations || []).filter(a => a.lineSeq === args.line_seq).slice(0, 2);
    return notes.length ? { role: 'narrator', say: notes.map(n => n.text).join(''), basis: notes.map(n => ({ kind: 'annotation', id: `ann:${n.id}` })), badge: 'NONE', next: 'no_action', source: 'local' }
      : guide('这一句的字词说明还在整理，先读读上下句。');
  }
  if (action === 'recite_prompt') return guide('放慢一点，一句一句读。');
  // 自己问的问题需要讲解服务来判断能不能答。没连上时不猜，也不把孩子打的字原样说回去。
  if (action === 'free_text') return guide('这一次没连上，我答不了你自己问的问题。上面的几个按钮还能用：先点一句，再点“这一句是什么意思”。', { unavailable: true });
  if (action === 'ask_why') return guide('读到这一句，你想到了什么？');
  if (action === 'evaluate_retell') return guide('这一次没连上讲解服务。你可以对照下面几句，看看自己讲到了哪些。', { evaluation: null, unavailable: true });
  // Reading a child's sentence is the agent's job (rules + safety screen). On the device we cannot do it, and we must
  // not pretend the question was understood and found "not covered": say what happened, and point at what is here.
  if (action === 'free_text') return guide('这一次没连上，你的问题我还没能看。上面几层里的内容都在，可以先翻翻，或者点一下想问的那一句。', { unavailable: true });
  return guide('这一点我们这一课没有讲到，要不要回头看看已经讲过的部分？');
}

function badgeOf(role, facts) {
  const kinds = new Set(facts.map(f => f.kind));
  if (role === 'poet' || kinds.has('DRAMATIZATION')) return 'DRAMATIZATION';
  if (kinds.has('INTERPRETATION')) return 'INTERPRETATION';
  return kinds.has('FACT') ? 'FACT' : 'NONE';
}
