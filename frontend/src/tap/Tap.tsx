// /nfc/<token>: the NFC sticker opens this on the employee's own phone. Logged in → the tap is the punch.
import "../fonts.css";
import { useEffect, useRef, useState } from "react";
import { ApiError, api, loadSession } from "../panel/api.ts";
import type { TapResult } from "../panel/api.ts";
import { Login } from "../panel/Panel.tsx";
import "../panel/panel.css";
import "./tap.css";

type Info = { point: string; workplace: string; signed_in: boolean; employee: string | null };

export default function Tap({ token }: { token: string }) {
  const [info, setInfo] = useState<Info | null>(null);
  const [result, setResult] = useState<TapResult | null>(null);
  const [error, setError] = useState("");
  const sent = useRef(false);
  const path = `/nfc/${encodeURIComponent(token)}/`;

  const punch = async () => {
    if (sent.current) return; // StrictMode / re-render: one tap = one request
    sent.current = true;
    try {
      setResult(await api.post<TapResult>(path));
      // A browser restoring this tab tomorrow must not punch again: the address becomes the panel.
      window.history.replaceState(null, "", "/panel");
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const load = async () => {
    try {
      await loadSession();
      const i = await api.get<Info>(path);
      setInfo(i);
      if (i.signed_in && i.employee) punch();
    } catch (err) {
      setError(err instanceof ApiError && err.status === 404 ? err.message : "Brak połączenia — odbicie nie zostało zapisane. Spróbuj jeszcze raz.");
    }
  };
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (error)
    return (
      <div className="panel">
        <main className="tap">
          <p className="tap-mark bad">!</p>
          <h1>Nie odbito</h1>
          <p>{error}</p>
          <a className="btn" href="/panel">Przejdź do panelu</a>
        </main>
      </div>
    );
  if (!info) return <div className="panel" />;
  if (!info.signed_in)
    return (
      <div className="panel">
        <Login title={info.point} lead={`${info.workplace}: zaloguj się raz na tym telefonie — potem wystarczy przyłożyć go do naklejki.`} onLogin={() => load()} />
      </div>
    );
  if (!info.employee)
    return (
      <div className="panel">
        <main className="tap">
          <p className="tap-mark bad">!</p>
          <h1>To konto nie jest w zespole</h1>
          <p>Naklejka należy do firmy {info.workplace}. Zaloguj się kontem nadanym przez tę firmę.</p>
          <a className="btn" href="/panel">Przejdź do panelu</a>
        </main>
      </div>
    );
  if (!result) return <div className="panel"><main className="tap"><p>Odbijam…</p></main></div>;
  return (
    <div className="panel">
      <main className={`tap ${result.kind}`}>
        <p className="tap-mark">{result.kind === "in" ? "→" : "←"}</p>
        <h1>{result.kind_label} {result.time}</h1>
        <p>
          <strong>{result.name}</strong> · {info.point}
        </p>
        {result.repeated && <p className="hint">To odbicie było już zapisane chwilę temu — nie liczymy go drugi raz.</p>}
        <a className="btn" href="/panel">Mój grafik</a>
      </main>
    </div>
  );
}
