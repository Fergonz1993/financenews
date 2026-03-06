import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import Layout from '../components/Layout';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Switch } from '../components/ui/switch';

type UserSettingsPayload = {
  darkMode: boolean;
  autoRefresh: boolean;
  refreshInterval: number;
  defaultFilters: {
    sources: string[];
    topics: string[];
    sentiment: string | null;
  };
  emailAlerts: {
    enabled: boolean;
    frequency: string;
    keywords: string[];
  };
  visualization: {
    chartType: string;
    colorScheme: string;
  };
};

type AlertRule = {
  id: string;
  source: string | null;
  sentiment: string | null;
  keywords: string[];
  enabled: boolean;
};

type UserAlertsPayload = {
  enabled: boolean;
  deliveryMode: string;
  rules: AlertRule[];
};

const defaultSettings: UserSettingsPayload = {
  darkMode: true,
  autoRefresh: false,
  refreshInterval: 5,
  defaultFilters: {
    sources: [],
    topics: [],
    sentiment: null,
  },
  emailAlerts: {
    enabled: false,
    frequency: 'daily',
    keywords: [],
  },
  visualization: {
    chartType: 'bar',
    colorScheme: 'default',
  },
};

const defaultAlerts: UserAlertsPayload = {
  enabled: false,
  deliveryMode: 'digest',
  rules: [],
};

const splitCsv = (value: string): string[] =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

const toCsv = (items: string[]): string => items.join(', ');

const createRuleId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID().slice(0, 12);
  }
  return `${Date.now()}${Math.random().toString(36).slice(2, 6)}`;
};

