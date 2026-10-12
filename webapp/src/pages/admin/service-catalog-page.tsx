import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { ServiceCatalogOfferingSettings } from "../../features/service-catalog/service-catalog-panel";

export function AdminServiceCatalogPage() {
  const { offeringCode } = useParams();
  const [params] = useSearchParams();
  return offeringCode ? <ServiceCatalogOfferingSettings key={offeringCode} code={offeringCode} />
    : <Navigate replace to={`/app/admin/request-template-studio${params.size ? `?${params}` : ""}`} />;
}
