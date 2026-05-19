import type { CommandCenterItem, CommandCenterSection } from "./api";

const SECTION_PRIORITY: Record<CommandCenterSection["key"], number> = {
  sla_risk: 10,
  ola_risk: 20,
  failed_operation: 30,
  unread_user_messages: 40,
  operator_action: 50,
  pending_consent: 60,
  pending_approval: 70,
  agent_offline_active: 80,
  closure_blocked: 90,
  similar_tickets_spike: 100,
  new_unassigned: 110,
  diagnostics_recommended: 120,
};

const CRITICAL_PRIORITY_BONUS = -5;

export type PrioritizedCommandCenterItem = CommandCenterItem & {
  reason_badges: string[];
  section_keys: CommandCenterSection["key"][];
};

export function buildPrioritizedAttentionList(
  sections: CommandCenterSection[],
  limit = 10,
): PrioritizedCommandCenterItem[] {
  const byTicket = new Map<string, PrioritizedCommandCenterItem & { priorityScore: number }>();

  for (const section of sections) {
    const baseScore = SECTION_PRIORITY[section.key] ?? 999;
    const score = baseScore + (section.severity === "critical" ? CRITICAL_PRIORITY_BONUS : 0);
    for (const item of section.items) {
      const key = item.similar_group?.group_key ?? item.ticket_id;
      const existing = byTicket.get(key);
      if (existing) {
        if (!existing.reason_badges.includes(section.title)) {
          existing.reason_badges.push(section.title);
        }
        if (!existing.section_keys.includes(section.key)) {
          existing.section_keys.push(section.key);
        }
        existing.priorityScore = Math.min(existing.priorityScore, score);
        continue;
      }
      byTicket.set(key, {
        ...item,
        reason_badges: [section.title],
        section_keys: [section.key],
        priorityScore: score,
      });
    }
  }

  return [...byTicket.values()]
    .sort((left, right) => {
      if (left.priorityScore !== right.priorityScore) {
        return left.priorityScore - right.priorityScore;
      }
      return String(right.updated_at ?? "").localeCompare(String(left.updated_at ?? ""));
    })
    .slice(0, Math.max(1, limit))
    .map(({ priorityScore: _priorityScore, ...item }) => item);
}
