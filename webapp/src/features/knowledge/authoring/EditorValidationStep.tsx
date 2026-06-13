import { CheckCircle2, GitCompare } from "lucide-react";

import type { ValidationCheck } from "./knowledge-studio-model";

type EditorValidationStepProps = {
  activeSegmentsCount: number;
  currentDiff: { added: string[]; removed: string[] };
  validationChecks: ValidationCheck[];
};

export function EditorValidationStep({ activeSegmentsCount, currentDiff, validationChecks }: EditorValidationStepProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <CheckCircle2 className="h-4 w-4" />
          Computed checklist
        </p>
        <div className="mt-3 space-y-2">
          {validationChecks.map((check) => (
            <div className="flex items-start gap-2 text-sm" key={check.key}>
              <span className={`mt-1 h-3 w-3 rounded-full ${check.ok ? "bg-emerald-500" : "bg-slate-300"}`} />
              <span>
                <span className={check.ok ? "text-slate-900" : "text-slate-500"}>{check.label}</span>
                {check.detail ? <span className="block text-xs text-slate-500">{check.detail}</span> : null}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-500">Сегменты версии: {activeSegmentsCount}. Остальные проверки считаются локально по текущему draft.</p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <GitCompare className="h-4 w-4" />
          Diff текущего draft
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="rounded-md bg-emerald-50 p-3">
            <p className="text-sm font-semibold text-emerald-800">Добавлено: {currentDiff.added.length}</p>
            <ul className="mt-2 max-h-48 space-y-1 overflow-auto text-xs text-emerald-900">
              {currentDiff.added.slice(0, 8).map((line) => (
                <li key={line}>+ {line}</li>
              ))}
              {!currentDiff.added.length ? <li>Новых строк нет</li> : null}
            </ul>
          </div>
          <div className="rounded-md bg-rose-50 p-3">
            <p className="text-sm font-semibold text-rose-800">Удалено: {currentDiff.removed.length}</p>
            <ul className="mt-2 max-h-48 space-y-1 overflow-auto text-xs text-rose-900">
              {currentDiff.removed.slice(0, 8).map((line) => (
                <li key={line}>- {line}</li>
              ))}
              {!currentDiff.removed.length ? <li>Удалённых строк нет</li> : null}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
