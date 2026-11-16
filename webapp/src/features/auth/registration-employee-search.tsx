import { useEffect, useId, useState } from "react";

import { Input } from "../../components/ui/input";
import { searchRegistrationEmployees, type RegistrationEmployee } from "./requester-registration";

type SearchOutcome =
  | { kind: "match"; employee: RegistrationEmployee }
  | { kind: "ambiguous" | "missing" | "unavailable" | "manual" };

const messages = {
  idle: "Введите фамилию и хотя бы две буквы имени.",
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
  const canSearch = /^\p{L}[\p{L}-]{2,} \p{L}[\p{L}-]+(?: [\p{L}-]+)*$/u.test(query);

  useEffect(() => {
    if (!enabled || !canSearch || outcome) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchRegistrationEmployees(query, controller.signal);
        if (controller.signal.aborted) return;
        if (result.refine || result.people.length > 1) setOutcome({ kind: "ambiguous" });
        else if (result.people.length === 1) setOutcome({ kind: "match", employee: result.people[0] });
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
    offerManualEntry: !canSearch && query.includes(" ") && !outcome,
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
  const match = search.outcome?.kind === "match" ? search.outcome.employee : null;

  return (
    <div className="space-y-2">
      <label className="block space-y-1 text-sm font-medium">
        Поиск сотрудника
        <Input className="block w-full" autoComplete="off" maxLength={120}
          value={selected?.full_name ?? search.input} placeholder="Фамилия и первые буквы имени"
          aria-describedby={statusId} onChange={(event) => onInput(event.target.value)} />
      </label>
      <p id={statusId} role="status" className="text-sm text-slate-700">
        {selected ? `${selected.department}. ${selected.has_agent
            ? "Найден привязанный агент. Для доступа к компьютеру подтвердите запись приглашением или обратитесь в техподдержку."
            : "Привязанный агент не найден. Можно продолжить обычную регистрацию."}`
          : search.status === "match" ? "Выберите найденного сотрудника." : messages[search.status]}
      </p>
      {match && !selected ? (
        <button type="button"
          className="w-full break-words rounded-xl border px-3 py-2 text-left text-sm hover:bg-slate-50 focus-visible:outline-brand-600"
          onClick={() => onSelect(match)}>
          <span className="block font-medium">{match.full_name}</span>
          <span className="text-slate-600">{match.department}</span>
        </button>
      ) : null}
      {search.offerManualEntry && !selected ? (
        <button type="button" className="text-sm font-semibold text-brand-700 underline"
          onClick={search.enterManually}>Ввести ФИО вручную</button>
      ) : null}
    </div>
  );
}
