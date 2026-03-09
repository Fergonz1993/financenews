import { Article } from '../models/Article';
import { NewsSource } from '../models/NewsSource';

class CrawlerManager {
  private articles: Article[] = [
    {
      id: 'article-1',
      title: 'Markets gain momentum after strong earnings season',
      url: 'https://example.com/article-1',
      source: 'Reuters',
      sourceId: 'reuters',
      published_at: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
      content:
        'Analysts reported strong earnings across major technology names, leading to an improved sentiment outlook for equities.',
      summarized_headline: 'Technology earnings boosted a constructive market view.',
      summary_bullets: [
        'Large-cap tech posted stronger-than-expected margins',
        'Analysts revised forward guidance upward',
        'Sentiment scores improved across sectors',
      ],
      sentiment: 'positive',
      sentiment_score: 0.84,
      market_impact_score: 0.78,
      key_entities: ['AAPL', 'MSFT', 'NVDA'],
      topics: ['technology', 'earnings', 'markets'],
      crawled_at: new Date().toISOString(),
      hash: 'hash-article-1',
      is_saved: false,
    },
    {
      id: 'article-2',
      title: 'Inflation data keeps investors cautious',
      url: 'https://example.com/article-2',
      source: 'Bloomberg',
      sourceId: 'bloomberg',
      published_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      content:
        'Recent inflation readings remained elevated, increasing the probability of a tighter policy stance.',
      summarized_headline: 'Sticky inflation keeps central bank expectations tight.',
      summary_bullets: [
        'Core inflation surprised on the upside',
        'Housing and labor inputs remain pressured',
      ],
      sentiment: 'negative',
      sentiment_score: -0.48,
      market_impact_score: 0.65,
      key_entities: ['CPI', 'Fed', 'rates'],
      topics: ['economy', 'policy', 'macro'],
      crawled_at: new Date().toISOString(),
      hash: 'hash-article-2',
      is_saved: false,
    },
    {
      id: 'article-3',
      title: 'Energy transition receives new policy support',
      url: 'https://example.com/article-3',
      source: 'Wall Street Journal',
      sourceId: 'wall-street-journal',
      published_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
      content:
        'New policy proposals are likely to increase incentives for renewable deployment in the coming years.',
      summarized_headline: 'Policy changes could accelerate clean energy investments.',
      summary_bullets: [
        'New credit mechanisms target long-term grid upgrades',
        'Regional utilities report expanded procurement plans',
      ],
      sentiment: 'neutral',
      sentiment_score: 0.12,
      market_impact_score: 0.42,
      key_entities: ['utilities', 'renewables', 'policy'],
      topics: ['policy', 'markets'],
      crawled_at: new Date().toISOString(),
      hash: 'hash-article-3',
      is_saved: true,
    },
  ];

  private sources: NewsSource[] = [
    {
      id: 'reuters',
      name: 'Reuters',
      url: 'https://www.reuters.com',
      type: 'api',
      category: 'markets',
      crawlFrequency: 30,
      isActive: true,
      useProxy: false,
      respectRobotsTxt: true,
    },
    {
      id: 'bloomberg',
      name: 'Bloomberg',
      url: 'https://www.bloomberg.com',
      type: 'api',
      category: 'finance',
      crawlFrequency: 45,
      isActive: true,
      useProxy: false,
      respectRobotsTxt: true,
    },
  ];

  getArticles(): Promise<Article[]> {
    return Promise.resolve(this.articles);
  }

  async runCrawlers(): Promise<number> {
    return this.articles.length;
  }

  getSources(): NewsSource[] {
    return this.sources;
  }

  findSourcesDueCrawling(): NewsSource[] {
    return this.sources.filter((source) => source.isActive);
  }

  addOrUpdateSource(sourceData: NewsSource): NewsSource {
    const existingIndex = this.sources.findIndex((source) => source.id === sourceData.id);
    if (existingIndex >= 0) {
      this.sources[existingIndex] = { ...this.sources[existingIndex], ...sourceData };
      return this.sources[existingIndex];
    }

    const source = { ...sourceData };
    this.sources.push(source);
    return source;
  }

  removeSource(id: string): boolean {
    const lengthBefore = this.sources.length;
    this.sources = this.sources.filter((source) => source.id !== id);
    return this.sources.length < lengthBefore;
  }
}

export const crawlerManager = new CrawlerManager();
