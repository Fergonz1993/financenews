import type { ReactNode } from 'react';
import Head from 'next/head';
import Navigation from './Navigation';

interface LayoutProps {
  children: ReactNode;
  title?: string;
  description?: string;
}

const Layout = ({
  children,
  title = 'Financial News Platform',
  description = 'Real-time financial news analysis with AI',
}: LayoutProps): React.JSX.Element => {
  return (
    <>
      <Head>
        <title>{title}</title>
        <meta name="description" content={description} />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="relative flex min-h-screen flex-col overflow-x-clip">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-grid-subtle opacity-50" />
        <Navigation />

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-12 pt-8 sm:px-6 lg:px-8">
          {children}
        </main>

        <footer className="border-t border-border/60 bg-background/70 px-4 py-6 backdrop-blur-sm sm:px-6">
          <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
            <p>© {new Date().getFullYear()} Financial News Platform.</p>
            <p>Built for real-time market intelligence.</p>
          </div>
        </footer>
      </div>
    </>
  );
};

export default Layout;
