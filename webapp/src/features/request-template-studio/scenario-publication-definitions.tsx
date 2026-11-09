import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { ScenarioMapProcessing } from "./scenario-map-processing";

/** Explicit, scoped management also covers legacy and unattached map definitions. */
export function ScenarioPublicationDefinitions({ definition, disabled, onChange }: { definition: ScenarioDraftDefinition; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
 const [open, setOpen] = useState(false);
 const [section, setSection] = useState<"route" | "sla">("route");
 const [routeKey, setRouteKey] = useState<string | null>(null), [slaKey, setSlaKey] = useState<string | null>(null);
 const processing = definition.processing;
 if (!processing) return null;
 const choices = section === "route" ? processing.routes : processing.sla_profiles;
 const requested = section === "route" ? routeKey : slaKey;
 const fallback = section === "route" ? processing.defaults.route : processing.defaults.sla_profile;
 const selected = requested !== null && choices[requested] ? requested : choices[fallback] ? fallback : Object.keys(choices)[0] ?? "";
 const select = (key: string) => section === "route" ? setRouteKey(key) : setSlaKey(key);
 return <div className="space-y-3">
  <Button variant="outline" aria-expanded={open} onClick={() => setOpen(value => !value)}>Настроить направления и профили карты</Button>
  {open && <section aria-label="Направления и профили карты" className="space-y-3 rounded border p-3">
   <p className="text-sm text-slate-600">Здесь можно настроить сохранённые направления и профили, включая используемые в переходах и исторических картах. Изменение действует везде, где выбран этот профиль или направление; резервные назначения выше сохраняются отдельно.</p>
   <div className="flex flex-wrap gap-2"><Button variant={section === "route" ? "secondary" : "ghost"} onClick={() => setSection("route")}>Направления карты</Button><Button variant={section === "sla" ? "secondary" : "ghost"} onClick={() => setSection("sla")}>Профили SLA карты</Button></div>
   <label className="block">{section === "route" ? "Направление для редактирования" : "Профиль для редактирования"}<Select disabled={disabled || !Object.keys(choices).length} value={selected} onChange={event => select(event.target.value)}>{!Object.keys(choices).length && <option value="">Настройки пока не созданы</option>}{Object.entries(choices).map(([key, value]) => <option key={key} value={key}>{value.title}</option>)}</Select></label>
   <ScenarioMapProcessing key={`${section}:${selected}`} definition={definition} disabled={disabled} onChange={onChange} section={section} itemKey={selected} onCreated={(next, key) => { select(key); onChange(next); }} />
  </section>}
 </div>;
}
