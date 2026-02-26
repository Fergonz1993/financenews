import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';

export default function SavedArticlesPage(): React.JSX.Element {
  return (
    <Layout title="Saved Articles" description="Articles saved for later reading">
      <section className="space-y-2">
        <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
          Saved Articles
        </h1>
      </section>

      <Card className="mt-6 border-border/70 bg-card/85 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Saved Articles</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground sm:text-base">
            Saved-articles support will appear here once user accounts are enabled.
          </p>
        </CardContent>
      </Card>
    </Layout>
  );
}
