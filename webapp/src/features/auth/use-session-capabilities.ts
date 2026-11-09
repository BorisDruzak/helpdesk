import { useEffect, useState } from "react";
import { fetchSessionCapabilities, type WebSessionCapabilities } from "./api";

export function useSessionCapabilities() {
  const [capabilities, setCapabilities] = useState<WebSessionCapabilities | null>(null);
  useEffect(() => {
    let active = true;
    void fetchSessionCapabilities().then(
      (value) => { if (active) setCapabilities(value); },
      () => { if (active) setCapabilities({ self_registration_enabled: false, sso_enabled: false }); },
    );
    return () => { active = false; };
  }, []);
  return capabilities;
}
