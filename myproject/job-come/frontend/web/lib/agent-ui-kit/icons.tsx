import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { className?: string };

const stroke = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

const base = "h-4 w-4";

function PathIcon({ className, d }: IconProps & { d: string }) {
  return (
    <svg className={className ?? base} {...stroke}>
      <path d={d} />
    </svg>
  );
}

function PathsIcon({ className, paths }: IconProps & { paths: string[] }) {
  return (
    <svg className={className ?? base} {...stroke}>
      {paths.map((d) => (
        <path key={d.slice(0, 32)} d={d} />
      ))}
    </svg>
  );
}

export function IconQueueSubmit(p: IconProps) {
  return <PathIcon {...p} d="M19 5v6a3 3 0 0 1-3 3H6m0 0 4-4m-4 4 4 4" />;
}

export function IconPencil(p: IconProps) {
  return (
    <PathIcon
      {...p}
      d="M16.862 4.487 18.549 2.8a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10"
    />
  );
}

export function IconTrash(p: IconProps) {
  return (
    <PathsIcon
      {...p}
      paths={[
        "M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0",
      ]}
    />
  );
}

export function IconGrip(p: IconProps) {
  return (
    <PathsIcon
      {...p}
      paths={[
        "M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.008v.008H3.75V6.75Zm.008 5.25h.008v.008H3.75v-.008Zm.008 5.25h.008v.008H3.75v-.008Z",
      ]}
    />
  );
}

export function IconCheck(p: IconProps) {
  return <PathIcon {...p} d="m4.5 12.75 6 6 9-13.5" />;
}
