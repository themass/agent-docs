import { bareSkillId } from './task-classifier.js';
import { createActionLoopGate } from './loop-gates.js';
export function createAgentGates(sameActionLimit) {
    return {
        loadedSkillIds: new Set(),
        loadedSkillBodies: [],
        jsCspBlocked: new Set(),
        seenObs: new Set(),
        lastObsByKey: new Map(),
        dupSkipByKey: new Map(),
        actionLoop: createActionLoopGate(sameActionLimit),
        lastListHints: [],
        taskHintIssued: false,
        stepsWithoutNewObs: 0,
        frictionHitlKeys: new Set(),
        runTabIds: new Set(),
        subtaskEvidenceReady: false,
        tabsListProgressUsed: false,
        pageVisits: new Map(),
    };
}
export function resetTurnGates(gates) {
    gates.lastListHints = [];
    gates.taskHintIssued = false;
}
export function markObservationSeen(gates, key, trace) {
    gates.seenObs.add(key);
    gates.lastObsByKey.set(key, trace);
}
export function observationAlreadySeen(gates, key) {
    return Boolean(key && gates.seenObs.has(key));
}
export function bumpDuplicateSkip(gates, key) {
    const n = (gates.dupSkipByKey.get(key) ?? 0) + 1;
    gates.dupSkipByKey.set(key, n);
    return n;
}
export function priorObservation(gates, key) {
    return gates.lastObsByKey.get(key);
}
export function recordListHints(gates, hints) {
    if (hints.length)
        gates.lastListHints = hints;
}
export function recordLoadedSkill(gates, id, body) {
    gates.loadedSkillIds.add(bareSkillId(id));
    if (body?.trim()) {
        gates.loadedSkillBodies.length = 0;
        gates.loadedSkillBodies.push(body.trim().slice(0, 4_000));
    }
}
export function recordRunTab(gates, tabId) {
    if (Number.isFinite(tabId) && tabId > 0)
        gates.runTabIds.add(tabId);
}
/** Enough material to synthesize an answer without more tabs_list loops. */
export function hasSynthesisEvidence(gates) {
    if (gates.subtaskEvidenceReady)
        return true;
    for (const key of gates.seenObs) {
        if (key.startsWith('dom_read|') || key.startsWith('fetch_text|'))
            return true;
    }
    return false;
}
export function scopeTabsToRun(tabs, gates, anchorTabId) {
    const totalBrowserTabs = tabs.length;
    const ids = new Set(gates.runTabIds);
    if (anchorTabId != null)
        ids.add(anchorTabId);
    if (!ids.size) {
        const active = tabs.filter((tab) => tab.active).slice(0, 1);
        return {
            tabs: active,
            scoped: false,
            totalBrowserTabs,
            hint: '先用 tabs_open(url) 打开来源页，再 tabs_switch(tab_id) + dom_read(body)；勿反复 tabs_list。',
        };
    }
    const filtered = tabs.filter((tab) => ids.has(tab.id));
    return {
        tabs: filtered.length ? filtered : tabs.filter((tab) => tab.active).slice(0, 1),
        scoped: true,
        totalBrowserTabs,
        hint: '仅本 run 相关 tab。用 tabs_switch(tab_id) 切换后 dom_read(body)；已有子任务/dom_read 证据可直接 system_done。',
    };
}
