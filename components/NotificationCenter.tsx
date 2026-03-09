import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import {
  AlertCircle,
  Bell,
  CheckCheck,
  CheckCircle2,
  Info,
  MoreHorizontal,
  Trash2,
  TriangleAlert,
  XCircle,
} from 'lucide-react';
import { FASTAPI_BASE_URL } from '@/pages/api/_utils/fastapiProxy';
import { cn } from '@/lib/utils';
import { useNotification } from '../lib/notification-context';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';

type Notification = {
  id: string;
  timestamp: string;
  read: boolean;
  type: string;
  title: string;
  message: string;
  source?: string;
  severity: 'success' | 'error' | 'warning' | 'info';
  url?: string;
};

type WsEnvelope = {
  type: string;
  payload?: Record<string, unknown>;
  ts?: string;
  request_id?: string;
  alert?: Record<string, unknown>;
  news?: Record<string, unknown>;
};

const WEBSOCKET_PATH = '/ws';
const MAX_RECONNECT_DELAY_MS = 15_000;

const createNotificationId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
};

const clampDateString = (value: string | undefined): string => {
  if (!value) {
    return new Date().toISOString();
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
};

const parseEnvelope = (raw: string): WsEnvelope | null => {
  try {
    const payload = JSON.parse(raw) as unknown;
    if (!payload || typeof payload !== 'object' || typeof (payload as { type?: unknown }).type !== 'string') {
      return null;
    }
    const typed = payload as WsEnvelope;
    return typed;
  } catch {
    return null;
  }
};

const normalizeSeverity = (raw: unknown): Notification['severity'] => {
  if (raw === 'success' || raw === 'error' || raw === 'warning' || raw === 'info') {
    return raw;
  }
  return 'info';
};

const parseString = (value: unknown, fallback = ''): string => {
  return typeof value === 'string' ? value : fallback;
};

const NotificationCenter = (): React.JSX.Element => {
  const router = useRouter();
  const { notifyInfo, notifyError, notifySuccess } = useNotification();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);

  const websocketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const connectRef = useRef<() => void>(() => { });

  const unreadCount = useMemo(
    () => notifications.reduce((count, notification) => count + (notification.read ? 0 : 1), 0),
    [notifications]
  );

  const resolveWsUrl = useCallback((): string | null => {
    const candidates = [
      process.env.NEXT_PUBLIC_WS_URL,
      process.env.NEXT_PUBLIC_API_URL,
      FASTAPI_BASE_URL,
      process.env.BACKEND_API_URL,
      process.env.FASTAPI_URL,
    ];

    for (const candidate of candidates) {
      if (!candidate || typeof candidate !== 'string') {
        continue;
      }

      try {
        const parsed = new URL(candidate);
        const protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${parsed.host}${WEBSOCKET_PATH}`;
      } catch {
        continue;
      }
    }

    return 'ws://127.0.0.1:8000/ws';
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const closeSocket = useCallback(() => {
    const socket = websocketRef.current;
    if (!socket) {
      return;
    }
    websocketRef.current = null;
    socket.close();
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) {
      return;
    }
    setIsReconnecting(true);
    const backoff = Math.min(1_000 * 2 ** Math.min(reconnectAttemptRef.current, 5), MAX_RECONNECT_DELAY_MS);
    reconnectAttemptRef.current += 1;
    clearReconnectTimer();
    reconnectTimerRef.current = setTimeout(() => {
      connectRef.current();
    }, backoff);
  }, [clearReconnectTimer]);

  const handleIncoming = useCallback(
    (raw: string) => {
      const envelope = parseEnvelope(raw);
      if (!envelope) {
        return;
      }

      if (envelope.type === 'connection_established') {
        setIsConnected(true);
        setIsReconnecting(false);
        return;
      }

      if (envelope.type === 'market_alert') {
        const payloadObject = (envelope.payload || {}) as Record<string, unknown>;
        const alert =
          (envelope.alert as Record<string, unknown> | undefined)
          || (payloadObject.alert as Record<string, unknown> | undefined)
          || payloadObject
          || {};
        const title = parseString(alert.title, 'Market alert');
        const message = parseString(alert.details, 'New market alert');
        const source = parseString(alert.source, 'System');
        const severity = normalizeSeverity(alert.severity);

        if (severity === 'error') {
          notifyError(`Market alert: ${title}`);
        } else if (severity === 'warning') {
          notifyInfo(`Market alert: ${title}`);
        } else {
          notifySuccess(`Market alert: ${title}`);
        }
        setNotifications((current) => [
          {
            id: `notification-${createNotificationId()}`,
            timestamp: clampDateString(envelope.ts),
            read: false,
            type: 'market_alert',
            title,
            message,
            source,
            severity,
          },
          ...current,
        ].slice(0, 50));
        return;
      }

      if (envelope.type === 'news_update') {
        const payloadObject = (envelope.payload || {}) as Record<string, unknown>;
        const news =
          (envelope.news as Record<string, unknown> | undefined)
          || (payloadObject.news as Record<string, unknown> | undefined)
          || payloadObject
          || {};
        const title = parseString(news.title, 'News update');
        const message = parseString(news.summary, 'New article update');
        const source = parseString(news.source, 'System');
        const url = parseString(news.url);

        notifyInfo(`News update: ${title}`);
        setNotifications((current) => [
          {
            id: `notification-${createNotificationId()}`,
            timestamp: clampDateString(envelope.ts),
            read: false,
            type: 'news_update',
            title,
            message,
            source,
            severity: 'info' as const,
            url,
          },
          ...current,
        ].slice(0, 50));
      }
    },
    [notifyError, notifyInfo, notifySuccess]
  );

  const connect = useCallback(() => {
    if (!mountedRef.current) {
      return;
    }

    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      return;
    }

    const websocketUrl = resolveWsUrl();
    if (!websocketUrl) {
      setIsConnected(false);
      notifyError('Notification endpoint not available.');
      return;
    }

    const socket = new WebSocket(websocketUrl);
    websocketRef.current = socket;

    socket.addEventListener('open', () => {
      reconnectAttemptRef.current = 0;
      setIsConnected(true);
      setIsReconnecting(false);
      notifySuccess('Connected to notification stream');
    });

    socket.addEventListener('message', (event) => {
      if (typeof event.data === 'string') {
        handleIncoming(event.data);
      }
    });

    socket.addEventListener('error', () => {
      setIsConnected(false);
      notifyError('Notification stream error.');
    });

    socket.addEventListener('close', () => {
      setIsConnected(false);
      setIsReconnecting(true);
      if (mountedRef.current) {
        notifyInfo('Notification stream disconnected; reconnecting...');
        scheduleReconnect();
      }
    });
  }, [handleIncoming, notifyError, notifyInfo, notifySuccess, resolveWsUrl, scheduleReconnect]);

  // Keep ref in sync so scheduleReconnect can call the latest version.
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const handleOpen = useCallback(() => {
    setIsOpen(true);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    // Defer to next tick to avoid synchronous setState within effect body.
    const timer = setTimeout(() => {
      if (mountedRef.current) {
        connect();
      }
    }, 0);

    return () => {
      mountedRef.current = false;
      clearTimeout(timer);
      clearReconnectTimer();
      closeSocket();
    };
  }, [clearReconnectTimer, closeSocket, connect]);

  const handleNotificationClick = (notification: Notification) => {
    setNotifications((current) =>
      current.map((entry) => (entry.id === notification.id ? { ...entry, read: true } : entry)),
    );

    if (notification.url) {
      void router.push(notification.url);
    }

    setIsOpen(false);
  };

  const handleClearAll = () => {
    setNotifications([]);
    setIsOpen(false);
  };

  const handleMarkAllRead = () => {
    setNotifications((current) => current.map((entry) => ({ ...entry, read: true })));
  };

  const renderSeverityIcon = (severity: Notification['severity']): React.JSX.Element => {
    switch (severity) {
      case 'success':
        return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-destructive" />;
      case 'warning':
        return <TriangleAlert className="h-4 w-4 text-amber-500" />;
      default:
        return <Info className="h-4 w-4 text-primary" />;
    }
  };

  const formatRelativeTime = (timestamp: string): string => {
    const now = new Date();
    const diff = Math.floor((now.getTime() - new Date(timestamp).getTime()) / 1000);

    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hrs ago`;
    return `${Math.floor(diff / 86400)} days ago`;
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={`Notifications (${unreadCount} unread)`}
          onClick={handleOpen}
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        className="w-[350px] max-w-[calc(100vw-2rem)] p-0"
        sideOffset={10}
      >
        <div className="flex items-center justify-between px-4 py-3">
          <h3 className="font-display text-lg font-semibold">Notifications</h3>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
                <span className="sr-only">Notification actions</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                disabled={unreadCount === 0}
                onSelect={() => handleMarkAllRead()}
              >
                <CheckCheck className="mr-2 h-4 w-4" />
                Mark all as read
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={notifications.length === 0}
                onSelect={() => handleClearAll()}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Clear all
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <Separator />

        {(isConnected || isReconnecting) && (
          <div className="px-4 py-2">
            {isConnected ? (
              <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700">
                Connected
              </Badge>
            ) : (
              <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-700">
                Reconnecting
              </Badge>
            )}
          </div>
        )}

        {notifications.length > 0 ? (
          <ScrollArea className="max-h-[min(65vh,460px)]">
            <ul className="py-1">
              {notifications.map((notification, index) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => handleNotificationClick(notification)}
                    className={cn(
                      'flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/70',
                      notification.read ? 'opacity-70' : 'bg-muted/30'
                    )}
                  >
                    <span className="mt-0.5 shrink-0">{renderSeverityIcon(notification.severity)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-foreground">
                        {notification.title}
                      </span>
                      <span className="mt-1 block line-clamp-2 text-sm text-muted-foreground">
                        {notification.message}
                      </span>
                      <span className="mt-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                        <span className="truncate">{notification.source || 'System'}</span>
                        <span className="shrink-0">{formatRelativeTime(notification.timestamp)}</span>
                      </span>
                    </span>
                  </button>
                  {index < notifications.length - 1 && <Separator />}
                </li>
              ))}
            </ul>
          </ScrollArea>
        ) : (
          <div className="flex flex-col items-center gap-2 px-4 py-10 text-center text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4" />
            <p>No notifications</p>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

export default NotificationCenter;
