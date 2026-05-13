import { ExternalLink, PackageOpen } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";

export function SdkModulesTab() {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PackageOpen className="h-5 w-5 text-brand-700" />
          SDK Modules
        </CardTitle>
        <CardDescription>
          ZIP-модули агента, preflight, live tests, preferred rollout и provider config остаются в существующем Modules Workbench.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-[1rem] border border-border bg-surface-subtle px-5 py-5">
          <p className="font-semibold text-slate-950">Modules Workbench не переписывается в MVP</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Capability Studio показывает универсальный каталог возможностей. SDK/ZIP authoring и rollout для
            `agent_managed_module` остаются в текущем workbench, чтобы не ломать module API и live-test flows.
          </p>
        </div>
        <Button leadingIcon={<ExternalLink className="h-4 w-4" />} onClick={() => navigate("/app/admin/modules")}>
          Открыть Modules Workbench
        </Button>
      </CardContent>
    </Card>
  );
}
