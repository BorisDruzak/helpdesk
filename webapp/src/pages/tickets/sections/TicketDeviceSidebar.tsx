import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import {
  describePresence,
} from '../detail-formatting';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketDeviceSidebar({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { ticketId, detail } = controller;
  if (!ticketId) return null;
  if (!detail) return null;
  return (<Card>
    <CardHeader>
      <CardTitle>Устройство и присутствие</CardTitle>
    </CardHeader>
    <CardContent className="space-y-4 text-sm">
      <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
        <p className="font-semibold text-slate-950">
          {detail?.snapshot.device.hostname ?? detail?.snapshot.device.device_id ?? "Нет привязки"}
        </p>
        <p className="mt-1 text-slate-500">{detail?.snapshot.device.os ?? "ОС не определена"}</p>
        <p className="mt-2 text-slate-500">
          Агент: {detail?.snapshot.device.agent_version ?? "нет данных"} •{" "}
          {detail?.snapshot.device.connection_state === "unknown" ? "состояние неизвестно" : detail?.snapshot.device.online ? "онлайн" : "офлайн"}
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-slate-500">Пользователь</span>
          <span className="font-medium text-slate-900">
            {describePresence(detail?.snapshot.presence.requester_online ?? false)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-500">Поддержка</span>
          <span className="font-medium text-slate-900">
            {describePresence(detail?.snapshot.presence.support_online ?? false)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-500">Агент</span>
          <span className="font-medium text-slate-900">
            {detail?.snapshot.device.connection_state === "unknown" ? "Состояние неизвестно" : describePresence(detail?.snapshot.presence.agent_online ?? false)}
          </span>
        </div>
      </div>
    </CardContent>
  </Card>);
}