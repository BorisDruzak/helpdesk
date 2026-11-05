import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { SearchableSelect } from "../../components/ui/searchable-select";
import { PasswordInput } from "../../components/ui/password-input";
import { buildProfilePayload, buildProfileValues, missingProfileFields, RequesterProfileFieldControl, type RequesterProfileValues } from "../requester/profile-runtime";
import { fieldsWithRuntimeOptions } from "../../pages/requester/profile-workflow";
import { WebSessionApiError } from "./api";
import { useSession } from "./session-provider";
import { clearRegistrationAttempt, clearPendingRegistrationSubmission, confirmRegistration, fetchRegistrationOptions, registerRequester, registrationAttempt, rememberRegistrationSubmission,
  registrationLoginPreview, RegistrationFieldError, type RegistrationAttempt, type RegistrationNames, type RegistrationOptions } from "./requester-registration";

export function RegistrationWizard({switchAccount}: {switchAccount:boolean}) {
  const navigate = useNavigate();
  const {login,logout,status} = useSession();
  const [attempt,setAttempt] = useState<RegistrationAttempt | null>(() => {try {return registrationAttempt();} catch {return null;}});
  const [names,setNames] = useState<RegistrationNames>(attempt?.submission?.names ?? {first_name:"",last_name:"",patronymic:""});
  const [values,setValues] = useState<RequesterProfileValues>(() => ({...buildProfileValues(),...attempt?.submission?.profile,custom_fields:attempt?.submission?.profile.custom_fields ?? {}}));
  const [options,setOptions] = useState<RegistrationOptions | null>(null);
  const [loadError,setLoadError] = useState(false);
  const [reload,setReload] = useState(0);
  const [step,setStep] = useState(attempt?.submission ? 2 : 0);
  const [password,setPassword] = useState("");
  const [repeat,setRepeat] = useState("");
  const [error,setError] = useState<string | null>(null);
  const [errors,setErrors] = useState<Record<string,string>>({});
  const [pending,setPending] = useState(false);
  const [uncertain,setUncertain] = useState(Boolean(attempt?.submission && !attempt?.user_login));
  const busy = useRef(false);
  const formRef = useRef<HTMLFormElement>(null);
  const preview = registrationLoginPreview(names.first_name,names.last_name);
  const fullName = [names.last_name,names.first_name,names.patronymic].map(v => v.trim()).filter(Boolean).join(" ");
  const profileValues = {...values,full_name:fullName};
  const departments = options?.departments ?? [];
  const fields = fieldsWithRuntimeOptions(options?.profile_schema,departments,[])
    .filter(field => !["full_name","login_identity","active_device_links"].includes(field.key));

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(false);
    void fetchRegistrationOptions(controller.signal).then(value => {if(!controller.signal.aborted) setOptions(value);})
      .catch(() => {if(!controller.signal.aborted) setLoadError(true);});
    return () => controller.abort();
  },[reload]);

  function showErrors(message: string, details: Record<string,string> = {}) {
    setError(message); setErrors(details);
    window.requestAnimationFrame(() => formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus());
  }
  function advance() {
    setError(null);setErrors({});
    if(step === 0) {
      const details: Record<string,string> = {};
      if(!names.last_name.trim()) details.last_name = "Укажите фамилию.";
      if(!names.first_name.trim()) details.first_name = "Укажите имя.";
      if(!preview && !Object.keys(details).length) details.last_name = "Используйте буквы, пробел или дефис.";
      if(names.patronymic && !/^[a-zа-яё]+(?:[ -][a-zа-яё]+)*$/i.test(names.patronymic.trim())) details.patronymic = "Проверьте отчество.";
      if(Object.keys(details).length) return showErrors("Проверьте ФИО.",details);
    } else {
      const missing = missingProfileFields(options?.profile_schema,profileValues);
      if(missing.length) return showErrors("Заполните обязательные поля профиля.",Object.fromEntries(missing.map(field => [field.key,`Заполните поле: ${field.key === "department_id" ? "Отдел" : field.label}.`])));
    }
    setStep(step+1);
  }
  async function finish() {
    if(busy.current || !attempt) return;
    if(password.length < 12) return showErrors("Пароль должен содержать не менее 12 символов.",{password:"Не менее 12 символов."});
    if(!attempt.user_login && password !== repeat) return showErrors("Пароли не совпадают.",{password_repeat:"Повторите тот же пароль."});
    busy.current = true; setPending(true);setError(null);setErrors({});
    try {
      if(switchAccount && status === "authenticated") await logout();
      let actual = attempt.user_login;
      if(!actual) {
        const submission = uncertain && attempt.submission ? attempt.submission : {names,profile:buildProfilePayload(profileValues,null,fields)};
        rememberRegistrationSubmission(attempt,submission.names,submission.profile);
        setAttempt({...attempt,submission});
        const result = await registerRequester({...submission.names,request_id:attempt.request_id,profile:submission.profile,password,password_repeat:repeat});
        actual = result.user_login;
        confirmRegistration(attempt,actual);
        setAttempt({...attempt,user_login:actual});
      }
      await login({login:actual,password});
      clearRegistrationAttempt();
      navigate("/app/requester",{replace:true,state:{registrationCompleted:true}});
    } catch(cause) {
      const retry = !(cause instanceof WebSessionApiError) || cause.status >= 500;
      setUncertain(retry);
      if(!retry && cause instanceof RegistrationFieldError && cause.status === 400) {
        clearPendingRegistrationSubmission(attempt);
        setAttempt({request_id:attempt.request_id});
      }
      showErrors(cause instanceof WebSessionApiError ? cause.message : "Ответ о регистрации не получен. Повторите завершение с теми же данными.",cause instanceof RegistrationFieldError ? cause.details : {});
      if(cause instanceof RegistrationFieldError && cause.status === 400 && cause.errorCode === "PROFILE_VALIDATION_ERROR") setStep(1);
    } finally {busy.current=false;setPending(false);}
  }
  function submit(event: FormEvent) {event.preventDefault(); if(step < 2 && !attempt?.user_login) advance(); else void finish();}
  function control(field: typeof fields[number]) {
    if(field.key==='department_id') return <SearchableSelect key={field.key} label="Отдел" required={field.required} value={values.department_id}
      options={departments} error={errors.department_id} onChange={value=>setValues(current=>({...current,department_id:value}))}/>;
    return <RequesterProfileFieldControl key={field.key} field={field} error={errors[field.key] ?? errors[`custom_fields.${field.key}`]}
      value={field.custom ? values.custom_fields[field.key] : values[field.key as keyof Omit<RequesterProfileValues,"custom_fields">]}
      onChange={value => setValues(current => field.custom ? {...current,custom_fields:{...current.custom_fields,[field.key]:value}} : {...current,[field.key]:value})}/>;
  }
  if(!attempt) return <p role="alert">Разрешите хранение состояния регистрации в этой вкладке и обновите страницу. Пароль не сохраняется.</p>;
  if(loadError) return <div role="alert"><p>Не удалось загрузить список отделов.</p><Button onClick={() => setReload(reload+1)}>Повторить</Button></div>;
  if(!options) return <p role="status">Загружаем данные регистрации…</p>;
  return <form noValidate onSubmit={submit} ref={formRef} className="space-y-5">
    {!attempt.user_login ? <ol aria-label="Шаги регистрации" className="flex flex-wrap gap-3 text-sm">
      {["ФИО","Отдел и связь","Пароль"].map((label,index) => <li key={label} aria-current={step===index ? "step" : undefined} className={step===index ? "font-semibold text-brand-700" : "text-slate-500"}>{index+1}. {label}</li>)}
    </ol> : <div role="status">Аккаунт создан, профиль заполнен. Ваш логин: <strong>{attempt.user_login}</strong>. Введите пароль, чтобы войти в кабинет.</div>}
    {error ? <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}
    {uncertain && !attempt.user_login ? <p role="status" className="text-sm text-slate-600">Повторите завершение с теми же данными и паролем. Новый аккаунт при повторе не создаётся.</p> : null}
    <fieldset disabled={pending} className="min-w-0 space-y-4">
      {!attempt.user_login && step===0 ? <div className="space-y-4">{([['last_name','Фамилия'],['first_name','Имя'],['patronymic','Отчество']] as const).map(([key,label]) =>
        <label key={key} className="block space-y-1 text-sm font-medium">{label}<Input className="w-full" aria-label={label} aria-invalid={errors[key] ? true : undefined} autoComplete={key==='last_name' ? 'family-name' : key==='first_name' ? 'given-name' : 'additional-name'} maxLength={100} value={names[key]} onChange={event => setNames({...names,[key]:event.target.value})}/>{errors[key] ? <span className="block text-rose-700">{errors[key]}</span> : null}</label>)}</div> : null}
      {!attempt.user_login && step===1 ? <div className="space-y-4">
        {fields.filter(field => field.required || field.key==='department_id' || field.key==='phone').map(control)}
        {fields.some(field => !field.required && !['department_id','phone'].includes(field.key)) ? <details><summary className="cursor-pointer text-sm font-semibold">Дополнительные сведения (необязательно)</summary><div className="mt-4 space-y-4">{fields.filter(field => !field.required && !['department_id','phone'].includes(field.key)).map(control)}</div></details> : null}
      </div> : null}
      {step===2 || attempt.user_login ? <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {!attempt.user_login ? <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 rounded-xl bg-slate-50 p-3 text-sm md:col-span-2"><dt>Сотрудник</dt><dd className="font-semibold break-words">{fullName}</dd><dt>Отдел</dt><dd>{options.departments.find(item => item.value===values.department_id)?.label}</dd><dt>Связь</dt><dd>{values.phone || values.internal_extension}</dd></dl> : null}
        <PasswordInput label="Пароль" aria-invalid={errors.password ? true : undefined} autoComplete={attempt.user_login ? "current-password" : "new-password"} maxLength={1024} value={password} onChange={event=>setPassword(event.target.value)} hint="Не менее 12 символов."/>
        {!attempt.user_login ? <PasswordInput label="Повторите пароль" toggleLabel="повтор пароля" aria-invalid={errors.password_repeat ? true : undefined} autoComplete="new-password" maxLength={1024} value={repeat} onChange={event=>setRepeat(event.target.value)}/> : null}
      </div> : null}
    </fieldset>
    {preview && !attempt.user_login ? <p className="rounded-xl bg-brand-50 p-3 text-sm">Ваш логин: <strong className="break-all">{preview}</strong><span className="mt-1 block text-xs text-slate-600">Если логин занят, добавится номер. Итоговый логин появится в кабинете.</span></p> : null}
    <div className="flex flex-wrap justify-between gap-3 border-t pt-4">
      {step>0 && !attempt.user_login ? <Button type="button" variant="outline" disabled={pending || uncertain} onClick={() => {setStep(step-1);setError(null);setErrors({});}}>Назад</Button> : <span/>}
      <Button type="submit" disabled={pending} className="ml-auto">{pending ? "Завершаем…" : attempt.user_login ? "Войти в кабинет" : uncertain ? "Повторить завершение" : step===2 ? "Зарегистрироваться" : "Продолжить"}</Button>
    </div>
  </form>;
}
