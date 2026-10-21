/** Admin / prompt audit links — never show in production builds. */
export const SHOW_DEV_ADMIN_TOOLS =
  process.env.NODE_ENV === "development" ||
  process.env.NEXT_PUBLIC_JC_DEV_TOOLS === "true";
