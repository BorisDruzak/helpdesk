import { Badge } from "../../../components/ui/badge";
import type { KnowledgeItem, KnowledgeItemVersion } from "../api";
import { statusLabel, type ValidationCheck } from "./knowledge-studio-model";

type EditorPublishStepProps = {
  selectedItem: KnowledgeItem | null;
  selectedVersion: KnowledgeItemVersion | null;
  validationChecks: ValidationCheck[];
};

export function EditorPublishStep({ selectedItem, selectedVersion, validationChecks }: EditorPublishStepProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold text-slate-950">Публикационный статус</p>
        <div className="mt-3 space-y-2 text-sm text-slate-700">
          <p>Материал: {selectedItem?.title ?? "не выбран"}</p>
          <p>Статус: {statusLabel(selectedItem?.status)}</p>
          <p>Выбранная версия: {selectedVersion ? `v${selectedVersion.version_number}` : "нет версии"}</p>
        </div>
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold text-slate-950">Готовность к публикации</p>
        <div className="mt-3 space-y-2">
          {validationChecks.map((check) => (
            <Badge key={check.key} tone={check.ok ? "success" : "neutral"}>
              {check.label}
            </Badge>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-500">Основные действия закреплены в правом inspector, чтобы publish/review не нужно было искать скроллом.</p>
      </div>
    </div>
  );
}
