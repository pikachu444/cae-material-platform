import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { useMemo } from "react";
import { AppShell } from "./AppShell";
import { MaterialsReader } from "../features/materials/ui/MaterialsReader";
import { ModelsReader } from "../features/models/ui/ModelsReader";
import { ConnectedTestDataReader } from "../features/test-data/ui/ConnectedTestDataReader";
import { ProcessingOutputsReader } from "../features/processing-output/ui/ProcessingOutputsReader";
import { ConnectedCardsReader } from "../features/cards/ui/ConnectedCardsReader";
import { NeutralMaterialReader } from "../features/cards/ui/NeutralMaterialReader";

export function LiveApp() {
  const queryClient = useMemo(() => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } }), []);
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell mode="live">
          <Routes>
            <Route path="/" element={<Navigate to="/materials" replace />} />
            <Route path="/materials" element={<MaterialsReader />} />
            <Route path="/test-data" element={<ConnectedTestDataReader />} />
            <Route path="/processing-outputs" element={<ProcessingOutputsReader />} />
            <Route path="/models" element={<ModelsReader />} />
            <Route path="/cards" element={<ConnectedCardsReader />} />
            <Route path="/neutral-materials" element={<NeutralMaterialReader />} />
            <Route path="*" element={<Navigate to="/materials" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
