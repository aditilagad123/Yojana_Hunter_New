/**
 * URL Utilities for Government Scheme Navigation
 * Validates external portals, ensures safe protocols, and prevents malformed URLs.
 */

/**
 * Validates that a URL is a secure/valid HTTP or HTTPS URL.
 * Strictly prevents javascript:, data:, file:, and malformed URL attacks.
 */
export function isValidHttpUrl(url?: string | null): boolean {
  if (!url || typeof url !== "string") return false;
  const trimmed = url.trim();
  if (!trimmed) return false;

  const lower = trimmed.toLowerCase();
  if (
    lower.startsWith("javascript:") ||
    lower.startsWith("data:") ||
    lower.startsWith("file:") ||
    lower.startsWith("vbscript:") ||
    lower.startsWith("about:") ||
    lower.startsWith("blob:")
  ) {
    return false;
  }

  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return false;
    }
    if (!parsed.hostname || (!parsed.hostname.includes(".") && parsed.hostname !== "localhost")) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

/**
 * Checks whether an application URL is distinct from the primary official URL.
 */
export function isDistinctApplicationUrl(appUrl?: string | null, officialUrl?: string | null): boolean {
  if (!isValidHttpUrl(appUrl)) return false;
  if (!isValidHttpUrl(officialUrl)) return true;

  const cleanApp = (appUrl || "").trim().replace(/\/+$/, "").toLowerCase();
  const cleanOff = (officialUrl || "").trim().replace(/\/+$/, "").toLowerCase();
  return cleanApp !== cleanOff;
}

/**
 * Returns user-friendly status message for unavailable portals.
 */
export function getFriendlyPortalUnavailableMessage(hasAlternative: boolean = false): string {
  if (hasAlternative) {
    return "The primary official portal could not be reached. It may be temporarily unavailable. A verified alternative official government portal is provided below.";
  }
  return "The official portal could not be reached. It may be temporarily unavailable. You can review the scheme details and try again later.";
}
