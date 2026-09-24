/**
 * Mirrors `hsr_battle_agent.battle_sandbox.gate_certificate.GateCertificate`.
 *
 * The certificate is sealed server-side. The frontend only ever displays one it
 * was handed, and it explicitly supports "certificate refused" so a reference or
 * non-native result is never rendered as if it had been certified.
 */
import type { ContractRef, EvidenceMode } from './evidence';
import type { ObligationAccess, PreflightResult } from './preflight';
import type { SnapshotPolicyIdentity, StateRevision } from './state';

/**
 * Mirrors `gate_certificate.GATE_CERTIFICATE_SCHEMA`.
 *
 * The serialized value is "terra_gate_certificate/1". This is LOCAL STRICT
 * integrity infrastructure: it is never labelled an official client or native
 * game certificate.
 */
export const GATE_CERTIFICATE_SCHEMA = 'terra_gate_certificate/1' as const;

/** The only label permitted for this panel. */
export const CERTIFICATE_PANEL_LABEL = 'LOCAL STRICT CERTIFICATE' as const;

export interface GateCertificate {
  readonly schema: typeof GATE_CERTIFICATE_SCHEMA;
  readonly planIdentity: string;
  readonly evidenceMode: EvidenceMode;
  readonly policyIdentity: SnapshotPolicyIdentity;
  readonly inputIdentity: string;
  readonly inputRevision: string;
  readonly stateRevision: StateRevision;
  readonly contractRef: ContractRef;
  readonly contractRevision: string;
  readonly closureIdentity: string;
  readonly allowedReads: readonly ObligationAccess[];
  readonly allowedWrites: readonly ObligationAccess[];
  /** Certificate identity, supplied by the backend. */
  readonly identity: string;
}

/**
 * Whether a certificate exists for the inspected preflight.
 *
 * `REFUSED` is a first-class state: the backend can close a closure locally and
 * still refuse to seal a certificate (for example when an obligation carries
 * `REFERENCE_MODEL` evidence). The frontend must render that refusal rather than
 * silently showing "no certificate".
 */
export type CertificateStatus = 'ISSUED' | 'REFUSED' | 'NOT_REQUESTED' | 'STALE';

export interface CertificateView {
  readonly status: CertificateStatus;
  readonly certificate: GateCertificate | null;
  /** Why no certificate could be sealed, when `status !== "ISSUED"`. */
  readonly refusalReason: string | null;
  /** The revision the certificate was sealed against, when supplied. */
  readonly sealedAgainstRevision: StateRevision | null;
}

/** Does the certificate match the revision currently displayed as live? */
export function certificateMatchesRevision(
  view: CertificateView,
  live: StateRevision | null,
): 'MATCHES' | 'STALE' | 'UNKNOWN' {
  if (!view.certificate || !live) return 'UNKNOWN';
  const sealed = view.certificate.stateRevision;
  if (sealed.counter !== live.counter) return 'STALE';
  if (sealed.snapshotId !== live.snapshotId) return 'STALE';
  return 'MATCHES';
}

export function certificateAppliesTo(view: CertificateView, result: PreflightResult): boolean {
  if (!view.certificate) return false;
  return view.certificate.closureIdentity.length > 0 && result.closure.blockers.length === 0;
}
