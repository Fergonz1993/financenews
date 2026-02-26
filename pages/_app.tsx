import { useState, useEffect, useCallback, useMemo } from 'react';
import { Newsreader, Public_Sans } from 'next/font/google';
import type { AppProps } from 'next/app';
import '../styles/globals.css';

import { initCrawlerSystem } from '../lib/crawler-init';
import { NotificationContext } from '../lib/notification-context';

const bodyFont = Public_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '600', '700'],
  display: 'swap',
});

const displayFont = Newsreader({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['500', '600', '700'],
  display: 'swap',
});

function MyApp({ Component, pageProps }: AppProps): React.JSX.Element {
  const getPreferredDarkMode = (): boolean => {
    if (typeof window === 'undefined') {
      return false;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  };

  const [darkMode, setDarkMode] = useState<boolean>(getPreferredDarkMode);

  const notifyInfo = useCallback((message: string) => {
    console.log('INFO:', message);
  }, []);

  const notifySuccess = useCallback((message: string) => {
    console.log('SUCCESS:', message);
  }, []);

  const notifyError = useCallback((message: string) => {
    console.log('ERROR:', message);
  }, []);

  const notifyWarning = useCallback((message: string) => {
    console.log('WARNING:', message);
  }, []);

  const notificationValue = useMemo(
    () => ({
      notifyInfo,
      notifySuccess,
      notifyError,
      notifyWarning,
    }),
    [notifyInfo, notifySuccess, notifyError, notifyWarning]
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleColorSchemeChange = (event: MediaQueryListEvent) => {
      setDarkMode(event.matches);
    };

    if (process.env.NODE_ENV === 'production') {
      try {
        initCrawlerSystem();
        console.log('Crawler system initialized');
      } catch (error) {
        console.error('Failed to initialize crawler system:', error);
      }
    }

    mediaQuery.addEventListener('change', handleColorSchemeChange);
    return () => mediaQuery.removeEventListener('change', handleColorSchemeChange);
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    document.documentElement.classList.toggle('dark', darkMode);
  }, [darkMode]);

  return (
    <div className={`${bodyFont.className} ${bodyFont.variable} ${displayFont.variable}`}>
      <NotificationContext.Provider value={notificationValue}>
        <Component {...pageProps} />
      </NotificationContext.Provider>
    </div>
  );
}

export default MyApp;
