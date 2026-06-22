import { Button, FieldShell, Input, Select, Stepper, Textarea } from "../../features/requester/ui/form-controls";
import { requesterDeviceLabel } from "../../features/requester/labels";
import type { DynamicFormValues } from "../../features/requester/dynamic-form";
import type {
  KnowledgeAttempt,
  RequestFormDefinition,
  RequesterContextPreview,
  RequesterDevice,
  RequesterOnBehalfPerson,
  ServiceCatalogCurrent,
} from "../../features/requester/types";

export type WizardStep = "problem" | "quick_help" | "details" | "review";
export const ASK_TICKET_CONTEXT_STORAGE_KEY = "pc_client.knowledge_ask.ticket_context";
const ASK_TICKET_CONTEXT_MAX_AGE_MS = 30 * 60 * 1000;
export const OWNER_CHANGE_INTENT = "device_owner_change";
export const OWNER_CHANGE_PROBLEM = "Нужно проверить владельца устройства";

export type AskTicketContext = {
  query?: string | null;
  created_at?: string | null;
  primary_item?: { item_id?: string | null; version_id?: string | null } | null;
  retrieval_results?: Array<{ item_id?: string | null; version_id?: string | null }>;
};

export type FormAvailability = {
  availableForSelf: boolean;
  availableForOnBehalf: boolean;
  availableWithoutProfile: boolean;
  availableWithoutDevice: boolean;
  requiresManualTriage: boolean;
  requiresOnBehalfForAvailability: boolean;
};

export type CategoryOption = {
  availability: FormAvailability;
  form: RequestFormDefinition;
  key: string;
  label: string;
  offering: (ServiceCatalogCurrent["services"][number]["offerings"][number] & { service_code: string }) | null;
  service: ServiceCatalogCurrent["services"][number] | null;
  serviceTitle: string | null;
};

export type RecommendedOffering = {
  confident: boolean;
  offering: ServiceCatalogCurrent["services"][number]["offerings"][number] & { service_code: string };
};

export function StepRail({ step }: { step: WizardStep }) {
  return (
    <Stepper
      current={step}
      steps={[
        { id: "problem", label: "Описание" },
        { id: "quick_help", label: "Подсказки" },
        { id: "details", label: "Детали" },
        { id: "review", label: "Проверка" },
      ]}
    />
  );
}

export function CategorySelector({
  canShowAll = false,
  onChange,
  onShowAll,
  options,
  recommendedKey,
  selectedKey,
}: {
  canShowAll?: boolean;
  onChange: (key: string) => void;
  onShowAll?: () => void;
  options: CategoryOption[];
  recommendedKey: string | null;
  selectedKey: string;
}) {
  return (
    <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-3">
      <FieldShell label="Выберите категорию обращения">
        <Select
          aria-label="Категория обращения"
          className="mt-2 w-full bg-white font-normal"
          onChange={(event) => onChange(event.currentTarget.value)}
          value={selectedKey}
        >
          <option value="">Выберите...</option>
          {options.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
              {option.key === recommendedKey ? " (подходит по описанию)" : ""}
            </option>
          ))}
        </Select>
      </FieldShell>
      {selectedKey ? (
        <p className="mt-2 text-xs text-slate-500">Вы можете изменить категорию перед проверкой и отправкой.</p>
      ) : (
        <p className="mt-2 text-xs text-slate-500">Автоматически первая форма не выбирается. Если нет точного совпадения, выберите вариант вручную.</p>
      )}
      {canShowAll ? (
        <Button className="mt-2" onClick={onShowAll} size="sm" type="button" variant="outline">
          Выбрать другую категорию
        </Button>
      ) : null}
    </div>
  );
}

