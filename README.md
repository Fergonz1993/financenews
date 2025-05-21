# Financial News Summarizer Agent

A powerful command-line tool that fetches financial news based on your interests, uses AI to summarize it concisely, and delivers the insights through multiple channels.

## Features

- Fetch relevant financial news based on stock tickers, keywords, or custom queries
- AI-powered summarization with OpenAI (GPT-3.5 or GPT-4o)
- Pretty-printed console output with color highlighting
- Automatic markdown report generation 
- Optional email delivery
- Asynchronous processing for speed and efficiency
- Rate-limiting to respect API quotas

## Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/financial-news-summarizer.git
   cd financial-news-summarizer
   ```

2. **Set up a Python virtual environment**

   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up your API keys**

   Create a `.env` file in the root directory with the following content:

   ```
   OPENAI_API_KEY=your_openai_api_key
   NEWS_API_KEY=your_newsapi_key
   
   # Optional email configuration
   EMAIL_TO=recipient@example.com
   EMAIL_FROM=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   EMAIL_SERVER=smtp.gmail.com
   EMAIL_PORT=587
   ```

   > Note: For Gmail, you'll need to use an "App Password" rather than your regular password. 
   > See [Google Account Help](https://support.google.com/accounts/answer/185833) for details.

5. **Run the tool**

   ```bash
   # With specific queries
   python news_summarizer.py -q AAPL MSFT "artificial intelligence" "federal reserve"
   
   # With a YAML config file
   python news_summarizer.py -c config.yaml
   
   # Limit the number of articles
   python news_summarizer.py -q AAPL MSFT -m 10
   
   # Use a different OpenAI model
   python news_summarizer.py -q AAPL -m 5 --model gpt-4o
   ```

## API Keys

### OpenAI API Key
1. Go to [OpenAI's platform](https://platform.openai.com/signup)
2. Create an account or log in
3. Navigate to the API section
4. Create a new API key
5. Copy the key to your `.env` file

### NewsAPI Key
1. Go to [NewsAPI.org](https://newsapi.org/register)
2. Register for a free account
3. Copy your API key from the dashboard
4. Add it to your `.env` file

## Example Config File (config.yaml)

```yaml
# List of stock tickers, keywords, or topics to track
queries:
  - AAPL
  - MSFT
  - GOOGL
  - "artificial intelligence"
  - "federal reserve"
  - "interest rates"
  - "stock market"
```

## Performance Tips

- Limit the number of articles (`-m` flag) to 10-20 for faster results
- Use `gpt-3.5-turbo` for faster (though less detailed) summaries
- Run on a schedule (e.g., morning and evening) rather than on-demand
- Consider using a dedicated email account for programmatic sending

## Next Feature Ideas

### Immediate Improvements
- Slack/Discord webhook integration
- Web UI for easier configuration and viewing
- Multiple output formats (JSON, HTML, PDF)
- Support for additional news sources
- Custom templates for summary format

### Advanced Extensions
- Set up as a daily cron job for automatic briefings
- Store articles in a vector database for similarity search
- Add sentiment analysis for market mood tracking
- Portfolio-specific relevance scoring
- LangChain agent refactor for more complex reasoning
- Custom fine-tuned financial summarization model

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
