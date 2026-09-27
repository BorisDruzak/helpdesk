const PREFIX = "pc_client.requester.create_intent.v1";

function storageKey(actor: string, intent: string): string {
  if (!actor) throw new Error("Не удалось определить учётную запись. Обновите страницу.");
  return `${PREFIX}:${encodeURIComponent(actor)}:${encodeURIComponent(intent || "default")}`;
}

export function pendingCreateKey(actor: string, intent: string): string {
  const location = storageKey(actor, intent);
  try {
    const existing = sessionStorage.getItem(location);
    if (existing) {
      if (!/^[A-Za-z0-9._:-]{8,128}$/.test(existing)) throw new Error("invalid pending key");
      return existing;
    }
    const key = crypto.randomUUID();
    sessionStorage.setItem(location, key);
    return key;
  } catch {
    throw new Error("Не удалось сохранить запрос для безопасного повтора. Проверьте доступ к хранилищу браузера.");
  }
}

export function clearCreateKey(actor: string, intent: string): void {
  sessionStorage.removeItem(storageKey(actor, intent));
}
