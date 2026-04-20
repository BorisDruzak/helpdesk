import { WorkspaceSurface } from "../../shared/ui/workspace-surface";


export function AdminWorkspacePage() {
  return (
    <WorkspaceSurface
      eyebrow="Контур управления"
      title="Рабочее место администрирования"
      description="Здесь будут жить устройства, модули, техпанель и сценарии выкладки."
      featureList={[
        "Реестр устройств",
        "Выкладка агентов",
        "Мастерская модулей",
        "Техпанель observer"
      ]}
    />
  );
}
