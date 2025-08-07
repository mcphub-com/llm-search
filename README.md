# 🚀 Tool Overview

This is an MCP server that exposes a single powerful web search tool: llm_search. It enables advanced internet searches with optional content crawling to retrieve full-page content in markdown format.

## ✨ Features

🔎 Full support for Google-style search operators (e.g., inurl:, site:, intitle:)

🌍 Location-specific search simulation

📄 Optional full-page crawling for markdown-formatted content

## 🛠️ Tool Parameters

query: The search query string. You can use typical Google search syntax like site:, inurl:, or intitle:. Supports advanced filters like as_dt, as_eq, etc.

location: Simulate a search from a specific geographic location (preferably at the city level).

start: Number of results to skip (used for pagination). 0 is the first page, 10 is the second, etc.

crawl: If true, crawls the linked pages and returns content in markdown. Adds latency and may skip pages that timeout.

## 📦 Response Format

```json
{
  "answer_box": { ... },
  "organic_results": [
    {
      "title": "...",
      "link": "...",
      "snippet": "...",
      "text_content": "..." // if crawl = true
    },
    ...
  ]
}
```