export function OnBehalfPanel({
  enabled,
  onQueryChange,
  onReasonChange,
  onSearch,
  onSelect,
  people,
  policy,
  query,
  reason,
  required = false,
  selectedPerson,
  setEnabled,
}: {
  enabled: boolean;
  onQueryChange: (value: string) => void;
  onReasonChange: (value: string) => void;
  onSearch: () => void;
  onSelect: (person: RequesterOnBehalfPerson) => void;
  people: RequesterOnBehalfPerson[];
  policy: NonNullable<RequestFormDefinition["on_behalf_policy"]>;
  query: string;
  reason: string;
  required?: boolean;
  selectedPerson: RequesterOnBehalfPerson | null;
  setEnabled: (value: boolean) => void;
}) {
  return (
    <div className="mt-4 rounded-panel border border-slate-200 bg-slate-50 p-3">
      <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
        <input
          checked={enabled}
          disabled={required}
          onChange={(event) => setEnabled(event.currentTarget.checked)}
          type="checkbox"
        />
        {policy.label || "Обращение за другого сотрудника"}
      </label>
      {required ? <p className="mt-2 text-sm text-amber-700">Эта категория доступна только как обращение за другого сотрудника.</p> : null}
      {enabled ? (
        <div className="mt-3 grid gap-3">
          <FieldShell label="Найти сотрудника">
            <Input className="mt-1 w-full font-normal" onChange={(event) => onQueryChange(event.currentTarget.value)} value={query} />
          </FieldShell>
          <Button className="w-fit" onClick={onSearch} size="sm" type="button" variant="outline">Найти</Button>
          {people.map((person) => (
            <Button className="h-auto justify-start rounded-panel px-3 py-2 text-left text-sm" key={person.person_id} onClick={() => onSelect(person)} type="button" variant="outline">
              <span className="font-semibold">{person.display_name || person.full_name || person.email}</span>
              {selectedPerson?.person_id === person.person_id ? <span className="ml-2 text-brand-700">выбран</span> : null}
            </Button>
          ))}
          {policy.reason_required ? (
            <FieldShell label="Причина">
              <Textarea className="mt-1 min-h-20 font-normal" onChange={(event) => onReasonChange(event.currentTarget.value)} value={reason} />
            </FieldShell>
          ) : null}
          {selectedPerson?.primary_agent?.status === "missing" || selectedPerson?.primary_agent?.status === "ambiguous" ? (
            <p className="text-sm text-amber-700">У выбранного сотрудника нет однозначного основного устройства. Диагностика может быть недоступна.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function recommendOffering(
  services: ServiceCatalogCurrent["services"],
  problem: string,
  forms: RequestFormDefinition[],
  intent?: string,
): RecommendedOffering | null {
  const words = searchableWords(problem);
  if (intent === OWNER_CHANGE_INTENT) {
    words.push("device_owner_change", "ownership", "владел", "владель", "устройств");
  }
  const uniqueWords = Array.from(new Set(words));
  if (!uniqueWords.length) {
    return null;
  }
  const formByKey = new Map(forms.map((form) => [form.key, form]));
  let best:
    | {
        offering: ServiceCatalogCurrent["services"][number]["offerings"][number] & { service_code: string };
        score: number;
        strongScore: number;
      }
    | null = null;
  let secondBestStrongScore = 0;
  for (const service of services) {
    for (const offering of service.offerings ?? []) {
      const form = offering.request_template_key ? formByKey.get(offering.request_template_key) : null;
      const haystack = searchableText([
        service.title,
        service.description,
        service.service_code,
        offering.title,
        offering.description,
        offering.full_code,
        offering.offering_code,
        offering.request_template_key,
        form?.title,
        form?.description,
        form?.request_kind,
      ]);
      const titleHaystack = searchableText([offering.title, offering.full_code, offering.offering_code, offering.request_template_key, form?.title]);
      const score = uniqueWords.reduce((total, word) => total + (haystack.includes(word) ? 1 : 0), 0);
      const strongScore = uniqueWords.reduce(
        (total, word) => total + (!REQUEST_CATEGORY_GENERIC_WORDS.has(word) && titleHaystack.includes(word) ? 1 : 0),
        0,
      );
      if (score > 0 && (!best || strongScore > best.strongScore || (strongScore === best.strongScore && score > best.score))) {
        if (best) {
          secondBestStrongScore = Math.max(secondBestStrongScore, best.strongScore);
        }
        best = { offering: { ...offering, service_code: service.service_code }, score, strongScore };
      } else if (score > 0) {
        secondBestStrongScore = Math.max(secondBestStrongScore, strongScore);
      }
    }
  }
  if (!best) {
    return null;
  }
  const confident = intent === OWNER_CHANGE_INTENT || (best.strongScore > 0 && best.strongScore > secondBestStrongScore);
  return { confident, offering: best.offering };
}

const REQUEST_CATEGORY_GENERIC_WORDS = new Set([
  "вопрос",
  "кабинет",
  "мест",
  "нужн",
  "обращ",
  "помощ",
  "проблем",
  "рабоч",
  "систем",
  "устройств",
]);

function searchableWords(value: string): string[] {
  const words = String(value || "")
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .map((word) => word.trim())
    .filter((word) => word.length >= 4);
  const variants = words.flatMap((word) => {
    const stem = word.replace(/(ыми|ими|ого|ему|ому|ыми|ими|ая|яя|ое|ее|ой|ий|ый|ом|ем|ым|им|ую|юю|ах|ях|ам|ям|а|я|е|о|у|ы|и)$/u, "");
    return stem.length >= 4 && stem !== word ? [word, stem] : [word];
  });
  return Array.from(new Set(variants));
}

function searchableText(values: Array<string | null | undefined>): string {
  return values.map((value) => String(value || "").toLowerCase()).join(" ");
}

export function buildCategoryOptions(
  services: ServiceCatalogCurrent["services"],
  forms: RequestFormDefinition[],
  profileComplete: boolean,
  hasAgentContext: boolean,
): CategoryOption[] {
  const formByKey = new Map(forms.map((form) => [form.key, form]));
  const seenFormKeys = new Set<string>();
  const options: CategoryOption[] = [];
  for (const service of services) {
    for (const rawOffering of service.offerings ?? []) {
      const form = rawOffering.request_template_key ? formByKey.get(rawOffering.request_template_key) : null;
      if (!form) {
        continue;
      }
      const availability = formAvailabilityForRequester(form, profileComplete, hasAgentContext);
      if (!availability.availableForSelf && !availability.availableForOnBehalf) {
        continue;
      }
      const offering = { ...rawOffering, service_code: service.service_code };
      seenFormKeys.add(form.key);
      options.push({
        availability,
        form,
        key: categoryKeyForOffering(offering, form.key),
        label: offering.title || form.title,
        offering,
        service,
        serviceTitle: service.title || service.service_code,
      });
    }
  }
  for (const form of forms) {
    if (seenFormKeys.has(form.key)) {
      continue;
    }
    const availability = formAvailabilityForRequester(form, profileComplete, hasAgentContext);
    if (!availability.availableForSelf && !availability.availableForOnBehalf) {
      continue;
    }
    options.push({
      availability,
      form,
      key: `form:${form.key}`,
      label: form.title || form.key,
      offering: null,
      service: null,
      serviceTitle: null,
    });
  }
  return options;
}

function categoryKeyForOffering(
  offering: ServiceCatalogCurrent["services"][number]["offerings"][number] & { service_code: string },
  formKey: string,
): string {
  return `offering:${offering.full_code || `${offering.service_code}.${offering.offering_code || formKey}`}:${formKey}`;
}

export function resolveRecommendedCategoryKey(
  options: CategoryOption[],
  offering: (ServiceCatalogCurrent["services"][number]["offerings"][number] & { service_code: string }) | null,
  intent?: string,
): string | null {
  if (intent === OWNER_CHANGE_INTENT) {
    return options.find((option) => option.form.key === OWNER_CHANGE_INTENT || option.offering?.request_template_key === OWNER_CHANGE_INTENT)?.key ?? null;
  }
  if (!offering) {
    return null;
  }
  return (
    options.find((option) => option.offering?.full_code && option.offering.full_code === offering.full_code)?.key ??
    options.find((option) => option.form.key === offering.request_template_key)?.key ??
    null
  );
}

function formAvailabilityForRequester(form: RequestFormDefinition, profileComplete: boolean, hasAgentContext: boolean): FormAvailability {
  const policy = form.availability_policy ?? {};
  const availableWithoutProfile = Boolean(policy.available_without_completed_profile || form.available_without_completed_profile);
  const availableWithoutDevice = Boolean(policy.available_without_agent_binding || form.available_without_agent_binding);
  const profileOk = profileComplete || availableWithoutProfile;
  const deviceOk = hasAgentContext || availableWithoutDevice;
  const availableForSelf = profileOk && deviceOk;
  const availableForOnBehalf = Boolean(form.on_behalf_policy?.allowed && profileOk);
  return {
    availableForSelf,
    availableForOnBehalf,
    availableWithoutProfile,
    availableWithoutDevice,
    requiresManualTriage: Boolean(policy.requires_manual_triage),
    requiresOnBehalfForAvailability: !availableForSelf && availableForOnBehalf,
  };
}

export function requesterFormPrefillFromContext(
  context: RequesterContextPreview | null | undefined,
  profile: { display_name?: string | null; full_name?: string | null; department_id?: string | null; location_id?: string | null; email?: string | null; phone?: string | null } | null | undefined,
  device: RequesterDevice | null,
  service: ServiceCatalogCurrent["services"][number] | null,
  offering: (ServiceCatalogCurrent["services"][number]["offerings"][number] & { service_code: string }) | null,
): DynamicFormValues {
  const values: DynamicFormValues = {};
  Object.entries(context?.form_prefill ?? {}).forEach(([key, value]) => {
    values[key] = Array.isArray(value) ? value.map((item) => String(item)) : typeof value === "boolean" ? value : String(value ?? "");
  });
  if (!device) {
    delete values.device_id;
    delete values.device;
  }
  if (profile?.department_id) values.department_id = profile.department_id;
  if (profile?.location_id) values.location_id = profile.location_id;
  if (profile?.phone) values.phone = profile.phone;
  if (profile?.email) values.email = profile.email;
  if (profile?.display_name || profile?.full_name) values.requester_name = profile.display_name || profile.full_name || "";
  if (device) {
    values.device_id = device.device_id;
    values.device = requesterDeviceLabel(device, "Основное устройство");
  }
  if (service) {
    values.service_code = service.service_code;
    values.service = service.title || service.service_code;
  }
  if (offering) {
    values.offering_code = offering.offering_code;
    values.offering_full_code = offering.full_code;
    values.offering = offering.title || offering.full_code;
  }
  return values;
}

export function isResolvedPrimaryDeviceStatus(status: string): boolean {
  return !status || status === "available" || status === "resolved";
}

export function primaryDeviceResolutionText(resolution: RequesterContextPreview | RequesterDevice | unknown): string {
  const status = String((resolution as { status?: unknown } | null | undefined)?.status ?? "").trim().toLowerCase();
  if (status === "ambiguous") {
    return "Основное устройство требует уточнения.";
  }
  if (status === "missing") {
    return "Основное устройство не найдено.";
  }
  return "Устройство не выбрано.";
}

export function deviceMetadata(device: RequesterDevice): Record<string, unknown> {
  return {
    device_id: device.device_id,
    hostname: device.hostname,
    os: device.os,
    agent_version: device.agent_version,
    asset_id: device.asset_id,
    asset_name: device.asset_name,
  };
}

export function stepTitle(step: WizardStep): string {
  return {
    problem: "Опишите проблему",
    quick_help: "Быстрые подсказки",
    details: "Детали обращения",
    review: "Проверка",
  }[step];
}

export function readAskContext(): AskTicketContext | null {
  try {
    const raw = window.sessionStorage.getItem(ASK_TICKET_CONTEXT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AskTicketContext;
    const createdAt = parsed.created_at ? Date.parse(parsed.created_at) : 0;
    if (createdAt && Date.now() - createdAt > ASK_TICKET_CONTEXT_MAX_AGE_MS) {
      window.sessionStorage.removeItem(ASK_TICKET_CONTEXT_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function askContextAttempts(context: AskTicketContext): KnowledgeAttempt[] {
  const now = new Date().toISOString();
  const items = context.primary_item?.item_id ? [context.primary_item, ...(context.retrieval_results ?? [])] : context.retrieval_results ?? [];
  const seen = new Set<string>();
  return items
    .map((item) => ({ item_id: item?.item_id ?? "", version_id: item?.version_id ?? null }))
    .filter((item) => {
      if (!item.item_id || seen.has(item.item_id)) return false;
      seen.add(item.item_id);
      return true;
    })
    .slice(0, 5)
    .map((item) => ({ ...item, result: "ticket_created_after_view" as const, surface: "requester_portal" as const, timestamp: now }));
}
