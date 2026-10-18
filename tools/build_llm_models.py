#!/usr/bin/env python3
"""Build llm-models.json (and llm-models.js): a de-duplicated directory of large language models.

Sources (all public, no API keys):
  * models.dev        https://models.dev/api.json   models, prices, context sizes, release dates
                      from first-party APIs and from 200+ hosting providers
  * Hugging Face      https://huggingface.co/api/models   the most downloaded and most trending
                      open-weight text-generation models

Run from the repository root:

    python3 tools/build_llm_models.py

The GitHub Action in .github/workflows/llm-feed.yml runs this every day and commits the result.
Python standard library only.
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "llm-models.json"
OUT_JS = ROOT / "llm-models.js"      # same data as a script, so the page also works when opened straight from disk
SITE = "https://liconrepo.github.io/"
UA = {"User-Agent": "Mozilla/5.0 (llm-directory-builder; +https://liconrepo.github.io/)"}

# Providers that are the model's own maker. Their entries count as "first party".
FIRST_PARTY = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "meta": "Meta", "llama": "Meta",
    "mistral": "Mistral AI", "deepseek": "DeepSeek", "xai": "xAI", "cohere": "Cohere",
    "alibaba": "Alibaba (Qwen)", "moonshotai": "Moonshot AI", "moonshotai-cn": "Moonshot AI",
    "zai": "Z.ai (Zhipu)", "zhipuai": "Z.ai (Zhipu)", "minimax": "MiniMax", "ai21": "AI21 Labs",
    "perplexity": "Perplexity", "nvidia": "NVIDIA", "stepfun": "StepFun", "upstage": "Upstage",
    "inception": "Inception", "reflection": "Reflection AI", "sarvam": "Sarvam", "poolside": "Poolside",
    "thinkingmachines": "Thinking Machines", "amazon-bedrock": None, "databricks": None,
}

# Prefix used in canonical ids -> display name.
COMPANY = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "meta": "Meta", "meta-llama": "Meta",
    "mistral": "Mistral AI", "mistralai": "Mistral AI", "deepseek": "DeepSeek", "xai": "xAI", "x-ai": "xAI",
    "cohere": "Cohere", "alibaba": "Alibaba (Qwen)", "qwen": "Alibaba (Qwen)", "moonshotai": "Moonshot AI",
    "zhipuai": "Z.ai (Zhipu)", "z-ai": "Z.ai (Zhipu)", "zai": "Z.ai (Zhipu)", "minimax": "MiniMax",
    "ai21": "AI21 Labs", "perplexity": "Perplexity", "nvidia": "NVIDIA", "microsoft": "Microsoft",
    "amazon": "Amazon", "tencent": "Tencent", "baidu": "Baidu", "bytedance": "ByteDance",
    "bytedance-seed": "ByteDance", "stepfun": "StepFun", "xiaomi": "Xiaomi", "inclusionai": "inclusionAI",
    "liquid": "Liquid AI", "nousresearch": "Nous Research", "ibm": "IBM", "ibm-granite": "IBM",
    "allenai": "Allen Institute (Ai2)", "upstage": "Upstage", "sarvam": "Sarvam", "reflection": "Reflection AI",
    "poolside": "Poolside", "thinkingmachines": "Thinking Machines", "01-ai": "01.AI", "huggingfaceh4": "Hugging Face",
    "stabilityai": "Stability AI", "databricks": "Databricks", "snowflake": "Snowflake", "arcee-ai": "Arcee AI",
    "cognitivecomputations": "Cognitive Computations", "gryphe": "Gryphe", "sao10k": "Sao10K",
}


# Where each company is headquartered (country names as used by the world-map outlines).
# This is NOT in the data sources: it is a hand-kept table. A company missing here, or an individual
# or community group with no clear base, is shown as "unknown / independent" instead of being guessed.
US = "United States of America"
COUNTRY = {
    "NVIDIA": US, "OpenAI": US, "Google": US, "Anthropic": US, "Meta": US, "xAI": US, "Amazon": US, "Microsoft": US,
    "Perplexity": US, "IBM": US, "Writer": US, "Fireworks": US, "Thinking Machines": US, "Reflection AI": US,
    "Inception": US, "Arcee AI": US, "Nous Research": US, "Rekaai": US,
    "Alibaba (Qwen)": "China", "Z.ai (Zhipu)": "China", "DeepSeek": "China", "ByteDance": "China",
    "Moonshot AI": "China", "MiniMax": "China", "Xiaomi": "China", "StepFun": "China", "Tencent": "China",
    "inclusionAI": "China", "Meituan": "China", "Baidu": "China", "Paddlepaddle": "China", "Baichuan": "China",
    "Baai": "China", "Openbmb": "China",
    "Mistral AI": "France", "Cohere": "Canada", "AI21 Labs": "Israel", "Sakana": "Japan",
    "Upstage": "South Korea", "Motif Technologies": "South Korea", "Sarvam": "India",
    "Swiss Ai": "Switzerland", "Mixedbread": "Germany", "Trendyol": "Turkey", "Sdaia": "Saudi Arabia",
    "Aisingapore": "Singapore",
}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def company_name(prefix):
    key = prefix.lower()
    return COMPANY.get(key) or prefix.replace("-", " ").replace("_", " ").title()


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def build_api_models(data):
    """Merge every provider's entries into one record per underlying model."""
    groups = {}
    for pid, prov in data.items():
        pname = prov.get("name") or pid
        for mid, m in (prov.get("models") or {}).items():
            outs = (m.get("modalities") or {}).get("output") or []
            if "text" not in outs or m.get("type") in ("embedding", "image", "video", "audio", "rerank"):
                continue                                         # keep text-generating models only
            canon = m.get("canonical_model_id")
            first = pid in FIRST_PARTY and FIRST_PARTY[pid]
            if canon:
                key = canon.lower()
                company = company_name(canon.split("/")[0]) if "/" in canon else (first or pname)
            elif first:
                key = f"{pid}/{mid}".lower()
                company = first
            else:
                continue                                         # unlabeled model on a reseller: skip, avoids duplicates
            g = groups.setdefault(key, {"company": company, "entries": []})
            g["entries"].append((pid, pname, mid, m, bool(first)))

    out = []
    for key, g in groups.items():
        entries = g["entries"]
        fp = [e for e in entries if e[4]]
        best = max(fp or entries, key=lambda e: (e[3].get("last_updated") or "", e[3].get("release_date") or ""))
        _, _, _, m, _ = best
        cost_in, cost_out, free, priced = [], [], False, False
        for _, _, _, em, _ in entries:
            c = em.get("cost")
            if not isinstance(c, dict):
                continue
            ci, co = num(c.get("input")), num(c.get("output"))
            if ci is None or co is None:
                continue
            if ci == 0 and co == 0:
                free = True
            else:
                priced = True
                cost_in.append(ci)
                cost_out.append(co)
        limit = m.get("limit") or {}
        mods = m.get("modalities") or {}
        out.append({
            "id": key,
            "name": m.get("name") or key.split("/")[-1],
            "company": g["company"],
            "family": m.get("family") or "",
            "released": m.get("release_date") or "",
            "updated": m.get("last_updated") or "",
            "open": bool(m.get("open_weights")),
            "free": free,
            "paid": priced,
            "price_in": min(cost_in) if cost_in else None,         # USD per 1M tokens, cheapest host
            "price_out": min(cost_out) if cost_out else None,
            "context": num(limit.get("context")),
            "max_out": num(limit.get("output")),
            "reasoning": bool(m.get("reasoning")),
            "tools": bool(m.get("tool_call")),
            "in": sorted(set(mods.get("input") or [])),
            "out": sorted(set(mods.get("output") or [])),
            "hosts": len({e[0] for e in entries}),
            "first_party": bool(fp),
            "status": m.get("status") or "",
            "country": COUNTRY.get(g["company"]),                  # None = unknown or independent
        })
    return out