export default function SettingsPage(): React.JSX.Element {
  const [settings, setSettings] = useState<UserSettingsPayload>(defaultSettings);
  const [alerts, setAlerts] = useState<UserAlertsPayload>(defaultAlerts);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingAlerts, setSavingAlerts] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const primaryRule = useMemo<AlertRule>(() => {
    if (alerts.rules.length > 0) {
      return alerts.rules[0];
    }
    return {
      id: createRuleId(),
      source: null,
      sentiment: null,
      keywords: [],
      enabled: true,
    };
  }, [alerts.rules]);

  useEffect(() => {
    let cancelled = false;
    const loadData = async () => {
      try {
        const [settingsResp, alertsResp] = await Promise.all([
          axios.get<UserSettingsPayload>('/api/user/settings'),
          axios.get<UserAlertsPayload>('/api/user/alerts'),
        ]);
        if (!cancelled) {
          setSettings(settingsResp.data || defaultSettings);
          setAlerts(alertsResp.data || defaultAlerts);
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Failed to load settings/alerts', error);
          setStatusMessage('Failed to load remote preferences. Using local defaults.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void loadData();
    return () => {
      cancelled = true;
    };
  }, []);

  const saveSettings = async () => {
    setSavingSettings(true);
    setStatusMessage(null);
    try {
      const resp = await axios.put<UserSettingsPayload>('/api/user/settings', settings);
      setSettings(resp.data || settings);
      setStatusMessage('Settings saved.');
    } catch (error) {
      console.error('Failed to save settings', error);
      setStatusMessage('Failed to save settings.');
    } finally {
      setSavingSettings(false);
    }
  };

  const saveAlerts = async () => {
    setSavingAlerts(true);
    setStatusMessage(null);
    try {
      const payload: UserAlertsPayload = {
        ...alerts,
        rules: [primaryRule],
      };
      const resp = await axios.put<UserAlertsPayload>('/api/user/alerts', payload);
      setAlerts(resp.data || payload);
      setStatusMessage('Alert preferences saved.');
    } catch (error) {
      console.error('Failed to save alerts', error);
      setStatusMessage('Failed to save alert preferences.');
    } finally {
      setSavingAlerts(false);
    }
  };

  return (
    <Layout title="Settings" description="Application settings">
      <section className="space-y-2">
        <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
          Settings
        </h1>
        <p className="text-sm text-muted-foreground">
          Manage UI defaults, refresh behavior, and personal alerts.
        </p>
      </section>

      {statusMessage && (
        <p className="mt-4 rounded-md border border-border/70 bg-card/70 px-3 py-2 text-sm">
          {statusMessage}
        </p>
      )}

      <Card className="mt-6 border-border/70 bg-card/85 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Display & Feed Defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Dark mode</p>
              <p className="text-xs text-muted-foreground">Persist preferred theme for this user.</p>
            </div>
            <Switch
              checked={settings.darkMode}
              onCheckedChange={(checked) => setSettings((prev) => ({ ...prev, darkMode: checked }))}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Auto refresh feed</p>
              <p className="text-xs text-muted-foreground">Enable periodic feed refreshes.</p>
            </div>
            <Switch
              checked={settings.autoRefresh}
              onCheckedChange={(checked) =>
                setSettings((prev) => ({ ...prev, autoRefresh: checked }))
              }
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Refresh interval (seconds)</p>
            <Input
              type="number"
              min={1}
              max={3600}
              value={settings.refreshInterval}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  refreshInterval: Number(event.target.value || 5),
                }))
              }
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Default sources (comma separated)</p>
            <Input
              value={toCsv(settings.defaultFilters.sources)}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  defaultFilters: {
                    ...prev.defaultFilters,
                    sources: splitCsv(event.target.value),
                  },
                }))
              }
              placeholder="Reuters, CNBC"
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Default topics (comma separated)</p>
            <Input
              value={toCsv(settings.defaultFilters.topics)}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  defaultFilters: {
                    ...prev.defaultFilters,
                    topics: splitCsv(event.target.value),
                  },
                }))
              }
              placeholder="Markets, Earnings"
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Default sentiment filter</p>
            <Select
              value={settings.defaultFilters.sentiment || 'all'}
              onValueChange={(value) =>
                setSettings((prev) => ({
                  ...prev,
                  defaultFilters: {
                    ...prev.defaultFilters,
                    sentiment: value === 'all' ? null : value,
                  },
                }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All sentiment" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="positive">Positive</SelectItem>
                <SelectItem value="neutral">Neutral</SelectItem>
                <SelectItem value="negative">Negative</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Email alert frequency</p>
            <Select
              value={settings.emailAlerts.frequency}
              onValueChange={(value) =>
                setSettings((prev) => ({
                  ...prev,
                  emailAlerts: {
                    ...prev.emailAlerts,
                    frequency: value,
                  },
                }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select frequency" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="immediate">Immediate</SelectItem>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button type="button" onClick={() => void saveSettings()} disabled={savingSettings || loading}>
            {savingSettings ? 'Saving...' : 'Save Settings'}
          </Button>
        </CardContent>
      </Card>

      <Card className="mt-6 border-border/70 bg-card/85 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Alert Preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Enable custom alerts</p>
              <p className="text-xs text-muted-foreground">Create keyword/source/sentiment alerts.</p>
            </div>
            <Switch
              checked={alerts.enabled}
              onCheckedChange={(checked) => setAlerts((prev) => ({ ...prev, enabled: checked }))}
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Delivery mode</p>
            <Select
              value={alerts.deliveryMode}
              onValueChange={(value) => setAlerts((prev) => ({ ...prev, deliveryMode: value }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select delivery mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="immediate">Immediate</SelectItem>
                <SelectItem value="digest">Digest</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Alert source filter</p>
            <Input
              value={primaryRule.source || ''}
              onChange={(event) =>
                setAlerts((prev) => ({
                  ...prev,
                  rules: [
                    {
                      ...primaryRule,
                      source: event.target.value || null,
                    },
                  ],
                }))
              }
              placeholder="Optional source key"
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Alert sentiment filter</p>
            <Select
              value={primaryRule.sentiment || 'all'}
              onValueChange={(value) =>
                setAlerts((prev) => ({
                  ...prev,
                  rules: [
                    {
                      ...primaryRule,
                      sentiment: value === 'all' ? null : value,
                    },
                  ],
                }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="All sentiment" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="positive">Positive</SelectItem>
                <SelectItem value="neutral">Neutral</SelectItem>
                <SelectItem value="negative">Negative</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Alert keywords (comma separated)</p>
            <Input
              value={toCsv(primaryRule.keywords)}
              onChange={(event) =>
                setAlerts((prev) => ({
                  ...prev,
                  rules: [
                    {
                      ...primaryRule,
                      keywords: splitCsv(event.target.value),
                    },
                  ],
                }))
              }
              placeholder="inflation, earnings, fed"
            />
          </div>

          <Button type="button" onClick={() => void saveAlerts()} disabled={savingAlerts || loading}>
            {savingAlerts ? 'Saving...' : 'Save Alert Preferences'}
          </Button>
        </CardContent>
      </Card>
    </Layout>
  );
}
