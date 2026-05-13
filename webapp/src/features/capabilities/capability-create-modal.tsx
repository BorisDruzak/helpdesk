import { DatabaseZap, MonitorCog, PlugZap, ScreenShare, UserCheck, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";

type CapabilityCreateModalProps = {
  open: boolean;
  onClose: () => void;
};

const TARGET_CARDS = [
  {
    title: "Проверка на устройстве",
    target: "agent_builtin / agent_managed_module",
    description: "Через SDK Modules сейчас. Recipe runner появится позже.",
    status: "Phase 2",
    icon: MonitorCog,
    action: "open-modules",
  },
  {
    title: "Серверная проверка",
    target: "server_builtin",
    description: "MVP показывает DNS/HTTP checks из существующего server_builtin provider.",
    status: "Просмотр",
    icon: DatabaseZap,
  },
  {
    title: "API-коннектор",
    target: "server_connector",
    description: "Zabbix доступен через существующий provider/config слой.",
    status: "Zabbix",
    icon: PlugZap,
    action: "providers",
  },
  {
    title: "Удалённая помощь",
    target: "remote_assist",
    description: "Используется из Remote Assist через session capabilities.",
    status: "Готово",
    icon: ScreenShare,
  },
  {
    title: "Ручная проверка",
    target: "manual",
    description: "Manual evidence capabilities доступны из Diagnostic Center.",
    status: "Готово",
    icon: UserCheck,
  },
  {
    title: "SDK-модуль",
    target: "agent_managed_module",
    description: "ZIP/SDK-модуль агента создаётся и публикуется в Modules Workbench.",
    status: "Открыть",
    icon: MonitorCog,
    action: "open-modules",
  },
];

export function CapabilityCreateModal({ open, onClose }: CapabilityCreateModalProps) {
  const navigate = useNavigate();

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 py-6" role="dialog" aria-modal="true">
      <div className="w-full max-w-4xl rounded-[1.1rem] bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">Target-first wizard</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Создать capability</h2>
            <p className="mt-2 text-sm text-slate-500">
              MVP честно показывает доступные entrypoints и Phase 2 placeholders без фейкового сохранения.
            </p>
          </div>
          <Button aria-label="Закрыть" onClick={onClose} size="icon" variant="ghost">
            <X className="h-4 w-4" />
          </Button>
        </header>
        <div className="grid gap-4 p-6 md:grid-cols-2">
          {TARGET_CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <div className="rounded-[1rem] border border-border bg-white px-4 py-4" key={card.title}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[0.8rem] bg-brand-50 text-brand-700">
                      <Icon className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="font-semibold text-slate-950">{card.title}</p>
                      <p className="mt-1 text-xs text-slate-500">{card.target}</p>
                    </div>
                  </div>
                  <Badge tone={card.status === "Phase 2" ? "warning" : "info"}>{card.status}</Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-600">{card.description}</p>
                {card.action === "open-modules" ? (
                  <Button className="mt-4" onClick={() => navigate("/app/admin/modules")} size="sm" variant="outline">
                    Открыть Modules Workbench
                  </Button>
                ) : null}
                {card.action === "providers" ? (
                  <Button className="mt-4" onClick={onClose} size="sm" variant="outline">
                    Перейти к Providers
                  </Button>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
