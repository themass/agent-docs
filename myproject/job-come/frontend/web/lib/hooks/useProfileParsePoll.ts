"use client";

import { useEffect, useRef } from "react";

import { getProfile, type Profile } from "@/lib/api/profile";
import { isProfileParseInFlight, PROFILE_PARSE_POLL_MS } from "@/lib/profile-parse";

/**
 * Keep profile in sync when background parse is in flight (e.g. user refreshed mid-upload).
 */
export function useProfileParsePoll(
  profile: Profile | null,
  onProfile: (profile: Profile) => void,
): void {
  const onProfileRef = useRef(onProfile);
  onProfileRef.current = onProfile;

  const inFlight = isProfileParseInFlight(profile);
  const profileId = profile?.id;

  useEffect(() => {
    if (!profileId || !inFlight) return;

    let cancelled = false;
    let busy = false;

    const tick = () => {
      if (cancelled || busy) return;
      busy = true;
      void getProfile(profileId)
        .then((data) => {
          if (!cancelled && data.id === profileId) {
            onProfileRef.current(data);
          }
        })
        .catch(() => undefined)
        .finally(() => {
          busy = false;
        });
    };

    tick();
    const timer = window.setInterval(tick, PROFILE_PARSE_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [profileId, inFlight]);
}
