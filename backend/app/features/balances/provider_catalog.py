from __future__ import annotations

import sqlite3

PROVIDERS = [
    ("openrouter", "OpenRouter", "USD", 10),
    ("parallel", "Parallel", "USD", 20),
    ("firecrawl", "Firecrawl", "credits", 30),
    ("exa", "Exa", "USD", 40),
    ("tavily", "Tavily", "credits", 50),
    ("chutes", "Chutes", "t", 60),
    ("desearch", "desearch", "USD", 70),
    ("vercel_gateway", "Vercel(GateWay)", "USD", 80),
]


def seed_provider_catalog(conn: sqlite3.Connection) -> None:
    for provider_key, display_name, unit, sort_order in PROVIDERS:
        conn.execute(
            """INSERT INTO providers(provider_key, display_name, unit, sort_order)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(provider_key) DO UPDATE SET
                   display_name = excluded.display_name,
                   unit = excluded.unit,
                   sort_order = excluded.sort_order""",
            (provider_key, display_name, unit, sort_order),
        )
