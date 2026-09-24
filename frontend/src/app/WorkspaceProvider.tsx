import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type {
  ActionPreview,
  ActionRequest,
  AvailableAction,
  BattleSetup,
  BattleSnapshot,
  CloneInfo,
  EventCategory,
  EvidenceRecord,
  ExecutionResult,
  QuarantineEntry,
  SessionInfo,
  TraceEvent,
} from '../models';
import type { BattleBackendAdapter } from '../adapters';
import { MockBattleBackendAdapter, LiveBattleBackendAdapter } from '../adapters';
import { MOCK_SCENARIO_DESCRIPTORS } from '../fixtures';

export type AdapterKind = 'MOCK' | 'LIVE';

export type ConsoleTab =
  | 'TRACE'
  | 'PIPELINE'
  | 'TRANSACTION'
  | 'DIFF'
  | 'QUARANTINE'
  | 'IMPORT'
  | 'RAW';

export interface WorkspaceState {
  readonly adapterKind: AdapterKind;
  readonly scenarioId: string;
  readonly session: SessionInfo | null;
  readonly setup: BattleSetup | null;
  readonly snapshot: BattleSnapshot | null;
  readonly actions: readonly AvailableAction[];
  readonly events: readonly TraceEvent[];
  /** FC-02 contract quarantine slots supplied by the adapter. */
  readonly quarantine: readonly QuarantineEntry[];
  readonly selectedActionId: string | null;
  readonly preview: ActionPreview | null;
  readonly execution: ExecutionResult | null;
  readonly selectedUnitId: string | null;
  readonly targetUnitId: string | null;
  readonly loading: boolean;
  /** Explicit failure code, e.g. BACKEND_NOT_CONNECTED. Never a generic error. */
  readonly failureCode: string | null;
  readonly failureMessage: string | null;
  readonly consoleTab: ConsoleTab;
  readonly eventFilter: EventCategory;
  readonly drawer: EvidenceRecord | null;
  readonly cloneInfo: CloneInfo | null;
  readonly lastActionAt: number | null;
}

export interface WorkspaceActions {
  setAdapterKind: (kind: AdapterKind) => void;
  selectScenario: (scenarioId: string) => void;
  selectAction: (actionId: string | null) => void;
  selectUnit: (unitId: string | null) => void;
  setTarget: (unitId: string | null) => void;
  previewSelected: () => void;
  executeSelected: () => void;
  reset: () => void;
  setConsoleTab: (tab: ConsoleTab) => void;
  setEventFilter: (filter: EventCategory) => void;
  openDrawer: (record: EvidenceRecord) => void;
  closeDrawer: () => void;
}

const WorkspaceContext = createContext<
  { state: WorkspaceState; actions: WorkspaceActions } | null
>(null);

function createAdapter(kind: AdapterKind): BattleBackendAdapter {
  return kind === 'MOCK' ? new MockBattleBackendAdapter() : new LiveBattleBackendAdapter();
}

function messageFor(error: unknown): { code: string; message: string } {
  if (error && typeof error === 'object' && 'code' in error) {
    const code = String((error as { code: unknown }).code);
    const text = error instanceof Error ? error.message : String(code);
    return { code, message: text };
  }
  if (error instanceof Error) return { code: 'ADAPTER_FAILURE', message: error.message };
  return { code: 'ADAPTER_FAILURE', message: 'Unknown adapter failure.' };
}

