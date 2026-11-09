import type {ServiceSettingsModel} from './use-service-settings';
import {ProcessSummary} from './process-summary';
import {ProcessReference} from './process-reference';
import {WorkflowProfiles} from './workflow-profiles';
import {LifecycleReference} from './lifecycle-reference';
import {ProcessLinks} from './process-links';
export function TicketsSettingsSection({model}:{model:ServiceSettingsModel}){return <div className="space-y-4"><WorkflowProfiles model={model}/><ProcessSummary model={model}/><ProcessReference model={model}/><LifecycleReference model={model}/><ProcessLinks model={model}/></div>;}
