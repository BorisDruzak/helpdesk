import type { RequesterProfileSchema, RequesterProfileUpdatePayload } from "../requester/types";
import { WebSessionApiError } from "./api";

const ATTEMPT_KEY = "helpdesk.requester-registration.v1";
export const REGISTRATION_LOGIN_KEY = "helpdesk.registration-completed-login";
export type RegistrationAttempt = { request_id: string; user_login?: string; submission?: {names:RegistrationNames;profile:RequesterProfileUpdatePayload} };
export type RegistrationOptions = { departments: Array<{value:string;label:string}>; profile_schema: RequesterProfileSchema };
export type RegistrationNames = { first_name: string; last_name: string; patronymic: string };

export function registrationAttempt(): RegistrationAttempt {
  const raw = sessionStorage.getItem(ATTEMPT_KEY);
  if (raw) {
    try {
      const saved = JSON.parse(raw) as RegistrationAttempt;
      const submission = saved.submission;
      const validSubmission = !submission || (typeof submission.names?.first_name === "string" && typeof submission.names?.last_name === "string"
        && typeof submission.names?.patronymic === "string" && typeof submission.profile?.department_id === "string" && typeof submission.profile?.phone === "string");
      if (/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(saved.request_id) && validSubmission
          && (!saved.user_login || /^[a-z][a-z0-9-]{1,99}$/.test(saved.user_login))) return saved;
    } catch { /* A malformed draft is not a registration receipt. */ }
  }
  const attempt = { request_id: crypto.randomUUID() };
  sessionStorage.setItem(ATTEMPT_KEY, JSON.stringify(attempt));
  return attempt;
}

export function confirmRegistration(attempt: RegistrationAttempt, login: string) {
  try {
    sessionStorage.setItem(ATTEMPT_KEY, JSON.stringify({request_id:attempt.request_id, user_login: login}));
    sessionStorage.setItem(REGISTRATION_LOGIN_KEY, login);
  } catch { /* The original request ID still supports a safe server replay. Continue the confirmed login. */ }
}
export function clearRegistrationAttempt() { sessionStorage.removeItem(ATTEMPT_KEY); }

export function rememberRegistrationSubmission(attempt:RegistrationAttempt, names:RegistrationNames, profile:RequesterProfileUpdatePayload) {
  // The password is deliberately absent from this bounded, session-only draft.
  sessionStorage.setItem(ATTEMPT_KEY,JSON.stringify({request_id:attempt.request_id,submission:{names,profile}}));
}

export function clearPendingRegistrationSubmission(attempt:RegistrationAttempt) {
  try {sessionStorage.setItem(ATTEMPT_KEY,JSON.stringify({request_id:attempt.request_id}));} catch { /* Keep the existing retry ID. */ }
}

const russian = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя";
const latin = ["a","b","v","g","d","e","yo","zh","z","i","y","k","l","m","n","o","p","r","s","t","u","f","kh","ts","ch","sh","shch","","y","","e","yu","ya"];
export function registrationLoginPreview(first: string, last: string): string {
  const clean = (text: string) => text.normalize("NFC").trim().replace(/\s+/g," ");
  first = clean(first); last = clean(last);
  if (!/^[a-zа-яё]+(?:[ -][a-zа-яё]+)*$/i.test(first) || !/^[a-zа-яё]+(?:[ -][a-zа-яё]+)*$/i.test(last)) return "";
  return Array.from((first[0] + last.replaceAll(" ", "")).toLowerCase())
    .map(letter => russian.includes(letter) ? latin[russian.indexOf(letter)] : letter).join("").slice(0,96);
}

export async function fetchRegistrationOptions(signal?: AbortSignal): Promise<RegistrationOptions> {
  const response = await fetch("/api/web/session/registration-options", {credentials:"same-origin",cache:"no-store",signal});
  const payload = await response.json();
  if (!response.ok || payload.status !== "success" || !Array.isArray(payload.data?.departments))
    throw new WebSessionApiError("Не удалось загрузить список отделов. Повторите попытку.",response.status);
  return payload.data;
}
export class RegistrationFieldError extends WebSessionApiError {
  constructor(message: string, status: number, code?: string, public details?: Record<string,string>) { super(message,status,code); }
}
export async function registerRequester(input: RegistrationNames & {
  request_id: string; profile: RequesterProfileUpdatePayload; password: string; password_repeat: string;
}): Promise<{user_login:string; actor_role:string; profile_complete:boolean}> {
  const {full_name: _name, person_id: _person, location_id: _location, ...profile} = input.profile;
  const response = await fetch("/api/web/session/register-requester", {
    method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({...profile,first_name:input.first_name,last_name:input.last_name,patronymic:input.patronymic,
      request_id:input.request_id,password:input.password,password_repeat:input.password_repeat}),
  });
  const payload = await response.json();
  if (!response.ok || payload.status !== "success") throw new RegistrationFieldError(payload.error ?? "Не удалось завершить регистрацию.",response.status,payload.error_code,payload.details);
  if (payload.data?.actor_role !== "user" || payload.data?.profile_complete !== true || typeof payload.data?.user_login !== "string")
    throw new WebSessionApiError("Ответ о регистрации не подтверждён. Повторите завершение с теми же данными.",503);
  return payload.data;
}
