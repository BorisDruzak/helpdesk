import {OverviewSettingsSection} from './overview-settings-section';
import {TicketsSettingsSection} from './tickets-settings-section';
import {NotificationsSettingsSection} from './notifications-settings-section';
import {QueuesSettingsSection} from './queues-settings-section';
import {RoutingSettingsSection} from './routing-settings-section';
import {SlaSettingsSection} from './sla-settings-section';
import {CalendarsSettingsSection} from './calendars-settings-section';
import {ResolutionSettingsSection} from './resolution-settings-section';
import {AuditSettingsSection} from './audit-settings-section';
import type {ServiceSettingsModel} from './use-service-settings';
export function ServiceSettingsSection({model}:{model:ServiceSettingsModel}){switch(model.activeTab){case 'overview': return <OverviewSettingsSection model={model}/>;
case 'tickets': return <TicketsSettingsSection model={model}/>;
case 'notifications': return <NotificationsSettingsSection model={model}/>;
case 'queues': return <QueuesSettingsSection model={model}/>;
case 'routing': return <RoutingSettingsSection model={model}/>;
case 'sla': return <SlaSettingsSection model={model}/>;
case 'calendars': return <CalendarsSettingsSection model={model}/>;
case 'resolution': return <ResolutionSettingsSection model={model}/>;
case 'audit': return <AuditSettingsSection model={model}/>;}}
