import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { SessionProvider } from "../../src/features/auth/session-provider";
import { TicketDetailPage } from "../../src/pages/tickets/detail-page";
import "./compat-detail.css";

const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}>
    <SessionProvider>
      <BrowserRouter><Routes><Route path="/app/tickets/:ticketId" element={<TicketDetailPage />} /></Routes></BrowserRouter>
    </SessionProvider>
  </QueryClientProvider>,
);
