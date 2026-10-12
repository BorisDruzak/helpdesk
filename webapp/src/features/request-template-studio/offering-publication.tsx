import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { publishServiceCatalogObject } from "../service-catalog/api";

export function OfferingPublication({ code }: { code: string }) {
  const cache = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const mutation = useMutation({ mutationFn: () => publishServiceCatalogObject("offering", code), onSuccess: async () => { setConfirmed(false); await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); } });
  return <section aria-label="Публикация услуги" className="rounded-xl border border-amber-200 p-4">
    <h2 className="font-semibold">Услуга сохранена как черновик</h2>
    <p className="mt-2 text-sm">Сотрудники пока её не видят. Опубликуйте услугу с обычной формой. Пошаговый сценарий можно создать и включить позднее.</p>
    {confirmed ? <div className="mt-3 space-y-2"><p>Сделать эту услугу доступной сотрудникам? Сервер проверит форму, раздел и политики перед публикацией.</p><Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>Подтвердить публикацию услуги</Button><Button variant="ghost" disabled={mutation.isPending} onClick={() => setConfirmed(false)}>Отмена</Button></div> : <Button className="mt-3" onClick={() => setConfirmed(true)}>Опубликовать услугу</Button>}
    {mutation.isError && <p role="alert">Услуга не опубликована. Проверьте опубликованную форму, раздел и политики в настройках услуги.</p>}
  </section>;
}
