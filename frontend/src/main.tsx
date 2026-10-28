import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Panel from "./panel/Panel.tsx";
import Site from "./site/Site.tsx";
import Invite from "./tap/Invite.tsx";
import Kiosk from "./tap/Kiosk.tsx";
import Tap from "./tap/Tap.tsx";

// Everything else (/, /rejestracja, /regulamin, unknown paths) is the public site.
// ponytail: path switch instead of a router — the panel has its own pushState router.
const path = window.location.pathname;
const tag = path.match(/^\/nfc\/([^/]+)\/?$/);
const kiosk = path.match(/^\/kiosk\/([^/]+)\/?$/);
const invite = path.match(/^\/zaproszenie\/([^/]+)\/?$/);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {path.startsWith("/panel") ? (
      <Panel />
    ) : tag ? (
      <Tap token={decodeURIComponent(tag[1])} />
    ) : kiosk ? (
      <Kiosk secret={decodeURIComponent(kiosk[1])} />
    ) : invite ? (
      <Invite token={decodeURIComponent(invite[1])} />
    ) : (
      <Site path={path} />
    )}
  </StrictMode>,
);
