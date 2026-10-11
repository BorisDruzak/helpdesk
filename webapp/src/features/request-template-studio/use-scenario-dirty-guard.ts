import { useEffect } from "react";
import { useBlocker } from "react-router-dom";

export function useScenarioDirtyGuard(dirty: boolean) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty && `${currentLocation.pathname}${currentLocation.search}` !== `${nextLocation.pathname}${nextLocation.search}`);
  useEffect(() => {
    if (!dirty) return;
    function beforeUnload(event: BeforeUnloadEvent) { event.preventDefault(); event.returnValue = ""; }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm("Есть несохранённые изменения в Студии. Покинуть страницу?")) blocker.proceed();
    else blocker.reset();
  }, [blocker]);
}
