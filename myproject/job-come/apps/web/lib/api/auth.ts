import { apiJson } from "./client";

export type UserContext = {
  id: string;
  email: string;
  email_verified: boolean;
  display_name: string | null;
};

export type AuthContext = {
  actor: string;
  user: UserContext | null;
  capabilities: string[];
  active_profile_id: string | null;
  merge_conflict: Record<string, unknown> | null;
};

export type LoginBody = { email: string; password: string };
export type RegisterBody = { email: string; password: string; display_name?: string };

export type AuthSuccess = {
  user: UserContext;
  active_profile_id: string | null;
  merge_conflict: Record<string, unknown> | null;
};

export function getAuthContext(): Promise<AuthContext> {
  return apiJson<AuthContext>("/auth/context");
}

export function login(body: LoginBody): Promise<AuthSuccess> {
  return apiJson<AuthSuccess>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function register(body: RegisterBody): Promise<AuthSuccess> {
  return apiJson<AuthSuccess>("/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function logout(): Promise<void> {
  await apiJson<void>("/auth/logout", { method: "POST" });
}

export function forgotPassword(body: { email: string }): Promise<{ message: string }> {
  return apiJson<{ message: string }>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function resetPassword(body: {
  token: string;
  password: string;
}): Promise<{ message: string }> {
  return apiJson<{ message: string }>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function verifyEmail(body: { token: string }): Promise<{ message: string }> {
  return apiJson<{ message: string }>("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function resendVerification(): Promise<{ message: string }> {
  return apiJson<{ message: string }>("/auth/resend-verification", { method: "POST" });
}

export function resolveMerge(choice: "keep_guest" | "keep_account"): Promise<AuthSuccess> {
  return apiJson<AuthSuccess>("/auth/resolve-merge", {
    method: "POST",
    body: JSON.stringify({ choice }),
  });
}

export function changePassword(body: {
  current_password: string;
  new_password: string;
}): Promise<{ message: string }> {
  return apiJson<{ message: string }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
