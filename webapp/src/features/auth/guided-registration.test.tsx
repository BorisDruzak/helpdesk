import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RegisterPage } from "./register-page";
import { SessionProvider } from "./session-provider";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {status, headers: {"Content-Type":"application/json"}});
}
function Home() { const location = useLocation(); return <p data-testid="destination">{location.pathname}</p>; }
function install(options: { failOnce?: boolean; changedSchema?: boolean; invitation?: boolean; rejectInvite?: boolean } = {}) {
  let submissions = 0;
  let optionReads = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/capabilities")) return json({status:"success",data:{self_registration_enabled:true}});
    if (url.endsWith("/me")) return json({status:"error"},401);
    if (url.endsWith("/registration-options")) {
      optionReads++;
      const fields = options.changedSchema && optionReads>1 ? [
        {key:"full_name",label:"ФИО",type:"text",required:true},
        {key:"department_id",label:"Отдел",type:"select",required:true},
        {key:"phone",label:"Телефон или внутренний номер",type:"phone",required:true},
      ] : [];
      return json({status:"success",data:{departments:[{value:"real",label:"Юридический отдел"}],profile_schema:{fields,required_fields:[]},inventory_invitation_enabled:options.invitation}});
    }
    if (url.endsWith("/registration-invitation") && options.invitation)
      return json({status:"success",data:{full_name:"Петров Иван Сергеевич",department:"Юридический отдел",department_id:"real"}});
    if (url.endsWith("/register-requester")) {
      submissions++;
      if (options.rejectInvite && JSON.parse(String(init?.body)).inventory_invite_code)
        return json({status:"error",error:"Приглашение недействительно",error_code:"REGISTRATION_CONFLICT"},409);
      if (options.failOnce && submissions === 1) throw new TypeError("Network failed");
      return json({status:"success",data:{user_login:"ipetrov2",actor_role:"user",profile_complete:true}},201);
    }
    if (url.endsWith("/login")) return json({status:"success",data:{user_login:"ipetrov2",actor_role:"user",auth_type:"ui_token",default_workspace:"requester",available_workspaces:["requester"]}});
    throw new Error("Unexpected route " + url);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
function show() {
  return render(<SessionProvider><MemoryRouter initialEntries={["/app/register?next=%2Fapp%2Frequester%2Fnew"]}>
    <Routes><Route path="/app/register" element={<RegisterPage/>}/><Route path="/app/requester" element={<Home/>}/></Routes>
  </MemoryRouter></SessionProvider>);
}
async function names() {
  fireEvent.change(await screen.findByLabelText("Фамилия"), {target:{value:"Петров"}});
  fireEvent.change(screen.getByLabelText("Имя", {exact:true}), {target:{value:"Иван"}});
  fireEvent.change(screen.getByLabelText("Отчество"), {target:{value:"Сергеевич"}});
  fireEvent.click(screen.getByRole("button", {name:"Продолжить"}));
}
async function contacts(position?:string) {
  fireEvent.focus(await screen.findByRole("combobox",{name:"Отдел"}));
  fireEvent.click(screen.getByRole("option",{name:"Юридический отдел"}));
  fireEvent.change(screen.getByLabelText("Телефон или внутренний номер"), {target:{value:"1234"}});
  if(position) fireEvent.change(screen.getByLabelText("Должность"),{target:{value:position}});
  fireEvent.click(screen.getByRole("button", {name:"Продолжить"}));
}
async function password() {
  fireEvent.change(await screen.findByLabelText("Пароль", {exact:true}), {target:{value:"Long-registration-password-43!"}});
  fireEvent.change(screen.getByLabelText("Повторите пароль"), {target:{value:"Long-registration-password-43!"}});
  fireEvent.click(screen.getByRole("button", {name:"Зарегистрироваться"}));
}
afterEach(() => {vi.unstubAllGlobals(); sessionStorage.clear();});

describe("guided employee registration", () => {
  it("uses one department input for search and explicit keyboard selection", async () => {
    install(); show(); await names();
    const department = screen.getByRole("combobox", { name: "Отдел" });
    expect(department.tagName).toBe("INPUT");
    expect(screen.queryByLabelText("Найти отдел")).not.toBeInTheDocument();
    fireEvent.focus(department);
    fireEvent.change(department, {target:{value:"юрид"}});
    fireEvent.keyDown(department, {key:"ArrowDown"});
    fireEvent.keyDown(department, {key:"Enter"});
    expect(department).toHaveValue("Юридический отдел");
    expect(screen.getByLabelText("Телефон или внутренний номер")).toBeInTheDocument();
    fireEvent.focus(department);
    fireEvent.change(department, {target:{value:"такого отдела нет"}});
    fireEvent.blur(department);
    fireEvent.change(screen.getByLabelText("Телефон или внутренний номер"),{target:{value:"1234"}});
    fireEvent.click(screen.getByRole("button",{name:"Продолжить"}));
    expect(screen.getByRole("alert")).toHaveTextContent("Заполните обязательные поля профиля");
  });
  it("shows and hides both password values without submitting or losing them", async () => {
    const requests=install(); show(); await names(); await contacts();
    const first=screen.getByLabelText("Пароль",{exact:true});
    const second=screen.getByLabelText("Повторите пароль");
    fireEvent.change(first,{target:{value:"Synthetic-long-password-43!"}});
    fireEvent.change(second,{target:{value:"Synthetic-long-password-43!"}});
    fireEvent.click(screen.getByRole("button",{name:"Показать пароль"}));
    expect(first).toHaveAttribute("type","text");
    expect(second).toHaveAttribute("type","password");
    fireEvent.click(screen.getByRole("button",{name:"Показать повтор пароля"}));
    expect(second).toHaveAttribute("type","text");
    fireEvent.click(screen.getByRole("button",{name:"Скрыть пароль"}));
    expect(first).toHaveAttribute("type","password");
    expect(first).toHaveValue("Synthetic-long-password-43!");
    expect(requests.mock.calls.some(([url])=>String(url).endsWith('/register-requester'))).toBe(false);
  });
  it("retains name/profile values going backwards and previews the generated login", async () => {
    install(); show(); await names();
    expect(screen.getByText("ipetrov")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name:"Назад"}));
    expect(screen.getByLabelText("Фамилия")).toHaveValue("Петров");
    expect(screen.getByLabelText("Имя", {exact:true})).toHaveValue("Иван");
    expect(screen.queryByLabelText("Локация")).not.toBeInTheDocument();
  });
  it("finishes the complete profile, uses actual login, opens home and never creates a ticket", async () => {
    const requests = install(); show(); await names(); await contacts(); await password();
    expect(await screen.findByTestId("destination")).toHaveTextContent("/app/requester");
    const calls = requests.mock.calls;
    const signup = calls.find(([input]) => String(input).endsWith("/register-requester"));
    expect(JSON.parse(String(signup?.[1]?.body))).toMatchObject({first_name:"Иван",last_name:"Петров",department_id:"real",phone:"1234"});
    const login = calls.find(([input]) => String(input).endsWith("/login"));
    expect(JSON.parse(String(login?.[1]?.body)).login).toBe("ipetrov2");
    expect(calls.some(([input]) => String(input).includes("/tickets"))).toBe(false);
    expect(JSON.stringify({...sessionStorage})).not.toContain("Long-registration-password");
  });
  it("reuses the same attempt after an uncertain response", async () => {
    const requests = install({failOnce:true}); show(); await names(); await contacts(); await password();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", {name:"Повторить завершение"}));
    await screen.findByTestId("destination");
    const calls = requests.mock.calls.filter(([input]) => String(input).endsWith("/register-requester"));
    expect(calls).toHaveLength(2);
    expect(JSON.parse(String(calls[0][1]?.body)).request_id).toBe(JSON.parse(String(calls[1][1]?.body)).request_id);
  });
  it("resumes an uncertain attempt after remount without persisting passwords", async () => {
    const requests = install({failOnce:true,changedSchema:true});
    const first = show(); await names(); await contacts("Инженер"); await password();
    await screen.findByRole("alert"); first.unmount();
    expect(JSON.stringify({...sessionStorage})).not.toContain("Long-registration-password");
    show();
    expect(await screen.findByLabelText("Пароль", {exact:true})).toHaveValue("");
    expect(screen.getByText("Петров Иван Сергеевич")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Пароль", {exact:true}), {target:{value:"Long-registration-password-43!"}});
    fireEvent.change(screen.getByLabelText("Повторите пароль"), {target:{value:"Long-registration-password-43!"}});
    fireEvent.click(screen.getByRole("button", {name:"Повторить завершение"}));
    await screen.findByTestId("destination");
    const calls = requests.mock.calls.filter(([input]) => String(input).endsWith("/register-requester"));
    expect(calls).toHaveLength(2);
    expect(JSON.parse(String(calls[1][1]?.body)).position).toBe("Инженер");
    expect(JSON.parse(String(calls[0][1]?.body))).toEqual(JSON.parse(String(calls[1][1]?.body)));
  });
});