export function WorkspaceProvider({ children }: { readonly children: ReactNode }) {
  const [adapterKind, setAdapterKindState] = useState<AdapterKind>('MOCK');
  const [scenarioId, setScenarioId] = useState<string>(
    MOCK_SCENARIO_DESCRIPTORS[0]?.id ?? 'A',
  );
  const adapterRef = useRef<BattleBackendAdapter>(createAdapter('MOCK'));

  const [session, setSession] = useState<SessionInfo | null>(null);
  const [setup, setSetup] = useState<BattleSetup | null>(null);
  const [snapshot, setSnapshot] = useState<BattleSnapshot | null>(null);
  const [actions, setActions] = useState<readonly AvailableAction[]>([]);
  const [events, setEvents] = useState<readonly TraceEvent[]>([]);
  const [quarantine, setQuarantine] = useState<readonly QuarantineEntry[]>([]);
  const [cloneInfo, setCloneInfo] = useState<CloneInfo | null>(null);

  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [preview, setPreview] = useState<ActionPreview | null>(null);
  const [execution, setExecution] = useState<ExecutionResult | null>(null);

  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [targetUnitId, setTargetUnitId] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [failureCode, setFailureCode] = useState<string | null>(null);
  const [failureMessage, setFailureMessage] = useState<string | null>(null);
  const [lastActionAt, setLastActionAt] = useState<number | null>(null);

  const [consoleTab, setConsoleTab] = useState<ConsoleTab>('TRACE');
  const [eventFilter, setEventFilter] = useState<EventCategory>('ALL');
  const [drawer, setDrawer] = useState<EvidenceRecord | null>(null);

  const load = useCallback(async (scenario: string) => {
    const adapter = adapterRef.current;
    setLoading(true);
    try {
      if (adapter instanceof MockBattleBackendAdapter) {
        adapter.loadScenario(scenario);
      }
      const [nextSession, nextSnapshot, nextSetup, nextActions, nextEvents, nextQuarantine] =
        await Promise.all([
          adapter.getSessionInfo(),
          adapter.getBattleSnapshot(),
          adapter.getBattleSetup(),
          adapter.getAvailableActions(),
          adapter.getTraceEvents(),
          adapter.getQuarantineEntries(),
        ]);
      setSession(nextSession);
      setSnapshot(nextSnapshot);
      setSetup(nextSetup);
      setActions(nextActions);
      setEvents(nextEvents);
      setQuarantine(nextQuarantine);
      setCloneInfo(adapter.cloneInfo());
      setSelectedActionId(nextActions[0]?.id ?? null);
      setPreview(null);
      setExecution(null);
      setSelectedUnitId(nextSnapshot?.currentActorId ?? nextSnapshot?.allies[0]?.id ?? null);
      setTargetUnitId(nextSnapshot?.selectedTargetId ?? null);
      setFailureCode(null);
      setFailureMessage(null);
      setConsoleTab('TRACE');
    } catch (error) {
      const { code, message } = messageFor(error);
      setSession(null);
      setSnapshot(null);
      setSetup(null);
      setActions([]);
      setEvents([]);
      setQuarantine([]);
      setPreview(null);
      setExecution(null);
      setFailureCode(code);
      setFailureMessage(message);
      setCloneInfo(adapter.cloneInfo());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(scenarioId);
  }, [adapterKind, scenarioId, load]);

  const currentTarget = useRef<string | null>(null);
  currentTarget.current = targetUnitId;

  const previewSelected = useCallback(async () => {
    if (!selectedActionId) return;
    const adapter = adapterRef.current;
    setLoading(true);
    try {
      const request: ActionRequest = {
        actionId: selectedActionId,
        targetId: currentTarget.current,
      };
      const result = await adapter.previewAction(request);
      setPreview(result);
      setFailureCode(null);
      setFailureMessage(result === null ? 'NO_PREVIEW_SUPPLIED' : null);
    } catch (error) {
      const { code, message } = messageFor(error);
      setPreview(null);
      setFailureCode(code);
      setFailureMessage(message);
    } finally {
      setLoading(false);
      setLastActionAt(Date.now());
      setConsoleTab('TRANSACTION');
    }
  }, [selectedActionId]);

  const executeSelected = useCallback(async () => {
    if (!selectedActionId) return;
    const adapter = adapterRef.current;
    setLoading(true);
    try {
      const request: ActionRequest = {
        actionId: selectedActionId,
        targetId: currentTarget.current,
      };
      const result = await adapter.executeAction(request);
      setExecution(result);
      setFailureCode(null);
      setFailureMessage(null);
      setConsoleTab('TRANSACTION');
      // Re-read session so revision / transaction state stay truthful.
      const nextSession = await adapter.getSessionInfo();
      setSession(nextSession);
    } catch (error) {
      const { code, message } = messageFor(error);
      setExecution(null);
      setFailureCode(code);
      setFailureMessage(message);
    } finally {
      setLoading(false);
      setLastActionAt(Date.now());
    }
  }, [selectedActionId]);

  const reset = useCallback(async () => {
    const adapter = adapterRef.current;
    setLoading(true);
    try {
      const nextSession = await adapter.reset();
      setSession(nextSession);
      setPreview(null);
      setExecution(null);
      setFailureCode(null);
      setFailureMessage(null);
      setConsoleTab('TRACE');
    } catch (error) {
      const { code, message } = messageFor(error);
      setFailureCode(code);
      setFailureMessage(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const setAdapterKind = useCallback((kind: AdapterKind) => {
    adapterRef.current = createAdapter(kind);
    setAdapterKindState(kind);
    setDrawer(null);
  }, []);

  const selectScenario = useCallback((next: string) => {
    adapterRef.current =
      adapterRef.current instanceof MockBattleBackendAdapter
        ? adapterRef.current
        : new MockBattleBackendAdapter();
    setAdapterKindState((current) => current);
    setScenarioId(next);
    setDrawer(null);
  }, []);

  const value = useMemo(
    () => ({
      state: {
        adapterKind,
        scenarioId,
        session,
        setup,
        snapshot,
        actions,
        events,
        quarantine,
        selectedActionId,
        preview,
        execution,
        selectedUnitId,
        targetUnitId,
        loading,
        failureCode,
        failureMessage,
        consoleTab,
        eventFilter,
        drawer,
        cloneInfo,
        lastActionAt,
      },
      actions: {
        setAdapterKind,
        selectScenario,
        selectAction: setSelectedActionId,
        selectUnit: setSelectedUnitId,
        setTarget: setTargetUnitId,
        previewSelected: () => void previewSelected(),
        executeSelected: () => void executeSelected(),
        reset: () => void reset(),
        setConsoleTab,
        setEventFilter,
        openDrawer: setDrawer,
        closeDrawer: () => setDrawer(null),
      },
    }),
    [
      adapterKind,
      scenarioId,
      session,
      setup,
      snapshot,
      actions,
      events,
      quarantine,
      selectedActionId,
      preview,
      execution,
      selectedUnitId,
      targetUnitId,
      loading,
      failureCode,
      failureMessage,
      consoleTab,
      eventFilter,
      drawer,
      cloneInfo,
      lastActionAt,
      setAdapterKind,
      selectScenario,
      previewSelected,
      executeSelected,
      reset,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('useWorkspace must be used inside WorkspaceProvider');
  return context;
}
