import {Plus, Trash2} from "lucide-react";

import {Badge} from "../../components/ui/badge";
import {Button} from "../../components/ui/button";
import {Card, CardContent, CardHeader, CardTitle} from "../../components/ui/card";
import {Input} from "../../components/ui/input";

import {CALENDAR_DAYS} from './settings-types';
import {formatDateTime, prettyJson, defaultCalendarHours, createHolidayDraft, buildHolidaysJson, buildCalendarDraft} from './settings-form-model';

import {SettingsField, PermissionNotice} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';
export function CalendarsSettingsSection({model}:{model:ServiceSettingsModel}){const {requestChange,setDirty,payload,canManageRouting,routingDeniedReason,setSelectedCalendarId,selectedCalendar,calendarDraft,setCalendarDraft,calendarMutation}=model; if(!payload)return null;
return (
            <div className="settings-object-editor">
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>Календари</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    disabled={!canManageRouting}
                    leadingIcon={<Plus className="h-4 w-4" />}
                    onClick={() => requestChange(() => {
                      setSelectedCalendarId(-1);
                      setDirty(true);
                      setCalendarDraft(buildCalendarDraft(null));
                    })}
                    variant="secondary"
                  >
                    Новый календарь
                  </Button>
                  {payload.calendars.map((calendar) => (
                    <button
                      key={calendar.id}
                      className={`w-full rounded-[1.1rem] px-4 py-4 text-left ${
                        selectedCalendar?.id === calendar.id ? "bg-brand-50 text-brand-800" : "bg-surface-subtle text-slate-700"
                      }`}
                      onClick={() => requestChange(() => setSelectedCalendarId(calendar.id))}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{calendar.name}</p>
                        <Badge tone={calendar.is_active ? "success" : "neutral"}>{calendar.code}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-current/70">Обновлён: {formatDateTime(calendar.updated_at)}</p>
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{selectedCalendar ? selectedCalendar.name : "Новый календарь"}</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-4">
                  <PermissionNotice text={routingDeniedReason} />
                  <div className="grid gap-4 md:grid-cols-2">
                    <SettingsField label="Код">
                      <Input data-settings-draft="calendar"
                        onChange={(event) => setCalendarDraft((current) => ({ ...current, code: event.target.value }))}
                        value={calendarDraft.code}
                      />
                    </SettingsField>
                    <SettingsField label="Название">
                      <Input data-settings-draft="calendar"
                        onChange={(event) => setCalendarDraft((current) => ({ ...current, name: event.target.value }))}
                        value={calendarDraft.name}
                      />
                    </SettingsField>
                  </div>
                  <SettingsField label="Часовой пояс">
                    <Input data-settings-draft="calendar"
                      onChange={(event) => setCalendarDraft((current) => ({ ...current, timezone: event.target.value }))}
                      value={calendarDraft.timezone}
                    />
                  </SettingsField>
                  <label className="flex items-center gap-3 rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                    <input data-settings-draft="calendar"
                      checked={calendarDraft.is_active}
                      onChange={(event) => setCalendarDraft((current) => ({ ...current, is_active: event.target.checked }))}
                      type="checkbox"
                    />
                    <span>Календарь активен</span>
                  </label>
                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">Рабочая неделя</p>
                        <p className="mt-1 text-sm text-slate-500">Один интервал на день; структура календаря собирается автоматически.</p>
                      </div>
                      <Button
                        onClick={() => {model.markDirty("calendar");setCalendarDraft((current) => ({ ...current, weekly_hours: defaultCalendarHours() }));}}
                        size="sm"
                        variant="outline"
                      >
                        Будни 09:00–18:00
                      </Button>
                    </div>
                    <div className="mt-4 grid gap-3">
                      {calendarDraft.weekly_hours.map((row) => {
                        const dayLabel = CALENDAR_DAYS.find((item) => item.day === row.day)?.label ?? String(row.day);
                        return (
                          <div key={row.day} className="grid gap-3 rounded-[0.9rem] bg-white px-3 py-3 md:grid-cols-[7rem_1fr_1fr]">
                            <label className="flex items-center gap-2 text-sm font-medium text-slate-800">
                              <input data-settings-draft="calendar"
                                checked={row.enabled}
                                onChange={(event) =>
                                  setCalendarDraft((current) => ({
                                    ...current,
                                    weekly_hours: current.weekly_hours.map((item) =>
                                      item.day === row.day ? { ...item, enabled: event.target.checked } : item,
                                    ),
                                  }))
                                }
                                type="checkbox"
                              />
                              <span>{dayLabel}</span>
                            </label>
                            <Input data-settings-draft="calendar"
                              disabled={!row.enabled}
                              onChange={(event) =>
                                setCalendarDraft((current) => ({
                                  ...current,
                                  weekly_hours: current.weekly_hours.map((item) =>
                                    item.day === row.day ? { ...item, start: event.target.value } : item,
                                  ),
                                }))
                              }
                              type="time"
                              value={row.start}
                            />
                            <Input data-settings-draft="calendar"
                              disabled={!row.enabled}
                              onChange={(event) =>
                                setCalendarDraft((current) => ({
                                  ...current,
                                  weekly_hours: current.weekly_hours.map((item) =>
                                    item.day === row.day ? { ...item, end: event.target.value } : item,
                                  ),
                                }))
                              }
                              type="time"
                              value={row.end}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-900">Праздники и исключения</p>
                        <p className="mt-1 text-sm text-slate-500">
                          Даты выбираются списком; JSON для API собирается автоматически.
                        </p>
                      </div>
                      <Button
                        disabled={!canManageRouting}
                        leadingIcon={<Plus className="h-4 w-4" />}
                        onClick={() =>
                          {model.markDirty("calendar");setCalendarDraft((current) => ({
                            ...current,
                            holidays: [...current.holidays, createHolidayDraft("", current.holidays.length)],
                          }));}
                        }
                        size="sm"
                        variant="outline"
                      >
                        Добавить дату
                      </Button>
                    </div>

                    <div className="mt-4 grid gap-3">
                      {calendarDraft.holidays.length ? (
                        calendarDraft.holidays.map((holiday, index) => (
                          <div key={holiday.id} className="grid gap-3 rounded-[0.9rem] bg-white px-3 py-3 md:grid-cols-[minmax(0,1fr)_auto]">
                            <Input data-settings-draft="calendar"
                              aria-label="Дата праздника или исключения"
                              disabled={!canManageRouting}
                              onChange={(event) =>
                                setCalendarDraft((current) => ({
                                  ...current,
                                  holidays: current.holidays.map((item) =>
                                    item.id === holiday.id ? { ...item, date: event.target.value } : item,
                                  ),
                                }))
                              }
                              type="date"
                              value={holiday.date}
                            />
                            <Button
                              aria-label={`Удалить дату ${holiday.date || index + 1}`}
                              disabled={!canManageRouting}
                              leadingIcon={<Trash2 className="h-4 w-4" />}
                              onClick={() =>
                                {model.markDirty("calendar");setCalendarDraft((current) => ({
                                  ...current,
                                  holidays: current.holidays.filter((item) => item.id !== holiday.id),
                                }));}
                              }
                              size="sm"
                              variant="outline"
                            >
                              Удалить
                            </Button>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-[0.9rem] border border-dashed border-border bg-white px-4 py-5 text-sm text-slate-500">
                          Исключений нет. Добавьте дату, если сроки ответа не должны считать этот день рабочим.
                        </div>
                      )}
                    </div>

                    <details className="rounded-lg border border-border p-3"><summary className="cursor-pointer font-medium">Дополнительно: структура календаря</summary><div className="mt-4 rounded-[0.9rem] bg-white px-3 py-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Собирается для API</p>
                      <pre className="mt-2 overflow-x-auto text-xs text-slate-600">{prettyJson(buildHolidaysJson(calendarDraft.holidays))}</pre>
                    </div></details>
                  </div>
                  <Button disabled={!canManageRouting || calendarMutation.isPending} onClick={() => calendarMutation.mutate()} className="w-full">
                    Сохранить календарь
                  </Button>
                </CardContent>
              </Card>
            </div>
          );
}