def build_hf_models():
    """Top open-weight text-generation repos on Hugging Face, by downloads and by trending."""
    seen, out = {}, []
    for sort, limit in (("downloads", 150), ("trendingScore", 100)):
        q = urllib.parse.urlencode({"pipeline_tag": "text-generation", "sort": sort, "direction": -1, "limit": limit})
        try:
            rows = get_json("https://huggingface.co/api/models?" + q)
        except Exception as e:                                   # the list still works without this source
            print("Hugging Face", sort, "failed:", e, file=sys.stderr)
            continue
        for r in rows:
            rid = r.get("id")
            if not rid or rid in seen:
                continue
            lic = next((t.split(":", 1)[1] for t in r.get("tags", []) if t.startswith("license:")), "")
            rec = {"id": rid, "author": rid.split("/")[0], "downloads": r.get("downloads") or 0,
                   "likes": r.get("likes") or 0, "license": lic, "created": (r.get("createdAt") or "")[:10],
                   "trending": sort == "trendingScore"}
            seen[rid] = rec
            out.append(rec)
    return out


def main():
    now = datetime.now(timezone.utc)
    print("Fetching models.dev ...")
    api = build_api_models(get_json("https://models.dev/api.json"))
    print("Fetching Hugging Face ...")
    hf = build_hf_models()

    # Remember when each model first appeared in this directory, so the page can show "new this week".
    old = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            old = {m["id"]: m.get("first_seen") for m in prev.get("models", [])}
        except Exception:
            pass
    today = now.strftime("%Y-%m-%d")
    first_run = not old
    for m in api:
        m["first_seen"] = old.get(m["id"]) or (m["released"] if first_run and m["released"] else today)
    api.sort(key=lambda m: (m["released"] or "0000"), reverse=True)

    doc = {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [
            {"name": "models.dev", "url": "https://models.dev/"},
            {"name": "Hugging Face", "url": "https://huggingface.co/models"},
        ],
        "prices": "USD per 1 million tokens, cheapest listed host",
        "models": api,
        "huggingface": hf,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    OUT_JS.write_text("window.LLM_MODELS=" + json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    cos = {m["company"] for m in api}
    print(f"Wrote {OUT.name}: {len(api)} models from {len(cos)} companies, {len(hf)} Hugging Face repos, "
          f"{OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
