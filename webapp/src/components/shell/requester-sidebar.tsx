import { Link } from "react-router-dom";
import { type AppNavItem, isNavItemActive, REQUESTER_HOME_PATH, REQUESTER_NEW_PATH, REQUESTER_PROFILE_PATH } from "../../app/navigation";
import { WorktimeLink } from "../../features/auth/worktime-link";

type Props = {
  items: AppNavItem[];
  currentPath: string;
  onNavigate?: () => void;
  worktimePortalUrl?: string | null;
  worktimeHandoffEnabled?: boolean;
};

export function RequesterSidebar({ items, currentPath, onNavigate, worktimePortalUrl, worktimeHandoffEnabled }: Props) {
  function navLink(item: AppNavItem) {
    const Icon = item.icon;
    return <Link key={item.to} aria-label={item.label} aria-current={isNavItemActive(item, currentPath) ? "page" : undefined} className="requester-sidebar__link" to={item.to} onClick={onNavigate}>
      <Icon aria-hidden="true" /><span>{item.label}</span>
    </Link>;
  }
  return <aside className="requester-sidebar">
    <Link aria-label="pc_client HelpDesk workspace" className="requester-sidebar__brand" to={REQUESTER_HOME_PATH} onClick={onNavigate}>
      <span aria-hidden="true" className="requester-sidebar__logo">PC</span>
      <span><strong>Служба поддержки</strong><small>Кабинет сотрудника</small></span>
    </Link>
    <nav aria-label="Боковая навигация заявителя" className="requester-sidebar__nav">
      {items.filter((item) => item.to !== REQUESTER_NEW_PATH && item.to !== REQUESTER_PROFILE_PATH).map(navLink)}
      <WorktimeLink handoffEnabled={worktimeHandoffEnabled} url={worktimePortalUrl} className="requester-sidebar__link" />
    </nav>
    <div className="requester-sidebar__footer">{items.filter((item) => item.to === REQUESTER_PROFILE_PATH).map(navLink)}</div>
  </aside>;
}
