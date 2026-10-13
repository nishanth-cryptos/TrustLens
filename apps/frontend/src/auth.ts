// Browser side of the backend-for-frontend session. The browser never sees a token: it holds only the backend's
// HttpOnly session cookie, sent automatically to the same origin. Nothing is written to localStorage,
// sessionStorage or a script-readable cookie.

export type Me = { principal_id: string; principal_kind: string; roles: string[]; capabilities: string[] };

export type AuthState =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "signed-in"; me: Me }
  | { kind: "unavailable" };

export type SigninNotice = "denied" | "failed" | "unavailable" | null;

export const SIGN_IN_PATH = "/auth/login";

type Fetch = typeof fetch;

function isMe(value: unknown): value is Me {
  const v = value as Me;
  return !!v && typeof v.principal_id === "string" && typeof v.principal_kind === "string"
    && Array.isArray(v.roles) && v.roles.every((r) => typeof r === "string") && Array.isArray(v.capabilities);
}

export async function loadSession(fetcher: Fetch = fetch): Promise<AuthState> {
  try {
    const response = await fetcher("/api/v1/me", { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (response.status === 401) return { kind: "signed-out" };
    if (!response.ok) return { kind: "unavailable" };
    const body: unknown = await response.json();
    return isMe(body) ? { kind: "signed-in", me: body } : { kind: "unavailable" };
  } catch {
    return { kind: "unavailable" };
  }
}

export async function signOut(fetcher: Fetch = fetch): Promise<boolean> {
  try {
    const csrf = await fetcher("/auth/csrf", { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!csrf.ok) return csrf.status === 401;            // already signed out
    const { csrf_token } = (await csrf.json()) as { csrf_token?: unknown };
    if (typeof csrf_token !== "string") return false;
    const response = await fetcher("/auth/logout", {
      method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf_token, Accept: "application/json" },
    });
    return response.ok;
  } catch {
    return false;
  }
}

/** The categorical ?signin= outcome the callback adds; it never carries identity or token data. Pure read. */
export function readSigninNotice(search: string): SigninNotice {
  const value = new URLSearchParams(search).get("signin");
  if (value === null) return null;
  return value === "denied" || value === "unavailable" ? value : "failed";
}

/** Removes ?signin= from the address bar without a navigation. Idempotent (safe under StrictMode re-runs). */
export function clearSigninNotice(location: Location, history: History): void {
  const params = new URLSearchParams(location.search);
  if (!params.has("signin")) return;
  params.delete("signin");
  const query = params.toString();
  history.replaceState(null, "", location.pathname + (query ? `?${query}` : "") + location.hash);
}
