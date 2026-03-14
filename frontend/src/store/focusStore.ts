import { create } from 'zustand';

interface FocusState {
  isInSession: boolean;
  currentSessionId: string | null;
  plannedDuration: number;
  remainingSeconds: number;
  setSession: (sessionId: string, duration: number) => void;
  updateRemainingSeconds: (seconds: number) => void;
  clearSession: () => void;
}

export const useFocusStore = create<FocusState>((set) => ({
  isInSession: false,
  currentSessionId: null,
  plannedDuration: 0,
  remainingSeconds: 0,
  setSession: (sessionId: string, duration: number) =>
    set({
      isInSession: true,
      currentSessionId: sessionId,
      plannedDuration: duration,
      remainingSeconds: duration * 60,
    }),
  updateRemainingSeconds: (seconds: number) =>
    set({ remainingSeconds: seconds }),
  clearSession: () =>
    set({
      isInSession: false,
      currentSessionId: null,
      plannedDuration: 0,
      remainingSeconds: 0,
    }),
}));
