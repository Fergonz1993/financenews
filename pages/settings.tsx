import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';

export default function SettingsPage(): React.JSX.Element {
  return (
    <Layout title="Settings" description="Application settings">
      <section className="space-y-2">
        <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
          Settings
        </h1>
      </section>

      <Card className="mt-6 border-border/70 bg-card/85 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground sm:text-base">
            User settings and preference controls will be added in the next iteration.
          </p>
        </CardContent>
      </Card>
    </Layout>
  );
}
