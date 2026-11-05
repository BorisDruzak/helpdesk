import { Clock3 } from "lucide-react";

export function WorktimeLink({ url, className, handoffEnabled=false }: { url?: string | null; className?: string;handoffEnabled?:boolean }) {
  if (url !== "https://endpoint.sosnadmin.local/employee" && url !== "https://endpoint-staging.sosnadmin.local/employee") return null;
  const target=handoffEnabled ? url.replace('/employee','/auth/worktime/helpdesk/login') : url;
  return <a className={className} href={target} referrerPolicy="no-referrer">
    <Clock3 aria-hidden="true" className="h-4 w-4 shrink-0" />
    Рабочее время
  </a>;
}
