import crypto from 'crypto';
import robotsParser from 'robots-parser';
import fetch from 'node-fetch';
import { Article } from '../../../types';

/**
 * Generate a unique hash for an article to help with deduplication
 */
export const generateArticleHash = (title: string, content: string): string => {
  const data = `${title}${content.substring(0, 200)}`;
  return crypto.createHash('md5').update(data).digest('hex');
};

/**
 * Check if a URL is allowed by robots.txt
 */
export async function checkRobotsTxt(url: string, userAgent: string): Promise<boolean> {
  try {
    const urlObj = new URL(url);
    const robotsUrl = `${urlObj.protocol}//${urlObj.hostname}/robots.txt`;
    
    const response = await fetch(robotsUrl);
    if (!response.ok) return true; // If robots.txt doesn't exist or can't be fetched, assume allowed
    
    const robotsTxt = await response.text();
    const robots = robotsParser(robotsUrl, robotsTxt);
    
    return robots.isAllowed(url, userAgent);
  } catch (error) {
    console.error('Error checking robots.txt:', error);
    return true; // Default to allowed in case of error
  }
}

/**
 * Clean HTML content by removing scripts, styles, and excessive whitespace
 */
export function cleanHtml(html: string): string {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Extract text content from HTML
 */
export function extractTextFromHtml(html: string): string {
  return cleanHtml(html)
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Create a delay function for polite crawling
 */
export const delay = (ms: number): Promise<void> => 
  new Promise(resolve => setTimeout(resolve, ms));

/**
 * Get a random user agent from a list
 */
export const getRandomUserAgent = (): string => {
  const userAgents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'FinanceNewsBot/1.0 (https://financenews.example.com/bot.html)'
  ];
  
  return userAgents[Math.floor(Math.random() * userAgents.length)];
};

/**
 * Log crawler activity with timestamps
 */
export const logCrawlerActivity = (message: string, level: 'info' | 'error' | 'warn' = 'info'): void => {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] [CRAWLER] [${level.toUpperCase()}] ${message}`;
  
  switch(level) {
    case 'error':
      console.error(logMessage);
      break;
    case 'warn':
      console.warn(logMessage);
      break;
    default:
      console.log(logMessage);
  }
};