it("uses the selected invitation and asks for the code again after an uncertain reload", async () => {
  const code = "fixture-invitation-code-".padEnd(43, "x");
  const requests = install({ failOnce: true, invitation: true });
  const initial = show();
  fireEvent.click(await screen.findByText("У меня есть приглашение"));
  fireEvent.change(screen.getByLabelText("Код приглашения"), {target:{value:code}});
  fireEvent.click(screen.getByRole("button", {name:"Проверить код"}));
  fireEvent.click(await screen.findByRole("button", {name:"Это моя запись"}));
  expect(screen.getByLabelText("Фамилия")).toHaveValue("Петров");
  fireEvent.click(screen.getByRole("button", {name:"Продолжить"}));
  expect(screen.queryByRole("combobox", {name:"Отдел"})).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Телефон или внутренний номер"), {target:{value:"1234"}});
  fireEvent.click(screen.getByRole("button", {name:"Продолжить"}));
  await password();
  await screen.findByRole("alert");
  expect(JSON.stringify({...sessionStorage})).not.toContain(code);
  initial.unmount();
  show();
  expect(await screen.findByLabelText("Код приглашения")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Пароль", {exact:true}), {target:{value:"Long-registration-password-43!"}});
  fireEvent.change(screen.getByLabelText("Повторите пароль"), {target:{value:"Long-registration-password-43!"}});
  fireEvent.click(screen.getByRole("button", {name:"Повторить завершение"}));
  expect(screen.getByRole("alert")).toHaveTextContent("Введите код приглашения");
  fireEvent.change(screen.getByLabelText("Код приглашения"), {target:{value:code}});
  fireEvent.click(screen.getByRole("button", {name:"Повторить завершение"}));
  await screen.findByTestId("destination");
  const attempts = requests.mock.calls.filter(([url])=>String(url).endsWith("/register-requester"));
  expect(attempts).toHaveLength(2);
  expect(JSON.parse(String(attempts[1][1]?.body))).toEqual(JSON.parse(String(attempts[0][1]?.body)));
  expect(JSON.parse(String(attempts[1][1]?.body))).toMatchObject({inventory_invite_code:code, department_id:"real"});
});



it("can explicitly start normal registration after a rejected invitation", async () => {
  const requests = install({ invitation: true, rejectInvite: true });
  show();
  fireEvent.click(await screen.findByText("У меня есть приглашение"));
  fireEvent.change(screen.getByLabelText("Код приглашения"), {target:{value:"a".repeat(43)}});
  fireEvent.click(screen.getByRole("button", {name:"Проверить код"}));
  fireEvent.click(await screen.findByRole("button", {name:"Это моя запись"}));
  fireEvent.click(screen.getByRole("button", {name:"Продолжить"}));
  fireEvent.change(screen.getByLabelText("Телефон или внутренний номер"), {target:{value:"1234"}});
  fireEvent.click(screen.getByRole("button", {name:"Продолжить"}));
  await password();
  fireEvent.click(await screen.findByRole("button", {name:"Продолжить без приглашения"}));
  await names();
  await contacts();
  await password();
  await screen.findByTestId("destination");
  const attempts = requests.mock.calls.filter(([url])=>String(url).endsWith("/register-requester"));
  expect(attempts).toHaveLength(2);
  const [invited, standard] = attempts.map(([,init]) => JSON.parse(String(init?.body)));
  expect(standard.request_id).not.toBe(invited.request_id);
  expect(standard).not.toHaveProperty("inventory_invite_code");
});
