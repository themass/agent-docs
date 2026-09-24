/** Local textures in `public/textures/` — avoids CDN CORS blocking WebGL. */
const LOCAL = "/textures";

export type PlanetTextureSet = {
  map: string;
  clouds?: string;
  ring?: string;
  /** Multiply material color when no dedicated map exists for a moon. */
  tint?: string;
  emissive?: boolean;
};

/** Solar System Scope 2K textures (CC BY 4.0), baked locally. See `public/textures/ATTRIBUTION.md`. */
export const PLANET_TEXTURES: Record<string, PlanetTextureSet> = {
  sun: { map: `${LOCAL}/2k_sun.jpg`, emissive: true },
  mercury: { map: `${LOCAL}/2k_mercury.jpg` },
  venus: { map: `${LOCAL}/2k_venus_atmosphere.jpg` },
  earth: {
    map: `${LOCAL}/2k_earth_daymap.jpg`,
    clouds: `${LOCAL}/2k_earth_clouds.jpg`,
  },
  moon: { map: `${LOCAL}/2k_moon.jpg` },
  mars: { map: `${LOCAL}/2k_mars.jpg` },
  phobos: { map: `${LOCAL}/2k_moon.jpg`, tint: "#9a8575" },
  deimos: { map: `${LOCAL}/2k_moon.jpg`, tint: "#7a6d62" },
  jupiter: { map: `${LOCAL}/2k_jupiter.jpg` },
  io: { map: `${LOCAL}/2k_mars.jpg`, tint: "#e8b84a" },
  europa: { map: `${LOCAL}/2k_moon.jpg`, tint: "#d8e8f4" },
  ganymede: { map: `${LOCAL}/2k_moon.jpg`, tint: "#a89888" },
  callisto: { map: `${LOCAL}/2k_moon.jpg`, tint: "#6e6258" },
  saturn: {
    map: `${LOCAL}/2k_saturn.jpg`,
    ring: `${LOCAL}/2k_saturn_ring_alpha.png`,
  },
  titan: { map: `${LOCAL}/2k_mars.jpg`, tint: "#c8842e" },
  enceladus: { map: `${LOCAL}/2k_moon.jpg`, tint: "#eef8ff" },
  rhea: { map: `${LOCAL}/2k_moon.jpg`, tint: "#b8b0a4" },
  iapetus: { map: `${LOCAL}/2k_moon.jpg`, tint: "#8a7a68" },
  uranus: { map: `${LOCAL}/2k_uranus.jpg` },
  miranda: { map: `${LOCAL}/2k_moon.jpg`, tint: "#a9a49c" },
  ariel: { map: `${LOCAL}/2k_moon.jpg`, tint: "#b7b1a5" },
  umbriel: { map: `${LOCAL}/2k_moon.jpg`, tint: "#68635d" },
  titania: { map: `${LOCAL}/2k_moon.jpg`, tint: "#9d968d" },
  oberon: { map: `${LOCAL}/2k_moon.jpg`, tint: "#807870" },
  neptune: { map: `${LOCAL}/2k_neptune.jpg` },
  triton: { map: `${LOCAL}/2k_moon.jpg`, tint: "#d5c7b6" },
  pluto: { map: `${LOCAL}/moon_1024.jpg`, tint: "#c4956e" },
  charon: { map: `${LOCAL}/2k_moon.jpg`, tint: "#bdb2a4" },
};

export function textureUrlsForBody(bodyId: string): string[] {
  const set = PLANET_TEXTURES[bodyId];
  if (!set) {
    return [];
  }
  const urls = [set.map];
  if (set.clouds) {
    urls.push(set.clouds);
  }
  if (set.ring) {
    urls.push(set.ring);
  }
  return urls;
}
