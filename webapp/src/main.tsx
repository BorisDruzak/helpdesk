import { startTransition } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { appRoutes } from "./app/router";
import { QueryProvider } from "./app/providers/query-provider";
import { SessionProvider } from "./features/auth/session-provider";
import "./styles.css";


const container = document.getElementById("root");

if (!container) {
  throw new Error("Root container #root was not found.");
}

const router = createBrowserRouter(appRoutes);
const root = createRoot(container);

startTransition(() => {
  root.render(
    <QueryProvider>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryProvider>
  );
});
