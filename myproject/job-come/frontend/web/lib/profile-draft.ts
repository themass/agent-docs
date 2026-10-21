import type { Profile, ProfilePayload } from "@/lib/api/profile";

export type ProfileDraft = {
  base: Profile;
  payload: ProfilePayload;
  conflict: Profile | null;
};

export const samePayload = (a: ProfilePayload, b: ProfilePayload) =>
  JSON.stringify(a) === JSON.stringify(b);
export const draftIsDirty = (draft: ProfileDraft) => !samePayload(draft.payload, draft.base.payload);
export const createProfileDraft = (profile: Profile): ProfileDraft => ({
  base: profile, payload: profile.payload, conflict: null,
});

// Photo URLs are refreshed on reads; photo writes have a separate endpoint. Only
// this field may be adopted without rebasing the user's unsaved career facts.
function withoutPhoto(payload: ProfilePayload) {
  return { ...payload, contact: { ...payload.contact, photo: undefined } };
}

export function receiveProfile(draft: ProfileDraft, incoming: Profile): ProfileDraft {
  if (incoming.id !== draft.base.id) return createProfileDraft(incoming);
  if (incoming.version < Math.max(draft.base.version, draft.conflict?.version ?? 0)) return draft;
  if (incoming.version === draft.base.version && samePayload(incoming.payload, draft.base.payload)) return draft;
  if (!draftIsDirty(draft)) return createProfileDraft(incoming);
  if (samePayload(withoutPhoto(incoming.payload), withoutPhoto(draft.base.payload))) {
    return {
      base: incoming,
      payload: { ...draft.payload, contact: { ...draft.payload.contact, photo: incoming.payload.contact.photo } },
      conflict: draft.conflict,
    };
  }
  return { ...draft, conflict: incoming };
}

export function acknowledgeSave(draft: ProfileDraft, submitted: ProfilePayload, saved: Profile): ProfileDraft {
  if (saved.id !== draft.base.id || saved.version < draft.base.version) return draft;
  // Edits typed while the request was in flight belong to the next save, not to
  // the response. Never erase them with the older submitted snapshot.
  return {
    base: saved,
    payload: samePayload(draft.payload, submitted) ? saved.payload : draft.payload,
    conflict: draft.conflict && draft.conflict.version > saved.version ? draft.conflict : null,
  };
}

export function cleanProfileDraft(payload: ProfilePayload): ProfilePayload {
  return {
    ...payload,
    experiences: payload.experiences.map((exp) => ({
      ...exp, scope: (exp.scope ?? "").trim() || null,
      highlights: (exp.highlights ?? []).map((h) => h.trim()).filter(Boolean),
    })),
  };
}
