import * as cryptoNode from "crypto";

const SESSION_COOKIE = "finance_news_session";
const CSRF_COOKIE = "finance_news_csrf";
const SESSION_TTL_SECONDS = 60 * 60 * 8;

export type SessionPayload = {
  u: string;
  sid: string;
  exp: number;
};

const encoder = new TextEncoder();

const useNodeCrypto =
  typeof cryptoNode.createHash === "function" &&
  (globalThis.crypto == null || !("subtle" in globalThis.crypto));

function randomId(length = 16): string {
  const bytes = new Uint8Array(length);
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = cryptoNode.randomBytes(1)[0];
    }
  }
  return toBase64Url(bytes);
}

function toBase64(data: string): string {
  if (typeof btoa === "function") {
    return btoa(data);
  }
  return Buffer.from(data, "binary").toString("base64");
}

function atobSafe(value: string): string {
  if (typeof atob === "function") {
    return atob(value);
  }
  return Buffer.from(value, "base64").toString("binary");
}

function toBase64Url(bytes: Uint8Array): string {
  let raw = "";
  for (let i = 0; i < bytes.length; i += 1) {
    raw += String.fromCharCode(bytes[i]);
  }
  return toBase64(raw).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function fromBase64Url(value: string): string {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return atobSafe(padded);
}

async function importHmacKey(secret: string): Promise<CryptoKey> {
  if (globalThis.crypto?.subtle) {
    return globalThis.crypto.subtle.importKey(
      "raw",
      encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign", "verify"],
    );
  }

  if (useNodeCrypto) {
    // Node fallback path uses HMAC verification with createHmac
    return Promise.resolve(secret as unknown as CryptoKey);
  }

  throw new Error("Crypto unavailable");
}

async function signValue(value: string, secret: string): Promise<string> {
  if (globalThis.crypto?.subtle) {
    const key = await importHmacKey(secret);
    const signature = await globalThis.crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(value),
    );
    return toBase64Url(new Uint8Array(signature));
  }

  if (useNodeCrypto) {
    return toBase64Url(
      new Uint8Array(
        cryptoNode
          .createHmac("sha256", secret)
          .update(value)
          .digest(),
      ),
    );
  }

  throw new Error("Crypto unavailable");
}

export async function createSessionToken(
  username: string,
  secret: string,
  ttlSeconds = SESSION_TTL_SECONDS,
): Promise<string> {
  const payload: SessionPayload = {
    u: username,
    sid: randomId(18),
    exp: Math.floor(Date.now() / 1000) + ttlSeconds,
  };
  const encodedPayload = toBase64Url(encoder.encode(JSON.stringify(payload)));
  const signature = await signValue(encodedPayload, secret);
  return `${encodedPayload}.${signature}`;
}

export async function verifySessionToken(
  token: string,
  secret: string,
): Promise<SessionPayload | null> {
  const [payloadPart, signaturePart] = token.split(".");
  if (!payloadPart || !signaturePart) {
    return null;
  }

  const expectedSignature = await signValue(payloadPart, secret);
  if (expectedSignature !== signaturePart) {
    return null;
  }

  try {
    const payloadRaw = fromBase64Url(payloadPart);
    const payload = JSON.parse(payloadRaw) as SessionPayload;
    if (!payload?.u || !payload?.exp || !payload?.sid) {
      return null;
    }
    if (payload.exp <= Math.floor(Date.now() / 1000)) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

export function getAuthSecret(): string {
  return process.env.AUTH_SECRET ?? "change-this-auth-secret";
}

export function generateCsrfToken(): string {
  return randomId(24);
}

export { SESSION_COOKIE, CSRF_COOKIE, SESSION_TTL_SECONDS };
