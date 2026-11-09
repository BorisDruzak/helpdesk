import { useSessionCapabilities } from "./use-session-capabilities";

export function useRegistrationPolicy() {
  return useSessionCapabilities()?.self_registration_enabled ?? null;
}
