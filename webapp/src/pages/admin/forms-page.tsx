import { useSession } from "../../features/auth/session-provider";
import { FormsBuilderWorkspace } from "../../features/forms-builder/forms-builder-workspace";

export function AdminFormsPage() {
  const { session } = useSession();

  return <FormsBuilderWorkspace permissions={session?.permissions ?? []} />;
}
