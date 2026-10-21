/** Routes that use the split workbench (resume + agent rail) and should use full viewport width. */
const WORKBENCH_PREFIXES = ["/resume-agent", "/apply-agent", "/coach-agent"];

export function isWorkbenchPath(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  return WORKBENCH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
