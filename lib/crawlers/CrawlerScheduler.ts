import { crawlerManager } from './CrawlerManager';

class CrawlerScheduler {
  start() {
    crawlerManager.getSources();
    return { status: 'started' };
  }

  stop() {
    return { status: 'stopped' };
  }

  async runImmediately(): Promise<number> {
    await crawlerManager.runCrawlers();
    const articles = await crawlerManager.getArticles();
    return articles.length;
  }
}

export const crawlerScheduler = new CrawlerScheduler();
