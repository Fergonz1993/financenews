import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  Activity,
  BarChart3,
  Bookmark,
  LayoutDashboard,
  LogOut,
  Menu,
  Newspaper,
  Settings,
  X,
  type LucideIcon,
} from 'lucide-react';
import NotificationCenter from './NotificationCenter';
import { Button } from './ui/button';
import { cn } from '@/lib/utils';

type NavItem = {
  text: string;
  icon: LucideIcon;
  path: string;
};

const navItems: NavItem[] = [
  { text: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { text: 'Articles', icon: Newspaper, path: '/articles' },
  { text: 'Analytics', icon: BarChart3, path: '/analytics' },
  { text: 'Ingest', icon: Activity, path: '/admin/ingest' },
  { text: 'Saved', icon: Bookmark, path: '/saved' },
  { text: 'Settings', icon: Settings, path: '/settings' },
];

const Navigation = (): React.JSX.Element => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const router = useRouter();

  const isPathActive = (path: string): boolean => {
    if (path === '/') {
      return router.pathname === '/';
    }

    return router.pathname === path || router.pathname.startsWith(`${path}/`);
  };

  useEffect(() => {
    const closeDrawer = () => {
      setDrawerOpen(false);
    };

    router.events.on('routeChangeStart', closeDrawer);
    return () => {
      router.events.off('routeChangeStart', closeDrawer);
    };
  }, [router.events]);

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-3 px-4 sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </Button>

          <Link href="/" className="group flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-primary to-secondary text-primary-foreground shadow-md shadow-primary/30 transition-transform duration-200 group-hover:scale-105">
              <BarChart3 className="h-4 w-4" />
            </span>
            <span className="font-display text-base font-semibold tracking-tight sm:text-lg">
              Market Signal Desk
            </span>
          </Link>

          <nav className="ml-3 hidden items-center gap-1 md:flex">
            {navItems.map((item) => {
              const active = isPathActive(item.path);
              const Icon = item.icon;

              return (
                <Link
                  key={item.text}
                  href={item.path}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    active
                      ? 'bg-primary/12 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  )}
                  aria-current={active ? 'page' : undefined}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.text}</span>
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-1 text-foreground">
            <NotificationCenter />
            <Button
              variant="outline"
              size="sm"
              className="hidden items-center gap-1.5 border-border/80 lg:inline-flex"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/45"
            aria-label="Close menu backdrop"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="absolute left-0 top-0 h-full w-80 border-r border-border/70 bg-background p-4 shadow-2xl shadow-black/30">
            <div className="mb-5 flex items-center justify-between">
              <p className="font-display text-lg font-semibold">Navigation</p>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setDrawerOpen(false)}
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>

            <nav className="space-y-1">
              {navItems.map((item) => {
                const active = isPathActive(item.path);
                const Icon = item.icon;

                return (
                  <Link
                    key={item.text}
                    href={item.path}
                    className={cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                      active
                        ? 'bg-primary/12 text-primary'
                        : 'text-foreground/85 hover:bg-accent hover:text-accent-foreground'
                    )}
                    aria-current={active ? 'page' : undefined}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.text}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="mt-6 border-t border-border/70 pt-4">
              <Button variant="outline" className="w-full justify-start gap-2">
                <LogOut className="h-4 w-4" />
                Logout
              </Button>
            </div>
          </aside>
        </div>
      )}
    </>
  );
};

export default Navigation;
