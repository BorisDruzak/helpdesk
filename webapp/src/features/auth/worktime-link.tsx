import { Clock3 } from "lucide-react";

export function WorktimeLink({ url, className }: { url?: string | null; className?: string }) {
  if (url !== "https://endpoint.sosnadmin.local/employee" && url !== "https://endpoint-staging.sosnadmin.local/employee") return null;
  return <a className={className} href={url} referrerPolicy="no-referrer">
    <Clock3 aria-hidden="true" className="h-4 w-4 shrink-0" />
    Рабочее время
  </a>;
}
