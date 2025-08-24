// Central event bus for cross-component communication
export const appEvents = new EventTarget()

export type EmotionEventDetail = { label: string }

export type MouthEventDetail = { label: string; durationMs?: number }


