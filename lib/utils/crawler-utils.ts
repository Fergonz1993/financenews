export const logCrawlerActivity = (message: string) => {
  if (process.env.NODE_ENV !== 'production') {
    console.log(`[crawler-utils] ${message}`);
  }
};
