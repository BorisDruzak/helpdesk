import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { expect, test } from "playwright/test";

// Exercise the browser against the actual server's effective projection and
// empty-answer transition, rather than reproducing its required-field policy.
const projected = JSON.parse(execFileSync("python", ["-X", "utf8", "-c", `
import json,sys,runpy
sys.path[:0]=[${JSON.stringify(resolve(process.cwd(), "..", "server"))},${JSON.stringify(resolve(process.cwd(), ".."))}]
helpers=runpy.run_path(${JSON.stringify(resolve(process.cwd(), "..", "server", "tests", "test_request_scenario_optional_evidence.py"))})
legacy_definition,answer=helpers['legacy_definition'],helpers['answer']
from tickets.request_scenario_runtime import ScenarioRuntime
from tickets.request_scenario_session import project_step
from tickets.request_scenario_optional_evidence import without_evidence_stage
from web_api.dto.request_scenario import ScenarioDefinition
d=legacy_definition()
r=ScenarioRuntime(d);s=r.initial_state();s=r.advance(s,answer(s,{'details':'Не открывается окно'}))
legacy=project_step(r.definition,s);s=r.advance(s,answer(s));submitted=project_step(r.definition,s)
n=ScenarioRuntime(ScenarioDefinition.model_validate(without_evidence_stage(d.model_dump(mode='json'))))
t=n.initial_state();initial=project_step(n.definition,t);t=n.advance(t,answer(t,{'details':'Не открывается окно'}))
print(json.dumps({'legacy':legacy,'submitted':submitted,'initial':initial,'newSubmitted':project_step(n.definition,t)},ensure_ascii=False))
`], { encoding: "utf8" }));

for (const [index, viewport] of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }, { width: 390, height: 844 }].entries()) {
  for (const legacy of [true, false]) {
    test(`${legacy ? "saved screenshot step optional" : "new request skips screenshot step"} ${viewport.width}`, async ({ page }, info) => {
      await page.setViewportSize(viewport);
      const errors: string[] = [], unexpected: string[] = [], answers: unknown[] = [];
      let writes = 0;
      const attach = (step: any) => ({ ...step, id: "evidence-session", state: "active", block: { ...step.block,
        title: step.block.id === "submit" ? "Проверьте обращение" : step.block.title,
        fields: step.block.fields?.map((field: any, offset: number) => ({ ...field,
          answer_attachments: legacy && offset < index ? [{ asset_id: `asset-${offset}`, name: `saved-${offset}.png`, mime_type: "image/png", size_bytes: 42, url: `/saved-${offset}.png` }] : [],
        })),
      } });
      let saved = attach(legacy ? projected.legacy : projected.initial);
      page.on("pageerror", e => errors.push(e.message));
      page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
      await page.route("**/saved-*.png", route => route.fulfill({ contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jFj8AAAAASUVORK5CYII=", "base64") }));
      await page.route("**/api/**", async route => {
        const req = route.request(), path = new URL(req.url()).pathname; let data: unknown;
        if (path === "/api/web/session/me") data = { user_login: "optional-employee", actor_role: "user", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
        else if (path === "/api/web/session/capabilities") data = {};
        else if (path === "/api/web/notifications/unread_count") return route.fulfill({ json: { status: "ok", unread_count: 0 } });
        else if (path === "/api/web/notifications/push/config") data = { enabled: false, public_key: null };
        else if (path === "/api/web/requester/bootstrap") data = { workspace: "requester", profile: { person_id: "optional-employee", display_name: "Тестовый сотрудник", full_name: "Тестовый сотрудник", department_id: "it", phone: "0000" }, profile_completion: { complete: true, blocks: {} }, devices: [], feature_flags: { requester_ticket_create: true, requester_no_device_create: true } };
        else if (path === "/api/web/requester/tickets") { if (req.method() === "POST") writes++; data = { tickets: [] }; }
        else if (path === "/api/service-catalog/current") return route.fulfill({ json: { status: "ok", services: [{ service_code: "other", title: "Другое", offerings: [{ full_code: "other.legacy", offering_code: "legacy", title: "Другая проблема или вопрос", request_template_key: "general", guided_scenario_enabled: true, catalog_items: [{ key: "not_found", entry_point_key: "not_found", title: "Не нашёл свою проблему" }] }] }] } });
        else if (path.endsWith("/step-preview")) data = saved;
        else if (path.endsWith("/answer")) {
          answers.push(req.postDataJSON().answers);
          saved = attach(legacy ? projected.submitted : projected.newSubmitted); data = saved;
        } else if (path.endsWith("/ticket-preview")) data = { ok: true, blockers: [], warnings: [] };
        else if (path.endsWith("/submit")) { writes++; return route.fulfill({ status: 409, json: { status: "error", error_code: "TEST_SUBMIT_FORBIDDEN" } }); }
        else if (path === "/api/web/requester/request-scenarios/sessions" && req.method() === "POST" || path === "/api/web/requester/request-scenarios/sessions/evidence-session" && req.method() === "GET") data = saved;
        else { unexpected.push(path); return route.fulfill({ status: 404, json: { status: "error" } }); }
        return route.fulfill({ json: { status: "success", data } });
      });
      await page.route("**/public_api/ticket_forms/current**", route => route.fulfill({ json: { status: "ok", pack: { key: "request_forms", version: "optional", forms: [{ key: "general", title: "Помощь", availability_policy: { available_without_agent_binding: true }, fields: [] }] } } }));
      async function open() {
        await page.goto("/app/requester/new");
        await page.getByRole("searchbox", { name: "Найти проблему во всём каталоге" }).click();
        const category = page.getByRole("button", { name: "Другая проблема или вопрос", exact: true });
        if (await category.getAttribute("aria-expanded") !== "true") await category.click();
        await page.getByRole("button", { name: "Не нашёл свою проблему", exact: true }).click();
      }
      await open();
      if (legacy) {
        await expect(page.getByRole("heading", { name: "Скриншот или фото (необязательно)", exact: true })).toBeVisible();
        await expect(page.getByLabel("Комментарий к снимку (необязательно)", { exact: true })).not.toHaveAttribute("required", "");
        for (let i = 0; i < index; i++) await expect(page.getByText(`saved-${i}.png`, { exact: true })).toBeVisible();
        await open(); // Resume the same pinned server session and existing files.
        for (let i = 0; i < index; i++) await expect(page.getByText(`saved-${i}.png`, { exact: true })).toBeVisible();
      } else {
        await expect(page.getByText("Скриншот или фото ошибки", { exact: true })).toHaveCount(0);
        await page.getByRole("textbox", { name: "Describe the problem", exact: true }).fill("Не открывается окно");
      }
      await page.screenshot({ path: info.outputPath("optional-screenshots.png"), fullPage: true });
      await page.getByRole("button", { name: "Продолжить", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Проверьте обращение", exact: true })).toBeVisible();
      expect(answers).toEqual([legacy ? {} : { details: "Не открывается окно" }]);
      expect(errors).toEqual([]); expect(unexpected).toEqual([]); expect(writes).toBe(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
  }
}
