import type { InputControl } from "./types";
export const INPUT_LABELS:Record<string,string>={target:"Адрес или имя",host:"Адрес или имя",count:"Количество пакетов",timeout_ms:"Тайм-аут, мс",port:"Порт",family:"Семейство адресов",name:"Имя",lookback_minutes:"За последние, мин",max_events:"Максимум событий",service_key:"Служба",profile:"Журнал",severity:"Уровень",path_key:"Расположение"};
export function inputLabel(name:string) {return INPUT_LABELS[name] ?? "Параметр";}
export function fixedValue(value:string|number) {return ({ipv4:"IPv4",ipv6:"IPv6",any:"Любое",endpoint_agent:"Агент Endpoint",endpoint_agent_updater:"Обновление Endpoint",print_service:"Служба печати",system:"Система",application:"Приложения",print:"Печать",endpoint:"Endpoint",error:"Ошибки",warning:"Предупреждения",information:"Информация",endpoint_install_root:"Каталог Endpoint",endpoint_data_root:"Данные Endpoint",endpoint_runtime_manifest:"Манифест Endpoint"} as Record<string,string>)[String(value)] ?? String(value);}
export function validControls(controls:readonly InputControl[]) {
  return Array.isArray(controls) && controls.length<=8 && controls.every(c=>c!=null && typeof c==="object") && new Set(controls.map(c=>c.name)).size===controls.length && controls.every(c=>
    /^[a-z][a-z0-9_]{0,63}$/.test(c.name) && ["integer","string"].includes(c.value_type) &&
    (c.minimum==null || Number.isSafeInteger(c.minimum)) && (c.maximum==null || Number.isSafeInteger(c.maximum)) &&
    (c.minimum==null || c.maximum==null || c.minimum<=c.maximum) && (c.enum_values==null || Array.isArray(c.enum_values) && c.enum_values.length>0 && c.enum_values.every((v:string)=>typeof v==="string")));
}
export function validateInputs(controls:readonly InputControl[],inputs:Readonly<Record<string,string|number>>) {
  if(!validControls(controls)) return "Формат параметров не поддерживается";
  if(Object.keys(inputs).length!==controls.length || controls.some(c=>!Object.hasOwn(inputs,c.name))) return "Заполните параметры проверки";
  for(const control of controls) {
    const value=inputs[control.name]; const label=inputLabel(control.name);
    if(control.value_type==="integer") {
      if(typeof value!=="number" || !Number.isSafeInteger(value) || control.minimum!=null && value<control.minimum || control.maximum!=null && value>control.maximum) return `${label}: проверьте допустимый диапазон`;
    } else {
      if(typeof value!=="string" || !value || value!==value.trim() || value.length>253 || /[\x00-\x1f\x7f]/.test(value)) return `${label}: введите корректное значение`;
      if(["target","host"].includes(control.name) && (/[\s/%\\]/.test(value) || value.includes("://"))) return "Укажите имя узла или IP-адрес без URL";
      if(control.enum_values!=null && !control.enum_values.includes(value)) return `${label}: выберите значение из списка`;
    }
  }
  return null;
}
