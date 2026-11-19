export {};
declare global {
  interface Window {
    bujjiDesktop?: {
      openSettingsFolder(): Promise<{opened:boolean}>;
      openComputer(): Promise<{opened:boolean}>;
      closeComputer(): Promise<{closed:boolean}>;
      computer(request: Record<string,unknown>): Promise<any>;
      chooseDocumentFolder(): Promise<{
        grant_id: string;
        folder: string;
      } | null>;
      bootstrap(): Promise<{ token: string; origin: string }>;
      preferences(): Promise<{
        soundEnabled: boolean;
        startAtLogin: boolean;
        notificationsSupported: boolean;
        packaged: boolean;
      }>;
      setPreferences(value: {
        soundEnabled?: boolean;
        startAtLogin?: boolean;
      }): Promise<{
        soundEnabled: boolean;
        startAtLogin: boolean;
        notificationsSupported: boolean;
        packaged: boolean;
      }>;
      testSound(): Promise<{ ok: boolean; reason: string }>;
      testNotification(): Promise<{
        notificationRequested: boolean;
        sound: { ok: boolean; reason: string };
      }>;
      onHidden(callback: () => void): () => void;
    };
  }
}
