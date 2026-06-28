const API_KEY_STORAGE_KEY = "lg:chat:apiKey";

export function getApiKey(): string | null {
  try {
    if (typeof window === "undefined") return null;
    const sessionKey = window.sessionStorage.getItem(API_KEY_STORAGE_KEY);
    if (sessionKey) return sessionKey;
    const legacyKey = window.localStorage.getItem(API_KEY_STORAGE_KEY);
    if (legacyKey) {
      window.sessionStorage.setItem(API_KEY_STORAGE_KEY, legacyKey);
      window.localStorage.removeItem(API_KEY_STORAGE_KEY);
      return legacyKey;
    }
  } catch {
    // no-op
  }

  return null;
}

export function storeApiKey(key: string): void {
  try {
    if (typeof window === "undefined") return;
    if (key) {
      window.sessionStorage.setItem(API_KEY_STORAGE_KEY, key);
    } else {
      window.sessionStorage.removeItem(API_KEY_STORAGE_KEY);
    }
    window.localStorage.removeItem(API_KEY_STORAGE_KEY);
  } catch {
    // no-op
  }
}
