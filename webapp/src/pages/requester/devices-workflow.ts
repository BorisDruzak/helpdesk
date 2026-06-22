import type { DevicePairingPayload } from "../device-pairing/api";

export type WizardStep = "code" | "preview" | "result";
export type RequesterDevicesMode = "overview" | "link";

export function resultTitle(pairing: DevicePairingPayload | null): string {
  const status = pairing?.registration?.status || pairing?.status;
  if (status === "approved" || status === "admin_confirmed" || status === "confirmed" || status === "active") {
    return "Устройство подключено";
  }
  if (status === "pending_admin_review" || status === "user_confirmed") {
    return "Запрос отправлен на проверку";
  }
  return "Запрос отправлен";
}

export function resultDescription(pairing: DevicePairingPayload | null): string {
  const status = pairing?.registration?.status || pairing?.status;
  if (status === "approved" || status === "admin_confirmed" || status === "confirmed" || status === "active") {
    return "Можно продолжить работу в кабинете. Список устройств обновится после синхронизации.";
  }
  if (status === "pending_admin_review" || status === "user_confirmed") {
    return "Администратор проверит запрос. Пока можно создать обращение без выбора устройства, если такая форма доступна.";
  }
  return "Мы сохранили запрос. Если статус не изменится, создайте обращение на проверку владельца.";
}

export function isRegistrationPairing(pairing: DevicePairingPayload): boolean {
  return pairing.purpose === "registration";
}
