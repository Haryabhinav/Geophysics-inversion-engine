import { create } from 'zustand';

import type { PendingEvent, PersistedInversion } from '@types_/api';

export interface ActivityItem {
  kind: 'pending' | 'result';
  jobId: string;
  sensorId: string;
  dataType: string;
  status?: PersistedInversion['status'];
  at: number;
}

interface LiveStore {
  connected: boolean;
  activity: ActivityItem[];
  latestResultByJobId: Record<string, PersistedInversion>;
  setConnected: (connected: boolean) => void;
  pushPending: (event: PendingEvent) => void;
  pushResult: (record: PersistedInversion) => void;
}

const MAX_ACTIVITY = 100;

export const useLiveStore = create<LiveStore>((set) => ({
  connected: false,
  activity: [],
  latestResultByJobId: {},
  setConnected: (connected) => set({ connected }),
  pushPending: (event) =>
    set((state) => {
      const item: ActivityItem = {
        kind: 'pending',
        jobId: event.jobId,
        sensorId: event.sensorId,
        dataType: event.dataType,
        at: event.createdAt,
      };
      return { activity: [item, ...state.activity].slice(0, MAX_ACTIVITY) };
    }),
  pushResult: (record) =>
    set((state) => {
      const item: ActivityItem = {
        kind: 'result',
        jobId: record.jobId,
        sensorId: record.sensorId,
        dataType: record.dataType,
        status: record.status,
        at: Date.now(),
      };
      return {
        activity: [item, ...state.activity].slice(0, MAX_ACTIVITY),
        latestResultByJobId: { ...state.latestResultByJobId, [record.jobId]: record },
      };
    }),
}));
