import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

type NotificationType = 'info' | 'success' | 'error' | 'warning';

type Notification = {
  id: number;
  message: string;
  type: NotificationType;
  open: boolean;
};

type NotificationContextType = {
  notifyInfo: (message: string) => void;
  notifySuccess: (message: string) => void;
  notifyError: (message: string) => void;
  notifyWarning: (message: string) => void;
};

const NotificationContext = createContext<NotificationContextType>({
  notifyInfo: () => {},
  notifySuccess: () => {},
  notifyError: () => {},
  notifyWarning: () => {},
});

export const useNotification = (): NotificationContextType => useContext(NotificationContext);

type NotificationProviderProps = {
  children: ReactNode;
};

const notificationStyles: Record<NotificationType, string> = {
  info: 'border-primary/30 bg-primary/10 text-foreground',
  success: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
  error: 'border-destructive/40 bg-destructive/10 text-destructive',
  warning: 'border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200',
};

export const NotificationProvider = ({ children }: NotificationProviderProps): React.JSX.Element => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const nextIdRef = useRef(0);

  const closeNotification = useCallback((id: number) => {
    setNotifications((prev) =>
      prev.map((notification) =>
        notification.id === id ? { ...notification, open: false } : notification
      )
    );

    setTimeout(() => {
      setNotifications((prev) => prev.filter((notification) => notification.id !== id));
    }, 250);
  }, []);

  const addNotification = useCallback(
    (message: string, type: NotificationType) => {
      const id = nextIdRef.current++;
      setNotifications((prev) => [...prev, { id, message, type, open: true }]);

      setTimeout(() => {
        closeNotification(id);
      }, 5000);
    },
    [closeNotification]
  );

  const notifyInfo = useCallback((message: string) => addNotification(message, 'info'), [addNotification]);
  const notifySuccess = useCallback((message: string) => addNotification(message, 'success'), [addNotification]);
  const notifyError = useCallback((message: string) => addNotification(message, 'error'), [addNotification]);
  const notifyWarning = useCallback((message: string) => addNotification(message, 'warning'), [addNotification]);

  return (
    <NotificationContext.Provider value={{ notifyInfo, notifySuccess, notifyError, notifyWarning }}>
      {children}

      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2">
        {notifications.map((notification) => (
          <div
            key={notification.id}
            role="status"
            className={cn(
              'pointer-events-auto rounded-md border px-3 py-2 text-sm shadow-md transition-opacity duration-200',
              notificationStyles[notification.type],
              notification.open ? 'opacity-100' : 'opacity-0'
            )}
          >
            <p>{notification.message}</p>
          </div>
        ))}
      </div>
    </NotificationContext.Provider>
  );
};
