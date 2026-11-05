import { useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import endpointTrayImage from "../../assets/guides/endpoint-tray-windows.png";
import endpointMenuImage from "../../assets/guides/endpoint-helpdesk-menu.png";

export function DeviceConnectionGuide() {
  const [platform, setPlatform] = useState<"windows" | "linux">("windows");
  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? "windows" : event.key === "End" ? "linux" : platform === "windows" ? "linux" : "windows";
    setPlatform(next);
    document.getElementById(`device-guide-tab-${next}`)?.focus();
  }
  return <>
    <h2 className="mt-4 font-semibold text-slate-950">Где взять код</h2>
    <div aria-label="Операционная система компьютера" role="tablist" className="mt-3 flex flex-wrap gap-2">
      {([ ["windows", "Windows"], ["linux", "Linux / ALT Linux"] ] as const).map(([key, label]) =>
        <button key={key} id={`device-guide-tab-${key}`} type="button" role="tab" aria-selected={platform === key} aria-controls={`device-guide-panel-${key}`} tabIndex={platform === key ? 0 : -1}
          onKeyDown={handleTabKey} onClick={() => setPlatform(key)}
          className={`rounded-lg border px-4 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-brand-600 ${platform === key ? "border-brand-700 bg-brand-50 text-brand-800" : "border-border bg-white text-slate-600"}`}>{label}</button>)}
    </div>
    <div role="tabpanel" id={`device-guide-panel-${platform}`} aria-labelledby={`device-guide-tab-${platform}`} className="mt-3" tabIndex={0}>
      {platform === "windows" ? <>
        <ol className="list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-700">
          <li>На этом компьютере нажмите стрелку «Показать скрытые значки» рядом с часами Windows. Найдите зелёный значок Endpoint Agent.</li>
          <li>Нажмите на значок правой кнопкой мыши и выберите «Привязать компьютер к Helpdesk».</li>
          <li>В открывшемся окне нажмите «Скопировать код», затем вставьте его в поле ниже.</li>
        </ol>
        <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold text-brand-700">Показать на скриншотах</summary>
          <div className="mt-3 grid items-start gap-3 sm:grid-cols-2">
            <figure><img src={endpointTrayImage} width="273" height="441" alt="Скрытые значки Windows: стрелка указывает на зелёный значок Endpoint Agent" className="h-auto max-w-full rounded-lg border"/><figcaption className="mt-1 text-slate-600">1. Найдите значок агента.</figcaption></figure>
            <figure><img src={endpointMenuImage} width="313" height="295" alt="Меню Endpoint Agent с пунктом Привязать компьютер к Helpdesk" className="h-auto max-w-full rounded-lg border"/><figcaption className="mt-1 text-slate-600">2. Откройте получение кода.</figcaption></figure>
          </div>
        </details>
      </> : <div className="space-y-3 text-sm leading-6 text-slate-700">
        <p>В Linux получение кода через значок агента пока недоступно. Для Linux, в том числе ALT Linux, с привязкой поможет специалист поддержки.</p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>Узнайте имя компьютера в настройках системы, в разделе «О системе». Его также можно посмотреть командой <code className="rounded bg-slate-100 px-1.5 py-0.5">hostname</code> в терминале.</li>
          <li>Создайте обращение о помощи с привязкой. Укажите имя компьютера, Linux или ALT Linux и ваш отдел.</li>
          <li>Дождитесь ответа специалиста. После проверки владельца компьютер появится в разделе «Устройства».</li>
        </ol>
        <Link className="inline-flex min-h-10 items-center font-semibold text-brand-700 underline underline-offset-4" to="/app/requester/new?intent=device_owner_change">Попросить помочь с привязкой</Link>
        <p className="text-slate-500">Обращение можно создать без привязанного компьютера. Если у вас уже есть действующий код, введите его ниже.</p>
      </div>}
    </div>
  </>;
}
