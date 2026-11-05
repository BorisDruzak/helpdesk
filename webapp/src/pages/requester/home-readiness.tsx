import { ArrowRight, CheckCircle2, CircleAlert, Monitor } from "lucide-react";
import { Link } from "react-router-dom";

import { requesterDeviceLabel, requesterDeviceConnectionStatusLabel } from "../../features/requester/labels";
import type { RequesterBootstrap } from "../../features/requester/types";

export function RequesterHomeReadiness({ bootstrap, profileComplete }: { bootstrap: RequesterBootstrap | null; profileComplete: boolean }) {
  const resolution = String(bootstrap?.primary_device_resolution?.status ?? "").toLowerCase();
  const device = bootstrap?.primary_device && (!resolution || resolution === "available" || resolution === "resolved") ? bootstrap.primary_device : null;
  const pending = Boolean(bootstrap?.pending_registration_claims?.length);
  const ambiguous = resolution === "ambiguous";
  const deviceLabel = device ? requesterDeviceLabel(device, "Мой компьютер")
    : pending ? "Привязка на проверке" : ambiguous ? "Основной компьютер не выбран" : "Устройство не привязано";
  const deviceHref = device || pending || ambiguous ? "/app/requester/devices" : "/app/requester/devices/link";

  return (
    <section aria-label="Профиль и компьютер" className="requester-home__readiness">
      <div className="requester-home__readiness-item">
        {profileComplete ? <CheckCircle2 aria-hidden="true" className="text-brand-700" /> : <CircleAlert aria-hidden="true" className="text-amber-700" />}
        <div>
          <p className="font-semibold text-slate-900">{profileComplete ? "Профиль заполнен" : "Профиль нужно заполнить"}</p>
          {!profileComplete ? <p className="mt-1 text-sm text-slate-600">Укажите данные для связи со специалистом.</p> : null}
        </div>
        <Link className="requester-home__text-link" to={profileComplete ? "/app/requester/profile" : bootstrap?.profile_completion?.setup_path || "/app/requester/profile/setup"}>
          {profileComplete ? "Мой профиль" : "Заполнить профиль"}<ArrowRight aria-hidden="true" />
        </Link>
      </div>
      <div className="requester-home__readiness-item">
        <Monitor aria-hidden="true" className={device ? "text-brand-700" : "text-slate-500"} />
        <div className="min-w-0">
          <p className="break-words font-semibold text-slate-900">{deviceLabel}</p>
          <p className="mt-1 text-sm text-slate-600">{device ? requesterDeviceConnectionStatusLabel(device)
            : pending ? "Администратор проверит владельца компьютера."
              : ambiguous ? "Проверьте привязанные устройства."
                : "Обращения без компьютера доступны в подходящих разделах."}</p>
        </div>
        <Link className="requester-home__text-link" to={deviceHref}>
          {device || pending || ambiguous ? "Мои устройства" : "Привязать компьютер"}<ArrowRight aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}
