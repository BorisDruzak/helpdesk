import { useEffect, useId, useState } from "react";

import { Input } from "../../components/ui/input";
import { searchRegistrationEmployees, type RegistrationEmployee } from "./requester-registration";

type SearchOutcome =
  | { kind: "match"; people: RegistrationEmployee[]; refine: boolean }
  | { kind: "ambiguous" | "missing" | "unavailable" | "manual" };

const messages = {
  idle: "Начните вводить имя или фамилию.",
  pending: "Ищем сотрудника…",
  ambiguous: "Найдено несколько совпадений. Уточните ФИО или добавьте отдел.",
  missing: "Сотрудник не найден. Введите ФИО вручную.",
  unavailable: "Поиск недоступен. Введите ФИО вручную.",
  manual: "Введите ФИО вручную.",
} as const;

export function useRegistrationEmployeeSearch(enabled: boolean) {
  const [input, setInput] = useState("");
  const [outcome, setOutcome] = useState<SearchOutcome | null>(null);
  const query = input.normalize("NFC").trim().replace(/\s+/g, " ");
  const canSearch = /^\p{L}[\p{L} -]*$/u.test(query);

  useEffect(() => {
    if (!enabled || !canSearch || outcome) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchRegistrationEmployees(query, controller.signal);
        if (controller.signal.aborted) return;
        if (result.people.length) setOutcome({ kind: "match", people: result.people, refine: result.refine });
        else if (result.refine) setOutcome({ kind: "ambiguous" });
        else setOutcome({ kind: "missing" });
      } catch {
        if (!controller.signal.aborted) setOutcome({ kind: "unavailable" });
      }
    }, 400);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [enabled, canSearch, outcome, query]);

  function changeInput(value: string) {
    setInput(value);
    setOutcome(null);
  }

  const status: SearchOutcome["kind"] | "pending" | "idle" =
    outcome?.kind ?? (canSearch ? "pending" : "idle");
  return {
    input,
    changeInput,
    outcome,
    offerManualEntry: !outcome || outcome.kind === "ambiguous",
    enterManually: () => setOutcome({ kind: "manual" }),
    status,
  };
}

type Props = {
  search: ReturnType<typeof useRegistrationEmployeeSearch>;
  selected: RegistrationEmployee | null;
  onInput: (value: string) => void;
  onSelect: (employee: RegistrationEmployee) => void;
};

export function RegistrationEmployeeSearch({ search, selected, onInput, onSelect }: Props) {
  const statusId = useId();
  const matches = search.outcome?.kind === "match" ? search.outcome.people : [];
  const searchMessage = search.status === "match"
    ? search.outcome?.kind === "match" && search.outcome.refine ? "Показаны первые совпадения. Уточните ФИО или отдел, если нужного сотрудника нет в списке."
      : "Выберите сотрудника. Если аккаунт уже создан, войдите в Helpdesk."
    : messages[search.status];

  return (
    <div className="space-y-2">
      <label className="block space-y-1 text-sm font-medium">
        Поиск сотрудника
        <Input className="block w-full" autoComplete="off" maxLength={120}
          value={selected?.full_name ?? search.input} placeholder="Имя или фамилия"
          aria-describedby={statusId} onChange={(event) => onInput(event.target.value)} />
      </label>
      <p id={statusId} role="status" className="text-sm text-slate-700">
        {selected ? `${selected.department ? `${selected.department}. ` : ""}${selected.has_agent
            ? "Найден привязанный агент. Для доступа к компьютеру подтвердите запись приглашением или обратитесь в техподдержку."
            : "Привязанный агент не найден. Можно продолжить обычную регистрацию."}`
          : searchMessage}
      </p>
      {matches.length > 0 && !selected ? <ul className="space-y-2" aria-label="Найденные сотрудники">
        {matches.map((match, index) => <li key={`${match.full_name}:${match.department}:${index}`}>
        <button type="button"
          disabled={match.registered}
          className="w-full break-words rounded-xl border px-3 py-2 text-left text-sm hover:bg-slate-50 focus-visible:outline-brand-600 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
          onClick={() => { if (!match.registered) onSelect(match); }}>
          <span className="block font-medium">{match.full_name}</span>
          {match.department ? <span className="text-slate-600">{match.department}</span> : null}
          {match.registered ? <span className="mt-1 block font-medium">Аккаунт уже создан</span> : null}
        </button>
        </li>)}
      </ul> : null}
      {search.offerManualEntry && !selected ? (
        <button type="button" className="text-sm font-semibold text-brand-700 underline"
          onClick={search.enterManually}>Ввести ФИО вручную</button>
      ) : null}
    </div>
  );
}
