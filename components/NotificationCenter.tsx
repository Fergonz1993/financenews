import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
import { io, type Socket as SocketClient } from 'socket.io-client';
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
  timestamp: Date;
  read: boolean;
  type: string;
  title: string;
  message: string;
  source?: string;
  severity: 'success' | 'error' | 'warning' | 'info';
  url?: string;
};

const SOCKET_PATH = '/api/ws';
const resolveSocketBaseUrl = (value: string): string => {
  try {
    const parsed = new URL(value);
    return parsed.origin;
  } catch {
    return value;
  }
};

type MarketAlertPayload = {
  type: 'market_alert';
  alert: {
    title: string;
    details: string;
    source?: string;
    severity: Notification['severity'];
  };
};

type NewsUpdatePayload = {
  type: 'news_update';
  news: {
    title: string;
    summary: string;
    source?: string;
    url?: string;
  };
};

type ConnectionEstablishedPayload = { type: 'connection_established' };
type UnknownPayload = {
  type: Exclude<string, 'market_alert' | 'news_update' | 'connection_established'>;
};
type NotificationPayload =
  | MarketAlertPayload
  | NewsUpdatePayload
  | ConnectionEstablishedPayload
  | UnknownPayload;

const createNotificationId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
};

const parsePayload = (raw: unknown): NotificationPayload | null => {
  if (!raw) {
    return null;
  }

  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' && 'type' in parsed
        ? (parsed as NotificationPayload)
        : null;
    } catch (error) {
      console.error('Error parsing notification message:', error);
      return null;
    }
  }

  if (typeof raw === 'object' && 'type' in raw) {
    return raw as NotificationPayload;
  }

  return null;
};

const NotificationCenter = (): React.JSX.Element => {
  const router = useRouter();
  const { notifyInfo, notifyError, notifySuccess, notifyWarning } = useNotification();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const unreadCount = useMemo(
    () => notifications.reduce((count, notification) => count + (notification.read ? 0 : 1), 0),
    [notifications]
  );

  const handleNewNotification = useCallback(
    (data: NotificationPayload) => {
      if (data.type === 'connection_established') {
        return;
      }

      if (data.type === 'market_alert') {
        const { alert } = data as MarketAlertPayload;
        const newNotification: Notification = {
          id: `notification-${createNotificationId()}`,
          timestamp: new Date(),
          read: false,
          type: 'market_alert',
          title: alert.title,
          message: alert.details,
          source: alert.source,
          severity: alert.severity,
        };

        switch (alert.severity) {
          case 'success':
            notifySuccess(alert.title);
            break;
          case 'error':
            notifyError(alert.title);
            break;
          case 'warning':
            notifyWarning(alert.title);
            break;
          default:
            notifyInfo(alert.title);
        }

        setNotifications((prev) => [newNotification, ...prev].slice(0, 50));
        return;
      }

      if (data.type === 'news_update') {
        const { news } = data as NewsUpdatePayload;
        const newNotification: Notification = {
          id: `notification-${createNotificationId()}`,
          timestamp: new Date(),
          read: false,
          type: 'news_update',
          title: news.title,
          message: news.summary,
          source: news.source,
          url: news.url,
          severity: 'info',
        };

        setNotifications((prev) => [newNotification, ...prev].slice(0, 50));
        notifyInfo(`New: ${news.title}`);
      }
    },
    [notifySuccess, notifyError, notifyWarning, notifyInfo]
  );

  const handleOpen = useCallback(() => {
    setIsConnected(true);
    notifySuccess('Connected to notification service');
  }, [notifySuccess]);

  const handleMessage = useCallback(
    (eventData: unknown) => {
      const data = parsePayload(eventData);
      if (!data) {
        return;
      }
      handleNewNotification(data);
    },
    [handleNewNotification]
  );

  const handleError = useCallback(
    (error: unknown) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
      notifyError('Connection to notification service failed');
    },
    [notifyError]
  );

  const handleDisconnected = useCallback(() => {
    setIsConnected(false);
    notifyInfo('Disconnected from notification service');
  }, [notifyInfo]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    let active = true;
    let socket: SocketClient | null = null;

    const connectSocket = async () => {
      try {
        // Ensure the Next.js API route initializes Socket.IO on the server.
        await fetch('/api/ws');
      } catch (error) {
        console.error('Failed to initialize websocket endpoint:', error);
      }

      if (!active) {
        return;
      }

      const baseUrl = process.env.NEXT_PUBLIC_WS_URL
        ? resolveSocketBaseUrl(process.env.NEXT_PUBLIC_WS_URL)
        : window.location.origin;
      socket = io(baseUrl, {
        path: SOCKET_PATH,
        autoConnect: false,
        transports: ['websocket', 'polling'],
      });

      socket.on('connect', handleOpen);
      socket.on('message', handleMessage);
      socket.on('connect_error', handleError);
      socket.on('disconnect', handleDisconnected);
      socket.io.on('error', handleError);
      socket.connect();
    };

    void connectSocket();

    return () => {
      active = false;
      if (!socket) {
        return;
      }
      socket.off('connect', handleOpen);
      socket.off('message', handleMessage);
      socket.off('connect_error', handleError);
      socket.off('disconnect', handleDisconnected);
      socket.io.off('error', handleError);
      socket.disconnect();
    };
  }, [handleOpen, handleMessage, handleError, handleDisconnected]);

  const handleNotificationClick = (notification: Notification) => {
    setNotifications((prev) =>
      prev.map((entry) => (entry.id === notification.id ? { ...entry, read: true } : entry))
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
    setNotifications((prev) => prev.map((entry) => ({ ...entry, read: true })));
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

  const formatRelativeTime = (timestamp: Date): string => {
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

        {isConnected && (
          <div className="px-4 py-2">
            <Badge
              variant="outline"
              className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
            >
              Connected
            </Badge>
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
