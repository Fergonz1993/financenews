const DEFAULT_INTERNAL_USER_ID = 'operator';
const LEGACY_INTERNAL_USER_IDS = ['anonymous', 'user1'] as const;

function normalizeUserId(candidate: string | undefined | null): string {
  return String(candidate || '').trim();
}

export function getInternalUserId(): string {
  const candidate = normalizeUserId(
    (typeof window === 'undefined'
      ? process.env.INTERNAL_USER_ID || process.env.NEXT_PUBLIC_INTERNAL_USER_ID
      : process.env.NEXT_PUBLIC_INTERNAL_USER_ID) || DEFAULT_INTERNAL_USER_ID
  );
  const normalized = normalizeUserId(candidate);
  return normalized || DEFAULT_INTERNAL_USER_ID;
}

export function resolveInternalUserIds(userId?: string | null): string[] {
  const canonicalUserId = getInternalUserId();
  const requestedUserId = normalizeUserId(userId || canonicalUserId) || canonicalUserId;
  const candidates = [requestedUserId];

  if (requestedUserId === canonicalUserId) {
    candidates.push(...LEGACY_INTERNAL_USER_IDS);
  }

  return candidates.filter(
    (candidate, index) =>
      Boolean(candidate) && candidates.indexOf(candidate) === index
  );
}
