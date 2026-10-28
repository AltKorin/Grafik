// Web NFC (Chrome on Android only): write the sticker link from the panel, read cards on a kiosk tablet.
// Everywhere else the same jobs go through an NFC app (writing) or a USB reader that types (reading).
type NdefReader = {
  scan(options?: { signal?: AbortSignal }): Promise<void>;
  write(message: { records: { recordType: "url"; data: string }[] }): Promise<void>;
  onreading: ((event: { serialNumber: string }) => void) | null;
  onreadingerror: (() => void) | null;
};

declare global {
  interface Window {
    NDEFReader?: new () => NdefReader;
  }
}

export const hasWebNfc = () => typeof window !== "undefined" && "NDEFReader" in window;

export async function writeUrl(url: string) {
  await new window.NDEFReader!().write({ records: [{ recordType: "url", data: url }] });
}

/** Calls back with each tapped tag's serial number until `signal` aborts. Needs a user gesture to start. */
export async function scanSerials(onSerial: (serial: string) => void, onError: () => void, signal: AbortSignal) {
  const reader = new window.NDEFReader!();
  reader.onreading = (e) => onSerial(e.serialNumber);
  reader.onreadingerror = onError;
  await reader.scan({ signal });
}
