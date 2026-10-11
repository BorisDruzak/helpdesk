import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ScenarioCatalog } from "./scenario-api";
import type { useScenarioEditor } from "./use-scenario-editor";

/** Preserve entry links from Forms, Service Catalog and Policy Health. */
export function useScenarioContext(catalog: ScenarioCatalog | undefined, editor: ReturnType<typeof useScenarioEditor>, canEdit: boolean) {
  const [params] = useSearchParams();
  const applied = useRef(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (!catalog || applied.current) return;
    applied.current = true;
    const offeringCode = params.get("offering"), template = params.get("template"), service = params.get("service");
    if (!offeringCode && !template && !service) return;
    if (catalog.offset > 0 || catalog.total > catalog.limit) {
      setNotice("Каталог содержит несколько страниц. Найдите услугу через поиск и откройте её сценарий; автоматическое создание по неполному каталогу отключено.");
      return;
    }
    const offerings = catalog.offerings.filter(item => (!offeringCode || item.full_code === offeringCode) && (!template || item.request_template_key === template) && (!service || item.service_code === service));
    if (offerings.length !== 1) { setNotice("Выберите услугу в каталоге: по ссылке найдено несколько вариантов или услуга недоступна."); return; }
    const offering = offerings[0];
    const existing = catalog.scenarios.filter(item => item.offering_full_code === offering.full_code && !item.archived);
    if (existing.length === 1) { void editor.open(existing[0].id); return; }
    if (existing.length > 1 || !canEdit || !offering.request_template_key || !offering.service_code) { setNotice("Выберите существующий сценарий услуги в каталоге."); return; }
    editor.create({ scenario_key: "new_scenario", service_code: offering.service_code, offering_full_code: offering.full_code,
      title: offering.public_title, description: offering.short_description ?? "", category_id: null, blocks: [], entry_block_id: null,
      process_binding: { request_template_key: offering.request_template_key } }, false);
  }, [catalog, params, editor, canEdit]);
  return notice;
}
