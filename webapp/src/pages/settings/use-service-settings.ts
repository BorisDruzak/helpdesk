import {useServiceSettingsState} from './use-service-settings-state';
import {useServiceSettingsActions} from './use-service-settings-actions';
export function useServiceSettings(){const state=useServiceSettingsState();return {...state,...useServiceSettingsActions(state)};}
export type ServiceSettingsModel=ReturnType<typeof useServiceSettings>;
