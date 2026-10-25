import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";


type QueryProviderProps = {
  children: ReactNode;
  client?: QueryClient;
};


export function createAppQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
        refetchOnWindowFocus: false
      }
    }
  });
}

export function QueryProvider({ children, client }: QueryProviderProps) {
  const [queryClient] = useState(() => client ?? createAppQueryClient());

  return <QueryClientProvider client={client ?? queryClient}>{children}</QueryClientProvider>;
}
