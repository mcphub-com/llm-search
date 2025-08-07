import json
import logging
import os
import signal
from typing import Union, Annotated, Literal

import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import html2text
from pydantic import Field
import requests

from util.crawler.dynamic_crawler import DynamicCrawlerPool
from mcp.server import FastMCP


load_dotenv()

mcp = FastMCP('llm-search')

serp_url = "https://serpapi.com/search"
serp_api_key = os.getenv("SERP_API_KEY")
crawler_pool = DynamicCrawlerPool(headless=True, mobile=False, EXECUTOR_TIMEOUT=60, run_js=True, use_proxy=False, max_crawlers=20)

@mcp.tool()
async def llm_search(
    query: Annotated[str, Field(
        description="The search query. You can use anything that you would use in a regular Google search. e.g. inurl:, site:, intitle:. We also support advanced search query parameters such as as_dt and as_eq.")],
    location: Annotated[Union[str, None], Field(description="Parameter defines from where you want the search to originate. If several locations match the location requested, we'll pick the most popular one. It is recommended to specify location at the city level in order to simulate a real user's search.")] = None,
    start: Annotated[Union[int, None], Field(
        description="Parameter defines the result offset. It skips the given number of results. It's used for pagination. (e.g., 0 (default) is the first page of results, 10 is the 2nd page of results, 20 is the 3rd page of results, etc.).")] = None,
    crawl: Annotated[Union[bool, None], Field(
        description="Parameter defines whether to crawl the search result page contents. If false (default), only the title, URL, and description will be returned like a search engine result page. If true, then the pages' contents will also be returned in markdown format. Enabling this option will add latency, and not all pages may be crawled successfully due to a timeout.")] = None,
):
    """Get web search results with the choice of a simple result list or full text content."""
    search_result = await search_light(query, location=location, start=start)
    if crawl:
        crawl_all(search_result["organic_results"], total_time=8)
    
    search_result = {k: v for k, v in search_result.items() if k in ("answer_box", "organic_results")}
    
    return search_result

async def search_light(
    q: Annotated[str, Field(
        description="Parameter defines the query you want to search. You can use anything that you would use in a regular Google search. e.g. inurl:, site:, intitle:. We also support advanced search query parameters such as as_dt and as_eq. See the full list of supported advanced search query parameters.")],
    location: Annotated[Union[str, None], Field(description="Parameter defines from where you want the search to originate. If several locations match the location requested, we'll pick the most popular one. Head to the /locations.json API if you need more precise control. The location and uule parameters can't be used together. It is recommended to specify location at the city level in order to simulate a real user’s search. If location is omitted, the search may take on the location of the proxy.")] = None,
    safe: Annotated[Union[Literal["active", "off"], None], Field(
        description="Parameter defines the level of filtering for adult content. It can be set to active or off, by default Google will blur explicit content.")] = None,
    nfpr: Annotated[Union[Literal[0, 1], None], Field(
        description="Parameter defines the exclusion of results from an auto-corrected query when the original query is spelled wrong. It can be set to 1 to exclude these results, or 0 to include them (default). Note that this parameter may not prevent Google from returning results for an auto-corrected query if no other results are available.")] = None,
    filter: Annotated[Union[Literal[0, 1], None], Field(
        description="Parameter defines if the filters for 'Similar Results' and 'Omitted Results' are on or off. It can be set to 1 (default) to enable these filters, or 0 to disable these filters.")] = None,
    start: Annotated[Union[int, None], Field(
        description="Parameter defines the result offset. It skips the given number of results. It's used for pagination. (e.g., 0 (default) is the first page of results, 10 is the 2nd page of results, 20 is the 3rd page of results, etc.).")] = None,
    num: Annotated[Union[int, None], Field(
        description="Parameter defines the maximum number of results to return. (e.g., 10 (default) returns 10 results, 40 returns 40 results, and 100 returns 100 results). The use of num may introduce latency, and/or prevent the inclusion of specialized result types. It is better to omit this parameter unless it is strictly necessary to increase the number of results per page.")] = None,
    device: Annotated[Union[Literal["desktop", "tablet", "mobile"], None], Field(
        description="Parameter defines the device to use to get the results. It can be set to desktop (default) to use a regular browser, tablet to use a tablet browser (currently using iPads), or mobile to use a mobile browser (currently using iPhones).")] = None,
    no_cache: Annotated[Union[bool, None], Field(
        description="Parameter will force SerpApi to fetch the Google Light results even if a cached version is already present. A cache is served only if the query and all parameters are exactly the same. Cache expires after 1h. Cached searches are free, and are not counted towards your searches per month. It can be set to false (default) to allow results from the cache, or true to disallow results from the cache. no_cache and async parameters should not be used together.")] = None,
    aasync: Annotated[Union[bool, None], Field(
        description="Parameter defines the way you want to submit your search to SerpApi. It can be set to false (default) to open an HTTP connection and keep it open until you got your search results, or true to just submit your search to SerpApi and retrieve them later. In this case, you'll need to use our Searches Archive API to retrieve your results. async and no_cache parameters should not be used together. async should not be used on accounts with Ludicrous Speed enabled.")] = None,
    zero_trace: Annotated[Union[bool, None], Field(
        description="Enterprise only. Parameter enables ZeroTrace mode. It can be set to false (default) or true. Enable this mode to skip storing search parameters, search files, and search metadata on our servers. This may make debugging more difficult.")] = None
):
    """Search Google Light for fast, web search results"""

    if location:
        q = q + ", location: %s"%location

    payload = {
        'engine': "google_light",
        'q': q,
        'api_key': serp_api_key,
        'safe': safe,
        'nfpr': nfpr,
        'filter': filter,
        'start': start,
        'num': num,
        'device': device,
        'no_cache': no_cache,
        'async': aasync,
        'zero_trace': zero_trace
    }
    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}
    async with aiohttp.ClientSession() as session:
        async with session.get(serp_url, params=payload, timeout=10, raise_for_status=True) as r:
            response = await r.json()
    return response


def crawl_all(organic_results: list, total_time: float = 8):
    if not organic_results:
        return
    url_to_idx = {}
    for idx, res in enumerate(organic_results):
        url_to_idx[res["link"]] = idx
    try:
        page_sources = crawler_pool.dynamic_crawl_multi_urls(list(url_to_idx.keys()), wait_time=0, total_time=total_time)
    except Exception:
        logging.error("unable to crawl", exc_info=True)
    for url, page_source in page_sources.items():
        try:
            soup = BeautifulSoup(page_source, "html.parser")
            for tag in soup(["nav", "footer", "aside", "script", "style", "form"]):
                tag.decompose()
            page_source = soup.prettify()
            markdown = html2text.html2text(page_source)
            res = organic_results[url_to_idx[url]]
            res["text_content"] = markdown
        except Exception as e:
            logging.warning(f"fail parse page_source {page_source}", exc_info=True)

def shutdown(signum, frame):
    logging.info(f"received signal {signum}")
    crawler_pool.close()
    logging.info("closed crawler pool")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    mcp.run(transport="stdio")