import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { saveKnowledgeApplicabilityRules, type KnowledgeApplicabilityRule, type KnowledgeItem, type KnowledgeMetadataBundle } from "./api";
import { MetadataApplicabilityEditor } from "./metadata-applicability-editor";
import { fieldClass, termsForSpace } from "./metadata-editor-common";

export function MetadataApplicabilityPanel({
  items,
  metadata,
  onChanged,
}: {
  items: KnowledgeItem[];
  metadata?: KnowledgeMetadataBundle;
  onChanged: () => void;
}) {
  const [itemId, setItemId] = useState("");
  const selectedItem = items.find((item) => item.item_id === itemId) ?? items[0] ?? null;
  const currentMetadata = (metadata?.item_metadata ?? []).find((row) => row.item_id === selectedItem?.item_id);
  const [rules, setRules] = useState<Array<Partial<KnowledgeApplicabilityRule>>>([]);
  const [saveMessage, setSaveMessage] = useState("");
  const taxonomyTerms = useMemo(() => termsForSpace(metadata, selectedItem?.space_id ?? ""), [metadata, selectedItem?.space_id]);

  useEffect(() => {
    if (!itemId && items[0]?.item_id) {
      setItemId(items[0].item_id);
    }
  }, [itemId, items]);

  useEffect(() => {
    setRules(currentMetadata?.applicability_rules ?? []);
    setSaveMessage("");
  }, [currentMetadata?.item_id]);

  const saveMutation = useMutation({
    onMutate: () => setSaveMessage(""),
    mutationFn: () => saveKnowledgeApplicabilityRules(selectedItem?.item_id ?? "", rules),
    onSuccess: () => {
      setSaveMessage("Применимость сохранена");
      onChanged();
    },
    onError: () => setSaveMessage("Не удалось сохранить применимость"),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Правила применимости</CardTitle>
          <CardDescription>Выберите статью и настройте, где она должна включаться или исключаться из рекомендаций.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="block max-w-xl text-sm font-medium">
            Статья
            <select className={fieldClass} value={selectedItem?.item_id ?? ""} onChange={(event) => setItemId(event.target.value)}>
              {items.map((item) => (
                <option key={item.item_id} value={item.item_id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <MetadataApplicabilityEditor
            addButtonLabel="Добавить правило"
            emptyMessage="Для выбранной статьи правил пока нет."
            onRulesChange={setRules}
            onSave={() => saveMutation.mutate()}
            rules={rules}
            saveButtonLabel="Сохранить применимость"
            saveDisabled={!selectedItem}
            saveMessage={saveMessage}
            savePending={saveMutation.isPending}
            scopeTypeLabelText="Тип области"
            taxonomyTerms={taxonomyTerms}
            updateButtonLabel="Обновить правило"
          />
        </CardContent>
      </Card>
    </div>
  );
}
