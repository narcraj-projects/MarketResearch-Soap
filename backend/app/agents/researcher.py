"""Independent per-competitor research; no shared extraction state or model calls."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

from app.harness.contracts import RunContext
from app.harness.policy import PolicyDenied
from app.harness.research_types import CompetitorResearch, ResearchState, RetrievedSource
from app.harness.retrieval import ResearchGateway
from app.harness.urls import normalize_url


def research_one(context: RunContext, competitor: dict, gateway: ResearchGateway, store: ResearchState) -> CompetitorResearch:
    cid = competitor["id"]
    with store.lane(context, cid):
        cached = store.cached_task(context, cid)
        if cached:
            return cached
        sources: list[RetrievedSource] = []
        limitations: list[str] = []
        first_url = competitor["canonical_url"]
        domain = normalize_url(first_url, demo=True)[1]
        visited = set()
        try:
            visited.add(first_url)
            documents = gateway.retrieve(context, cid, first_url)
            sources.extend(documents)
            links = [link for doc in documents if doc.access_status == "ok" and doc.evidence_kind == "page_excerpt" for link in doc.links]
            for link in links:
                if len(visited) >= 3:
                    break
                try:
                    url, target_domain = normalize_url(link, demo=True)
                except ValueError:
                    continue
                if target_domain != domain or url in visited or not any(word in urlsplit(url).path.lower() for word in ("product", "soap", "about", "ingredient", "review")):
                    continue
                visited.add(url)
                sources.extend(gateway.retrieve(context, cid, url))
            news = gateway.news(context, cid, competitor["name"])
            sources.extend(news)
            for hit in news[:2]:
                if hit.canonical_url not in visited:
                    visited.add(hit.canonical_url)
                    sources.extend(gateway.retrieve(context, cid, hit.canonical_url))
        except PolicyDenied as error:
            limitations.append(str(error))
        return store.save_task(context, cid, tuple(sources), tuple(limitations))


def research_parallel(context: RunContext, competitors: tuple[dict, ...], gateway: ResearchGateway, store: ResearchState) -> tuple[CompetitorResearch, ...]:
    if not 1 <= len(competitors) <= 3 or len({c["id"] for c in competitors}) != len(competitors):
        raise PolicyDenied("invalid_research_lanes")
    completed = []
    failures = []
    with ThreadPoolExecutor(max_workers=len(competitors), thread_name_prefix="lather-research") as pool:
        futures = [pool.submit(research_one, context, competitor, gateway, store) for competitor in competitors]
        for future in as_completed(futures):
            try:
                completed.append(future.result())
            except Exception as error:
                failures.append(error)
    # Other lanes commit even if one has an unexpected failure; never call a later agent.
    if failures:
        raise failures[0]
    store.finish(context)
    return tuple(sorted(completed, key=lambda result: str(result.competitor_id)))
