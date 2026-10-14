import { useEffect, useState } from "react";
import { AuthState, SIGN_IN_PATH, SigninNotice, clearSigninNotice, loadSession, readSigninNotice, signOut } from "./auth";
import Workspace from "./Workspace";

const NOTICES: Record<Exclude<SigninNotice, null>, string> = {
  denied: "You signed in, but this account has not been given access to TrustLens. Ask an administrator to grant access.",
  failed: "Sign-in did not complete. Please try again.",
  unavailable: "Sign-in is temporarily unavailable. Please try again shortly.",
};

const ROLE_LABELS: Record<string, string> = {
  USER: "User", ANALYST: "Analyst", KNOWLEDGE_EDITOR: "Knowledge editor",
  KNOWLEDGE_APPROVER: "Knowledge approver", ADMINISTRATOR: "Administrator",
};

type Props = { initialState?: AuthState; initialNotice?: SigninNotice };

export default function App({ initialState = { kind: "loading" }, initialNotice = null }: Props) {
  const [state, setState] = useState<AuthState>(initialState);
  const [notice, setNotice] = useState<SigninNotice>(
    () => initialNotice ?? (typeof window === "undefined" ? null : readSigninNotice(window.location.search)));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (initialState.kind !== "loading") return;
    clearSigninNotice(window.location, window.history);
    let active = true;
    loadSession().then((next) => { if (active) setState(next); });
    return () => { active = false; };
  }, [initialState.kind]);

  async function handleSignOut() {
    setBusy(true);
    const done = await signOut();
    setBusy(false);
    if (done) {
      setNotice(null);
      setState({ kind: "signed-out" });
    } else {
      setState(await loadSession());
    }
  }

  return (
    <main className="workspace">
      <header><span className="mark" aria-hidden="true">T</span><span>TrustLens</span></header>
      <section className="foundation" aria-labelledby="page-title" aria-busy={state.kind === "loading" || busy}>
        <p className="eyebrow">LOCAL DEVELOPMENT · SLICE 2</p>
        {notice && state.kind !== "signed-in" && <p className="notice" role="alert">{NOTICES[notice]}</p>}

        {state.kind === "loading" && <h1 id="page-title">Checking your session…</h1>}

        {state.kind === "signed-out" && <>
          <h1 id="page-title">Sign in to TrustLens.</h1>
          <p className="intro">Explainable scam analysis, built around evidence and honest uncertainty.</p>
          <a className="button" href={SIGN_IN_PATH}>Sign in with Keycloak</a>
          <p className="note">You will be taken to the TrustLens identity provider and brought back here.</p>
        </>}

        {state.kind === "signed-in" && <>
          <h1 id="page-title">You are signed in.</h1>
          <dl className="principal" aria-label="Your TrustLens access">
            <dt>Account type</dt><dd>{state.me.principal_kind === "HUMAN" ? "Person" : state.me.principal_kind}</dd>
            <dt>Roles</dt><dd>{state.me.roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</dd>
            <dt>Principal reference</dt><dd><code>{state.me.principal_id}</code></dd>
          </dl>
          <button type="button" className="button secondary" onClick={handleSignOut} disabled={busy}>
            {busy ? "Signing out…" : "Sign out"}
          </button>
          {state.me.roles.includes("USER") || state.me.roles.includes("ANALYST")
            ? <Workspace />
            : <p className="note">Case work is available to users and analysts only.</p>}
        </>}

        {state.kind === "unavailable" && <>
          <h1 id="page-title">TrustLens is temporarily unavailable.</h1>
          <p>Your session could not be checked. Please try again shortly.</p>
          <a className="button" href="/">Try again</a>
        </>}
      </section>
      <footer>TrustLens development workspace</footer>
    </main>
  );
}
