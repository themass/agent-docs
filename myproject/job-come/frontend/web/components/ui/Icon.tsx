/**
 * The few inline icons shared across pages. Kept as one small set rather than
 * a dependency: every glyph here is a single stroked path on a 24px grid, so
 * they stay visually consistent with the Heroicons-style paths already inline
 * in the header and agent panels.
 */
type IconProps = { className?: string };

const base = "h-4 w-4";

const svgProps = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

function Svg({ className, d }: IconProps & { d: string }) {
  return (
    <svg className={className ?? base} {...svgProps}>
      <path d={d} />
    </svg>
  );
}

function SvgPaths({ className, paths }: IconProps & { paths: string[] }) {
  return (
    <svg className={className ?? base} {...svgProps}>
      {paths.map((d) => (
        <path key={d.slice(0, 24)} d={d} />
      ))}
    </svg>
  );
}

export const IconLink = (p: IconProps) => (
  <Svg {...p} d="M13.5 10.5 21 3m0 0h-5.25M21 3v5.25m-3 5.25v4.5A2.25 2.25 0 0 1 15.75 20.25h-9A2.25 2.25 0 0 1 4.5 18v-9a2.25 2.25 0 0 1 2.25-2.25h4.5" />
);
export const IconDoc = (p: IconProps) => (
  <Svg {...p} d="M19.5 14.25V6.108c0-1.135-.845-2.098-1.976-2.192A48.4 48.4 0 0 0 13.5 3.75c-1.354 0-2.694.055-4.024.166C8.345 4.01 7.5 4.973 7.5 6.108V8.25m12 6-6.75 6.75H9a2.25 2.25 0 0 1-2.25-2.25V8.25m12.75 6h-3.75a1.5 1.5 0 0 0-1.5 1.5v3.75M4.5 8.25h3" />
);
export const IconTarget = (p: IconProps) => (
  <Svg {...p} d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm0-3a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" />
);
export const IconCheck = (p: IconProps) => <Svg {...p} d="m4.5 12.75 6 6 9-13.5" />;
export const IconArrowRight = (p: IconProps) => (
  <Svg {...p} d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
);
export const IconSpark = (p: IconProps) => (
  <Svg {...p} d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
);
export const IconInbox = (p: IconProps) => (
  <Svg {...p} d="M2.25 13.5h3.86a2.25 2.25 0 0 1 2.012 1.244l.256.512a2.25 2.25 0 0 0 2.013 1.244h3.218a2.25 2.25 0 0 0 2.013-1.244l.256-.512a2.25 2.25 0 0 1 2.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 0 0-2.15-1.588H6.911a2.25 2.25 0 0 0-2.15 1.588L2.35 13.177a2.25 2.25 0 0 0-.1.661Z" />
);
export const IconChat = (p: IconProps) => (
  <Svg {...p} d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3q-1.628 0-3.23-.129c-.305-.025-.598-.094-.869-.2M20.25 8.511a48 48 0 0 0-5.395-.513 3 3 0 0 0-.93.129m6.325.384V6.637c0-1.12-.788-2.1-1.902-2.223A48.5 48.5 0 0 0 12 4.125c-2.17 0-4.307.127-6.398.372C4.488 4.62 3.75 5.555 3.75 6.637v6.666a2.25 2.25 0 0 0 1.902 2.223c.471.058.945.108 1.423.15V20.25l3-3" />
);
export const IconBookmark = (p: IconProps) => (
  <Svg {...p} d="M16.5 3.75V16.5L12 14.25 7.5 16.5V3.75m9 0H18A2.25 2.25 0 0 1 20.25 6v12A2.25 2.25 0 0 1 18 20.25H6A2.25 2.25 0 0 1 3.75 18V6A2.25 2.25 0 0 1 6 3.75h1.5m9 0h-9" />
);
export const IconInfo = (p: IconProps) => (
  <Svg {...p} d="M11.25 11.25h.75v4.5h.75M12 8.25h.008M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
);
export const IconWarn = (p: IconProps) => (
  <Svg {...p} d="M12 9v3.75m0 3.75h.008M10.34 3.94 2.697 17.13A1.75 1.75 0 0 0 4.21 19.75h15.58a1.75 1.75 0 0 0 1.513-2.62L13.66 3.94a1.75 1.75 0 0 0-3.02 0Z" />
);

/** Codex-style “submit / run now” (corner return). */
export const IconQueueSubmit = (p: IconProps) => (
  <Svg {...p} d="M9 10.5 3 16.5M9 10.5V4.5M9 10.5h11.25" />
);

export const IconPencil = (p: IconProps) => (
  <Svg
    {...p}
    d="M16.862 4.487 18.549 2.8a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10"
  />
);

export const IconTrash = (p: IconProps) => (
  <SvgPaths
    {...p}
    paths={[
      "M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0",
    ]}
  />
);

export const IconGrip = (p: IconProps) => (
  <SvgPaths
    {...p}
    paths={[
      "M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.008v.008H3.75V6.75Zm.008 5.25h.008v.008H3.75v-.008Zm.008 5.25h.008v.008H3.75v-.008Z",
    ]}
  />
);
