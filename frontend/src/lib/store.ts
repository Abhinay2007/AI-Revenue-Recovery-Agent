import { create } from "zustand";
import type { AuditEntry, PendingApprovalItem } from "./types";

interface AppStore {
  // Pending approvals (in-memory, mirrors backend's pending_approval_store)
  pendingApprovals: PendingApprovalItem[];
  addPendingApproval: (item: PendingApprovalItem) => void;
  removePendingApproval: (id: string) => void;
  clearApprovals: () => void;

  // Audit trail (reconstructed from agent responses)
  auditEntries: AuditEntry[];
  addAuditEntry: (entry: AuditEntry) => void;
  clearAudit: () => void;

  // Session
  sessionId: string;
}

export const useAppStore = create<AppStore>((set) => ({
  pendingApprovals: [],
  addPendingApproval: (item) =>
    set((state) => ({
      pendingApprovals: [item, ...state.pendingApprovals],
    })),
  removePendingApproval: (id) =>
    set((state) => ({
      pendingApprovals: state.pendingApprovals.filter((p) => p.pending_action_id !== id),
    })),
  clearApprovals: () => set({ pendingApprovals: [] }),

  auditEntries: [],
  addAuditEntry: (entry) =>
    set((state) => ({
      auditEntries: [entry, ...state.auditEntries],
    })),
  clearAudit: () => set({ auditEntries: [] }),

  sessionId: `session_${Date.now()}`,
}));
