# Rules KB seed data

`rules_seed.csv` is ready to upload as the Rules KB's S3 data source — it
has the 3 rules we actually have real logic for (1, 3, 5), in the exact
column shape `kb_service/rules_kb_service.py` expects.

## How to use it

1. Upload `rules_seed.csv` to the S3 bucket/prefix you'll use as the Rules
   KB's data source.
2. Create the Bedrock Knowledge Base pointing at that S3 location, and sync it.
3. Set `RULES_KB_ID` in `.env` (copy from `.env.example`) to the new KB's id.
4. Set `MOCK_MODE=false`.
5. Run `python main.py --client-id AMAZON_PL` and see what actually comes back.

## Important — check this once you have a real KB

`rules_kb_service.py`'s `_parse_rule_chunk()` tries to parse each retrieved
chunk two ways: as a JSON object, then as a raw CSV row matching this
file's column order. **Neither is guaranteed to match what Bedrock
actually hands back** — that depends on how the KB was configured to
chunk the CSV during ingestion (one row per chunk, whole file per chunk,
reformatted some other way). Run a real `retrieve()` call, print what
comes back, and adjust `_parse_rule_chunk` if it doesn't match either
format already handled.

## Column reference (`rules_seed.csv`)

| Column | Meaning | Multi-value format |
|---|---|---|
| `rule_id` | e.g. `1`, `3`, `5` | - |
| `name` | short rule name | - |
| `description` | what it monitors | - |
| `threshold` | fixed numeric threshold, if any (blank = derived from the Baseline Matrix, e.g. rule 1's UCL) | - |
| `severity` | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` | - |
| `applicable_portfolios` | which `client_id`s this rule applies to (blank = all) | pipe-separated: `SYF_BNPL\|CARE_CREDIT` |
| `skill_type` | which Hard Logic skill MoE Gate should invoke (`UCL`, `PSI`, `VENDOR_CODE_MATCH`, ...) | - |
| `required_agents` | which agents MoE Gate should spin up | pipe-separated: `Data Agent\|Comparison Agent` |

Rules 2, 4, 6–16 aren't in this seed yet — add rows here once the team
defines their logic (see the project's real rule catalog notes).
