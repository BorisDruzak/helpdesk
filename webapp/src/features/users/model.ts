import type { AdminRegistryPayload } from "../admin/api";
import type { UserAccount } from "./api";

export type Person = AdminRegistryPayload["people"][number];
export const roleLabels: Record<string, string> = {
  user: "Пользователь", support: "Сотрудник техподдержки", admin: "Администратор", auditor: "Аудитор",
};
export const emptyAccount = (): UserAccount => ({ user_login: "", actor_role: "user", is_active: true, queue_ids: [], group_ids: [] });
export function toggleId(ids: number[], id: number) {
  return ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id];
}
export const fieldClass = "field-base h-10 w-full px-3 text-sm";
export const labelClass = "grid gap-1.5 text-sm font-medium text-slate-700";
