# FinRag: operational intelligence over a live transaction stream

A live data stream of mock transaction data that can be queried via an LLM connected to an MCP server. Messy transaction failure error messages are embedded via pgvector and are found on related queries via hybrid HNSW search.

## Key features

- Producer: creates events and pushes them to Kafka topic; ~4% of transactions are mock failures
- Consumer: reads from Kafka topic and pushes events to transaction database; embeds error messages on transaction failures
- MCP Server: list of tools available for the agent to use; agent never writes its own SQL
- Agent: queryable via CLI; routes queries to proper tooling; able to find embedded transaction failures; cites specific transaction IDs to avoid hallucinations
