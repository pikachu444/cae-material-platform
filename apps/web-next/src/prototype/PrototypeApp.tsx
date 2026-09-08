import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { useMemo } from "react";
import { AppShell } from "../app/AppShell";
import { ReaderGatewayProvider } from "../shared/api/ReaderGatewayProvider";
import { CardsReader } from "../features/cards/ui/CardsReader";
import { TestDataReader } from "../features/test-data/ui/TestDataReader";
import { createPrototypeReaderGateway } from "./prototype-gateway";
import { ReaderState } from "../shared/ui/ReaderState";

export function PrototypeApp() {
  const gateway = useMemo(() => createPrototypeReaderGateway(), []);
  const queryClient = useMemo(() => new QueryClient({
    defaultOptions: {
      queries: { staleTime: 15_000, gcTime: 5 * 60_000, retry: false },
    },
  }), []);
  return (
    <QueryClientProvider client={queryClient}>
      <ReaderGatewayProvider gateway={gateway}>
        <BrowserRouter>
          <AppShell mode="prototype">
            <Routes>
              <Route path="/" element={<Navigate to="/test-data" replace />} />
              <Route path="/test-data" element={<TestDataReader />} />
              <Route path="/test-data/:id" element={<TestDataReader />} />
              <Route path="/cards" element={<CardsReader />} />
              <Route path="/cards/:id" element={<CardsReader />} />
              <Route path="/materials" element={<PrototypeSection title="Materials" description="The compatible Materials entry remains available while the new direct readers are reviewed." />} />
              <Route path="/modeling" element={<PrototypeSection title="Modeling" description="Modeling can reuse the curve-focused grammar in a later connected reader unit." />} />
              <Route path="/activity" element={<PrototypeSection title="Activity" description="Activity is outside the RD-01 reader slice." />} />
              <Route path="/administration" element={<PrototypeSection title="Administration" description="Administration stays outside the RD-01 reader slice." />} />
              <Route path="*" element={<Navigate to="/test-data" replace />} />
            </Routes>
          </AppShell>
        </BrowserRouter>
      </ReaderGatewayProvider>
    </QueryClientProvider>
  );
}

function PrototypeSection({ title, description }: { title: string; description: string }) {
  return <div style={{ maxWidth: 720 }}><p style={{ color: "var(--cmp-blue-strong)", fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase" }}>Prototype foundation</p><h1>{title}</h1><ReaderState title="Reader slice only" description={description} /></div>;
}
