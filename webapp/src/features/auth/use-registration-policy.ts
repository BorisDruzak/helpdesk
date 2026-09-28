import { useEffect, useState } from "react";

import { fetchSessionCapabilities } from "./api";

export function useRegistrationPolicy() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  useEffect(() => {
    let active = true;
    void fetchSessionCapabilities().then(
      (capabilities) => { if (active) setEnabled(capabilities.self_registration_enabled); },
      () => { if (active) setEnabled(false); }
    );
    return () => { active = false; };
  }, []);
  return enabled;
}
