import { Navigate, useSearchParams } from "react-router-dom";
export function AdminServiceCreatePage(){const [params]=useSearchParams();const query=new URLSearchParams(params);query.set("create","1");return <Navigate replace to={`/app/admin/request-template-studio?${query}`}/>;}
