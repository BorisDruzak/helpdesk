import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { Tabs } from "../../components/ui/tabs";
import { fetchKnowledgeItems, fetchKnowledgeMetadata } from "./api";
import { MetadataApplicabilityPanel } from "./metadata-applicability-panel";
import { MetadataPropertyPanel } from "./metadata-property-panel";
import { MetadataQualityPanel } from "./metadata-quality-panel";
import { MetadataTaxonomyPanel } from "./metadata-taxonomy-panel";

const tabs = [
  { label: "Таксономия", value: "taxonomy" },
  { label: "Свойства", value: "properties" },
  { label: "Применимость", value: "applicability" },
  { label: "Модель качества", value: "quality" },
];

export function KnowledgeMetadataPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("taxonomy");
  const metadataQuery = useQuery({ queryKey: ["knowledge-metadata"], queryFn: fetchKnowledgeMetadata });
  const itemsQuery = useQuery({ queryKey: ["knowledge-items"], queryFn: fetchKnowledgeItems });
  const metadata = metadataQuery.data;
  const summary = metadata?.summary;

  function refreshMetadata() {
    queryClient.invalidateQueries({ queryKey: ["knowledge-metadata"] });
    queryClient.invalidateQueries({ queryKey: ["knowledge-quality"] });
  }

  return (
    <section className="space-y-5">
      <PageHeading
        eyebrow="Управление базой знаний"
        title="Метаданные знаний"
        description="Редактируемые категории, свойства, применимость и модель качества для управляемой базы знаний."
      />

      <div className="grid gap-3 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Активные термины</CardTitle>
            <CardDescription>Только active</CardDescription>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{summary?.taxonomy_terms_active ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Активные свойства</CardTitle>
            <CardDescription>Без draft/archive</CardDescription>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{summary?.property_definitions_active ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Правила применимости</CardTitle>
            <CardDescription>Для видимых статей</CardDescription>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{summary?.applicability_rules_active ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Модели качества</CardTitle>
            <CardDescription>Активные модели</CardDescription>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{summary?.quality_models_active ?? 0}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5" />
            Редактор метаданных
          </CardTitle>
          <CardDescription>Все изменения проходят через защищённые `/api/web/knowledge/*` endpoints и backend ACL.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Tabs items={tabs} onValueChange={setActiveTab} value={activeTab} />
          {metadataQuery.isLoading ? <p className="text-sm text-slate-500">Загрузка метаданных...</p> : null}
          {metadataQuery.isError ? <p className="text-sm text-red-700">Не удалось загрузить метаданные знаний.</p> : null}
          {activeTab === "taxonomy" ? <MetadataTaxonomyPanel metadata={metadata} onChanged={refreshMetadata} /> : null}
          {activeTab === "properties" ? <MetadataPropertyPanel metadata={metadata} onChanged={refreshMetadata} /> : null}
          {activeTab === "applicability" ? (
            <MetadataApplicabilityPanel items={itemsQuery.data ?? []} metadata={metadata} onChanged={refreshMetadata} />
          ) : null}
          {activeTab === "quality" ? <MetadataQualityPanel metadata={metadata} onChanged={refreshMetadata} /> : null}
        </CardContent>
      </Card>
    </section>
  );
}
