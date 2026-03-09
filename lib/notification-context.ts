import { createContext, useContext } from 'react';

type NotificationType = {
  notifyInfo: (message: string) => void;
  notifySuccess: (message: string) => void;
  notifyError: (message: string) => void;
  notifyWarning: (message: string) => void;
};

export const NotificationContext = createContext<NotificationType>({
  notifyInfo: () => {},
  notifySuccess: () => {},
  notifyError: () => {},
  notifyWarning: () => {},
});

export const useNotification = () => useContext(NotificationContext);

export { NotificationContext as default };
