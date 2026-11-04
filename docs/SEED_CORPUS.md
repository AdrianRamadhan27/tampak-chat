# NTI Operations corpus

The active corpus has **12 sources: 11 documents and one dataset**, with 60 physical PDF pages, approximately 11,000 document words and 109 searchable chunks. All sources are synthetic.

| Source | Original location | Indexed chunks |
| --- | --- | --- |
| data_dictionary_and_import_guide.md | Markdown · section anchors | 5 |
| gateway_integration_contracts.md | Markdown · section anchors | 5 |
| incident_communication_templates.md | Markdown · section anchors | 4 |
| incident_report_oct_2026.pdf | PDF · 32 pages | 34 |
| metric_definitions.md | Markdown · section anchors | 9 |
| payment_channel_reference.docx | DOCX · structural anchors | 16 |
| payment_incident_sop.pdf | PDF · 16 pages | 16 |
| reconciliation_handbook.docx | DOCX · structural anchors | 4 |
| reliability_review_checklist.pdf | PDF · 6 pages | 6 |
| routing_and_failover_policy.pdf | PDF · 6 pages | 6 |
| transactions_aug_oct_2026.csv | CSV · 30,180 exact-analysis records | 1 |
| transaction_status_reference.md | Markdown · section anchors | 3 |

All 109 vectors use Qwen3 Embedding 8B through OpenRouter, 4,096 dimensions and one model/query-format fingerprint. Provider pricing is capped at $0.01 per million input tokens. The 16 corpus-indexing calls used 15,717 input tokens and reported **$0.00015717**; this excludes separate query/probe calls.

The numerical CSV and the original page-7 incident finding are preserved. Replacement documents have new immutable revisions, so older citations remain meaningful. Each chatbot retrieves its own corpus; attachments added in chat remain scoped to that conversation.

## Try the added documents

- According to the gateway integration contracts, what should happen after a caller timeout?
- According to the transaction status reference, why are pending records excluded from failure rates?
- According to the routing and failover policy, what must be verified before using another gateway?
- According to the reconciliation handbook, which evidence fields are missing from the CSV?
- According to the data dictionary and import guide, how are timestamps and amounts interpreted?
- According to the incident communication templates, what belongs in a recovery update?
- According to the reliability review checklist, what evidence is needed before sign-off?
