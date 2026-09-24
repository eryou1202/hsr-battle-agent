/**
 * Render smoke test.
 *
 * Verifies the workspace actually mounts, loads a mock scenario, swaps between
 * scenarios and surfaces the required honesty markers (mock labelling, evidence
 * modes) without throwing. It asserts on user-visible text only — never on
 * internal implementation detail.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';
import { WorkspaceProvider } from './WorkspaceProvider';

// Auto-cleanup is not registered because Vitest globals are disabled here.
afterEach(() => cleanup());

function mount() {
  return render(
    <WorkspaceProvider>
      <App />
    </WorkspaceProvider>,
  );
}

describe('workspace smoke', () => {
  it('mounts and loads the default mock scenario', async () => {
    mount();

    await waitFor(() => {
      expect(screen.getByText('4.4.54')).toBeTruthy();
    });

    // Mock data must be labelled, and it must never look like live execution.
    expect(screen.getAllByText(/MOCK DATA/).length).toBeGreaterThan(0);

    // Fixture roster and board content rendered from adapter data.
    await waitFor(() => {
      expect(screen.getByText('Vanguard Unit')).toBeTruthy();
      expect(screen.getByText('Elite Adversary')).toBeTruthy();
    });

    // Top status bar metrics.
    expect(screen.getByText('state revision')).toBeTruthy();
    expect(screen.getByText('semantic hash')).toBeTruthy();
    expect(screen.getByText('rng draw pos')).toBeTruthy();
  });

  it('previews an action and exposes the preflight result', async () => {
    const user = userEvent.setup();
    mount();

    await waitFor(() => expect(screen.getByText('Run preflight')).toBeTruthy());

    await user.click(screen.getByText('Run preflight'));

    await waitFor(() => {
      // Local strict infrastructure — never an "official client certificate".
      expect(screen.getByText('LOCAL STRICT CERTIFICATE')).toBeTruthy();
    });
    expect(screen.getByText('dependency obligations (3)')).toBeTruthy();
    expect(screen.getAllByText('CLOSED').length).toBeGreaterThan(0);
  });

  it('renders the strict pipeline with per-stage states', async () => {
    const user = userEvent.setup();
    mount();
    await waitFor(() => expect(screen.getByText('Strict pipeline')).toBeTruthy());

    await user.click(screen.getByText('Strict pipeline'));

    await waitFor(() => {
      expect(screen.getByText('DependencyObligation')).toBeTruthy();
      expect(screen.getByText('StrictStepResult')).toBeTruthy();
    });
    // Before executing, the commit and strict stages are honestly unavailable.
    expect(screen.getAllByText('NOT_AVAILABLE').length).toBeGreaterThan(0);
  });

  it('separates pre-commit material from published output', async () => {
    const user = userEvent.setup();
    mount();
    await waitFor(() => expect(screen.getByText('Run preflight')).toBeTruthy());
    await user.click(screen.getByText('Run preflight'));
    await waitFor(() => expect(screen.getByText('Transaction')).toBeTruthy());

    await user.click(screen.getByText('Transaction'));
    await waitFor(() => {
      expect(screen.getAllByText('PRE-COMMIT · NOT LIVE').length).toBeGreaterThan(0);
    });
  });

  it('shows the FC-02 quarantine badges from contract-slot data', async () => {
    const user = userEvent.setup();
    mount();
    const selector = screen.getByTitle('Load a demo mock scenario') as HTMLSelectElement;
    await user.selectOptions(selector, 'G');

    await waitFor(() => expect(screen.getByText('Quarantine')).toBeTruthy());
    await user.click(screen.getByText('Quarantine'));

    await waitFor(() => {
      expect(screen.getAllByText('BLOCKED / QUARANTINED').length).toBeGreaterThan(0);
      expect(screen.getAllByText('REFERENCE ONLY').length).toBeGreaterThan(0);
    });
  });

  it('reports UNSUPPORTED SCHEMA for an unknown imported document', async () => {
    const user = userEvent.setup();
    mount();
    await waitFor(() => expect(screen.getByText('JSON import')).toBeTruthy());
    await user.click(screen.getByText('JSON import'));

    const textarea = document.querySelector('.import__textarea') as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.click(textarea);
    // paste() bypasses user-event's brace key handling.
    await user.paste('{"schema":"vendor.mystery/9","x":1}');
    await user.click(screen.getByText('Validate & import'));

    await waitFor(() => {
      expect(screen.getByText('UNSUPPORTED SCHEMA')).toBeTruthy();
    });
  });

  it('switches to the UNSUPPORTED scenario and shows the denied state', async () => {
    const user = userEvent.setup();
    mount();

    await waitFor(() => expect(screen.getByLabelText).toBeTruthy());

    const selector = screen.getByTitle('Load a demo mock scenario') as HTMLSelectElement;
    await user.selectOptions(selector, 'C');

    await waitFor(() => {
      expect(screen.getByText('Strike (unsupported target interaction)')).toBeTruthy();
    });
    expect(screen.getAllByText('UNSUPPORTED').length).toBeGreaterThan(0);
  });

  it('switches to the REFERENCE_MODEL scenario without promoting it', async () => {
    const user = userEvent.setup();
    mount();

    const selector = screen.getByTitle('Load a demo mock scenario') as HTMLSelectElement;
    await user.selectOptions(selector, 'D');

    await waitFor(() => {
      expect(screen.getByText('Signature action (reference estimate only)')).toBeTruthy();
    });

    await user.click(screen.getByText('Run preflight'));
    await waitFor(() => {
      expect(screen.getByText('certificate REFUSED')).toBeTruthy();
    });
  });

  it('renders the live adapter as an explicit disconnected state', async () => {
    const user = userEvent.setup();
    mount();
    await waitFor(() => expect(screen.getByText('4.4.54')).toBeTruthy());

    const adapterSelector = screen.getAllByRole('combobox')[1] as HTMLSelectElement;
    await user.selectOptions(adapterSelector, 'LIVE');

    await waitFor(() => {
      expect(screen.getAllByText('Backend disconnected').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/NOT_CONNECTED/).length).toBeGreaterThan(0);
  });

  it('filters the event console by category', async () => {
    const user = userEvent.setup();
    mount();

    await waitFor(() => expect(screen.getByText('Event / trace')).toBeTruthy());

    const consoleRegion = screen.getByText('Event / trace').closest('section');
    expect(consoleRegion).toBeTruthy();
    await user.click(within(consoleRegion as HTMLElement).getByText('BLOCKER'));

    await waitFor(() => {
      expect(within(consoleRegion as HTMLElement).getByText('BLOCKER')).toBeTruthy();
    });
  });
});
