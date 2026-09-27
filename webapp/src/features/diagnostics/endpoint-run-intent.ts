const PREFIX = "pc_client.diagnostics.endpoint_intent.v1";

function storageKey(actor: string, ticketId: string): string {
  if (!actor || !ticketId) throw new Error("Не удалось определить пользователя или обращение.");
  return `${PREFIX}:${encodeURIComponent(actor)}:${encodeURIComponent(ticketId)}`;
}

export function pendingEndpointRunKey(actor: string, ticketId: string): string {
  try {
    const location = storageKey(actor, ticketId);
    const existing = sessionStorage.getItem(location);
    if (existing) {
      if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/.test(existing)) throw new Error("Invalid pending key");
      return existing;
    }
    const key = crypto.randomUUID();
    sessionStorage.setItem(location, key);
    return key;
  } catch {
    throw new Error("Не удалось сохранить запрос для безопасного повтора. Проверьте доступ к хранилищу браузера.");
  }
}

export function clearEndpointRunKey(actor: string, ticketId: string, acceptedKey: string): void {
  const location = storageKey(actor, ticketId);
  if (sessionStorage.getItem(location) === acceptedKey) sessionStorage.removeItem(location);
}
