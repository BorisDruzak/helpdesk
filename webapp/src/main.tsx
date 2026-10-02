import { startTransition } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { appRoutes } from "./app/router";
import { QueryProvider } from "./app/providers/query-provider";
import { SessionProvider } from "./features/auth/session-provider";
import { captureDeviceLinkFragment } from "./features/requester/device-link-state";
import "./styles.css";
import { readBrowserSentryConfig } from './observability/runtime-config';
import { initializeBrowserSentry } from './observability/sentry';


const container = document.getElementById("root");

if (!container) {
  throw new Error("Root container #root was not found.");
}

captureDeviceLinkFragment();
const observability = initializeBrowserSentry(readBrowserSentryConfig(document), appRoutes, window.location.origin);
const router = (observability?.createRouter ?? createBrowserRouter)(appRoutes);
const root = createRoot(container, observability?.rootOptions);

startTransition(() => {
  root.render(
    <QueryProvider>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryProvider>
  );
});
