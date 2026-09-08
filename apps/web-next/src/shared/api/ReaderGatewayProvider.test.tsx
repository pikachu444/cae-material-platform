import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useReaderScope, useReaderSession, ReaderGatewayProvider } from "./ReaderGatewayProvider";
import type { ReaderGateway } from "./reader-gateway";

const gateway = { mode: "prototype", scopeKey: "gateway", searchTestData: vi.fn(), getTestData: vi.fn(), searchCards: vi.fn(), getCard: vi.fn(), downloadCard: vi.fn(), patchDisplayMetadata: vi.fn() } as unknown as ReaderGateway;

function Probe() {
  const scope = useReaderScope();
  const session = useReaderSession();
  return <div><output data-testid="scope">{scope.actorID}|{scope.projectID}|{scope.effectiveAccessFingerprint}|{scope.authEpoch}</output><button onClick={() => void session.changeScope({ projectID: "other-project" })}>change</button><button onClick={() => void session.handleAuthFailure(401)}>unauthorized</button><button onClick={() => void session.handleAuthFailure(403)}>forbidden</button><button onClick={() => void session.logout()}>logout</button></div>;
}

describe("reader scope lifecycle", () => {
  it("clears query state and advances scope on change, 401, 403 and logout", async () => {
    const client = new QueryClient();
    client.setQueryData(["protected"], { id: "secret" });
    render(<QueryClientProvider client={client}><ReaderGatewayProvider gateway={gateway}><Probe /></ReaderGatewayProvider></QueryClientProvider>);
    expect(screen.getByTestId("scope").textContent).toContain("prototype-reviewer|rd01|dataset-read+export-read|1");
    fireEvent.click(screen.getByRole("button", { name: "change" }));
    await waitFor(() => expect(screen.getByTestId("scope").textContent).toContain("other-project"));
    expect(client.getQueryData(["protected"])).toBeUndefined();
    fireEvent.click(screen.getByRole("button", { name: "unauthorized" }));
    await waitFor(() => expect(screen.getByTestId("scope").textContent).toContain("session-recovery|other-project|none"));
    fireEvent.click(screen.getByRole("button", { name: "forbidden" }));
    await waitFor(() => expect(screen.getByTestId("scope").textContent).toContain("library-read-only"));
    fireEvent.click(screen.getByRole("button", { name: "logout" }));
    await waitFor(() => expect(screen.getByTestId("scope").textContent).toContain("anonymous|other-project|none"));
  });
});
