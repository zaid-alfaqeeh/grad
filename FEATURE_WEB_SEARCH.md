# Web Search and Data Extraction Feature

## The Core Function

This is what makes the system actually useful. When we don't have cached data, or when we need fresh information, this feature searches for answers using ChatGPT's knowledge about the university.

## How It Works

Instead of scraping websites (which is messy and breaks often), we use ChatGPT's built-in knowledge. We give it a query about the university, and it searches its training data to find relevant information.

The process is:
1. We send the query to ChatGPT with context about JUST University
2. ChatGPT searches its knowledge and extracts relevant information
3. We structure the response into a clean JSON format
4. We use that structured data to generate a detailed answer

## Why This Approach

We tried web scraping at first, but it was a nightmare:
- Websites change their structure constantly
- We had to maintain parsers for each page
- It broke all the time
- Some pages required authentication

Using ChatGPT's knowledge is way better because:
- It's always up to date (within its training window)
- We don't need to maintain scrapers
- It understands context and can extract relevant info
- It works even if the website structure changes

## Resource URLs

We also have a `resources.json` file with helpful URLs. When we're searching, we can pass these URLs to ChatGPT as context. It's like saying "here are some relevant pages, use them for context."

ChatGPT doesn't actually visit these URLs, but it uses them to understand what we're looking for. It's helpful for pointing it in the right direction.

## Data Extraction

Once ChatGPT finds information, we extract it into a structured format. We look for:
- Titles and summaries
- Requirements lists
- Fees and costs
- Deadlines and dates
- Step-by-step processes
- Contact information

We store this as JSON, which makes it easy to work with and cache.

## Handling Failures

Sometimes ChatGPT can't find information, or the extraction fails. In those cases:
- We still try to generate a helpful answer
- We might use fallback data
- We log the issue for debugging
- We don't leave the user hanging

## The Prompt Engineering

We spent a lot of time crafting prompts that work well. The prompts:
- Give ChatGPT context about JUST University
- Specify what information we're looking for
- Ask for structured output
- Include examples of good responses

This ensures we get consistent, useful results.

## Limitations

ChatGPT's knowledge has a cutoff date, so it might not know about very recent changes. For that, we'd need to use web scraping or real-time APIs, but for most university information, ChatGPT's knowledge is sufficient.

Also, we can't guarantee 100% accuracy since we're relying on ChatGPT's understanding. But in practice, it's been very reliable.

## Why This Matters

Without this feature, the system would only work for questions we've seen before. With web search, we can answer almost any question about the university, even if it's the first time we've seen it. That's what makes the system truly useful.
