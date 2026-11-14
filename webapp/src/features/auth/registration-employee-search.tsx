import { useEffect, useState } from "react";

import { Input } from "../../components/ui/input";
import { searchRegistrationEmployees, type RegistrationEmployee } from "./requester-registration";

type Props = {
  selected: RegistrationEmployee | null;
  onInput: (name: string) => void;
  onSelect: (employee: RegistrationEmployee) => void;
};

export function RegistrationEmployeeSearch({ selected, onInput, onSelect }: Props) {
  const [input, setInput] = useState(selected?.full_name ?? "");
  const [results, setResults] = useState<RegistrationEmployee[]>([]);
  const [message, setMessage] = useState("");
  const query = input.normalize("NFC").trim().replace(/\s+/g, " ");
  const canSearch = /^\p{L}[\p{L}-]{2,} \p{L}[\p{L}-]+(?: [\p{L}-]+)*$/u.test(query);

  useEffect(() => {
    if (!canSearch || selected) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchRegistrationEmployees(query, controller.signal);
        if (controller.signal.aborted) return;
        setResults(result.people);
        setMessage(result.refine ? "Уточните ФИО или добавьте отдел."
          : result.people.length ? "" : "Совпадений нет. Можно продолжить регистрацию вручную.");
      } catch {
        if (!controller.signal.aborted) setMessage("Поиск недоступен. Можно продолжить регистрацию вручную.");
      }
    }, 400);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [canSearch, query, selected]);

  return (
    <div className="space-y-2">
      <label className="block space-y-1 text-sm font-medium">
        ФИО
        <Input autoComplete="off" maxLength={120} value={input} placeholder="Фамилия и первые буквы имени"
          onChange={(event) => {
            setInput(event.target.value);
            setResults([]);
            setMessage("");
            onInput(event.target.value);
          }} />
      </label>
      {message ? <p role="status" className="text-sm text-slate-600">{message}</p> : null}
      {results.length && !selected ? (
        <ul aria-label="Найденные сотрудники" className="divide-y rounded-xl border">
          {results.map((employee, index) => (
            <li key={index}>
              <button type="button" className="w-full break-words px-3 py-2 text-left text-sm hover:bg-slate-50 focus-visible:outline-brand-600"
                onClick={() => {
                  setInput(employee.full_name);
                  setResults([]);
                  onSelect(employee);
                }}>
                <span className="block font-medium">{employee.full_name}</span>
                <span className="text-slate-600">{employee.department}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {selected ? (
        <p role="status" className="text-sm text-slate-700">
          {selected.department}. {selected.has_agent
            ? "Найден привязанный агент. Для доступа к компьютеру подтвердите запись приглашением или обратитесь в техподдержку."
            : "Привязанный агент не найден. Можно продолжить обычную регистрацию."}
        </p>
      ) : null}
    </div>
  );
}
