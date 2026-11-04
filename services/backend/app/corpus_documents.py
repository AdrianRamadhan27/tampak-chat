"""Additional, distinct NTI reference documents rather than duplicated incident appendices."""

from collections.abc import Callable
from pathlib import Path

from docx import Document

from app.corpus_expansion import sections

TEXT_DOCUMENTS = {
    "gateway_integration_contracts.md": """# Synthetic gateway integration contracts

This is a fictional interface-design reference, not an observed gateway log or a statement of a real provider's capabilities. PG-A and PG-B are demonstration identifiers. The transaction dataset records their mapping, but does not contain complete request/response or settlement histories.

## Operation identity
An integration should assign a stable internal transaction identifier and preserve it through transport retries. A downstream operation identifier belongs in a separate reference field. The example CSV has transaction_id but no downstream reference, so the assistant must not invent a join to an unavailable gateway ledger.

## Request acceptance versus payment completion
An acknowledgement means the gateway accepted a request, not that the payment completed or settled. A reference integration should distinguish accepted, terminal success, terminal failure and unknown outcomes. The dataset's PENDING state captures unresolved status without supplying every intermediate lifecycle event.

## Idempotency contract
Before replaying a request, verify key scope, retention window, payload matching and the downstream response to an in-flight duplicate. Keep the same payment identity during uncertainty. This reference deliberately does not assign an actual retention duration or safe retry count: those must come from the selected provider's approved contract.

## Timeout handling
A caller timeout leaves the downstream outcome uncertain. Check status using the original operation identity when that capability is available. Do not label the operation a confirmed failure simply because a response did not arrive before a deadline. Preserve the distinction between a transport error, a recorded FAILED outcome and an unresolved payment.

## Status lookup requirements
A useful status response includes operation identity, state, last-update time and a trace or reference identifier. Missing operations, delayed replication and terminal failures need different interpretations. This corpus provides a design checklist; it does not supply actual status-lookup responses for the 60 pending October transactions.

## Error classification
Preserve the original response code and a normalized category. Separate validation, authentication, rate limiting, decline, transport timeout and unknown outcomes. In the simplified CSV, failure categories are only DECLINED and GATEWAY_TIMEOUT. A richer taxonomy in this reference does not imply that those extra observations are present in the data.

## Observability fields
Record request start, downstream acceptance, response completion, attempt number, stable identity and result category when building an integration. Latency percentiles and retry amplification require those events. The supplied transaction timestamps alone cannot reconstruct request durations, a retry count or a measured p95 latency.

## Security and evidence handling
Keep credentials in server-side secret storage and redact authorization material from logs. Share only the minimal diagnostic evidence needed for an investigation. All examples in this corpus are fictional and have no real customer identity, credential, account number or employee contact detail.

## Routing boundaries
The fixture maps E-wallet to PG-A and other channels to PG-B. It does not establish that PG-B supports E-wallet failover. Confirm method support, idempotency, status lookup, capacity and monitoring before using any alternative. The separate routing policy describes the required approval process rather than a measured successful intervention.
""",
    "transaction_status_reference.md": """# Transaction status reference

Fictional NTI operations reference. This document defines how to interpret the imported fixture; it does not resolve pending transactions or add new observed outcomes.

## SUCCESS
SUCCESS is a terminal successful outcome in the fixture. Count it in both the successful numerator and the completed population. The success rate is SUCCESS / (SUCCESS + FAILED) times 100. A successful transaction record is not by itself an audited settlement or revenue record.

## FAILED
FAILED is a terminal failed outcome in this fixture. Count it in the failure-rate numerator and the completed denominator. Do not equate every failed amount with confirmed financial loss. A failed record also does not identify how many transport attempts preceded it.

## PENDING
PENDING means the final outcome is unresolved in the supplied evidence. Include it in total record volume and exclude it from completed-transaction rates. There are 60 pending records per month and 15 per channel. An absent error code does not turn a pending record into success.

## Unknown or unmapped values
New uploads may contain labels such as unknown, processing or cancelled. Those labels are not additional observed states in the packaged CSV. Review their semantics and map or exclude them explicitly. Report excluded counts instead of silently changing the denominator to make a chart look complete.

## Completed population
Completed means SUCCESS plus FAILED, not merely successful transactions. Each seeded month has 10,000 completed records and 10,060 total records. October includes 8,890 successes, 1,110 failures and 60 pending records. The resulting 11.10% failure rate uses a denominator of 10,000.

## State transitions versus snapshots
A transaction row is a recorded state, not a full sequence of transition events. This CSV does not show when a request was accepted, how many times it was retried, when it settled or whether a later reconciliation changed its state. Transition diagrams should describe an illustrative lifecycle unless additional event evidence is supplied.

## Corrections and revision history
When a reconciliation source supplies a later outcome, import a new dataset revision and record the correction source. Preserve earlier evidence rather than editing old cited results in place. An older answer should remain understandable against the snapshot it actually used, even if a later revision changes the current operational picture.

## Display conventions
Show terminal and unresolved populations separately. Keep counts alongside percentages and preserve null or undefined results when the denominator is zero. A chart can describe a trend, while the source-record view explains which records were included. Neither should claim an unobserved final outcome.
""",
    "data_dictionary_and_import_guide.md": """# Transaction data dictionary and import guide

This fictional import specification accompanies transactions_aug_oct_2026.csv. Its purpose is schema interpretation and reproducibility, rather than supplying another copy of the transaction dataset.

## transaction_id
The internal synthetic record identifier uses a TX prefix and a zero-padded sequence. It identifies a record in this fixture. Do not treat the identifier as a customer identity, downstream gateway reference or proof of one and only one network attempt. There are no real payment identifiers in this corpus.

## timestamp
Timestamps are local Asia/Jakarta values written in ISO format. Period starts are inclusive and ends are exclusive. Convert UTC or offset-bearing timestamps before using local calendar boundaries in a different upload. For day-first dates, select the explicit format in review rather than relying on ambiguous automatic parsing.

## channel
Supported fixture values are E-wallet, Bank transfer, QRIS and Card. Preserve consistent spelling during import. A channel identifies a payment method and is not a merchant segment or region. If an uploaded file uses another vocabulary, confirm its mapping before comparing it with the seed.

## status
Observed labels are SUCCESS, FAILED and PENDING. Map successful, failed and excluded populations separately. Completed-transaction rates exclude pending states. Counts of all records include them. Consult the status reference when explaining why these two metrics have different denominators.

## amount
Amounts are synthetic integer IDR values. Sum or average the actual mapped column through the dataset tool. Recorded successful value, attempted failed value, revenue, settlement and financial loss are different concepts. Fields needed for the latter concepts are not present.

## error_code
Failed October E-wallet rows carry GATEWAY_TIMEOUT; other failed rows carry DECLINED. Successful and pending rows have an empty category. Preserve the distinction between an empty value and a confirmed absence of an operational issue. The field is a classification, not a latency measurement or root-cause verdict.

## gateway
PG-A is assigned to E-wallet and PG-B to the other channels. Because gateway and channel are coupled, simple group comparisons cannot isolate their causal effects. A routing experiment or corroborating traces would be needed to separate those explanations.

## File-level checks
Validate column names, timestamp parsing, row count, supported categories and missing values before analysis. Review at least a sample and the semantic mappings. CSV and XLSX parsing do not themselves establish that a selected timestamp or amount column has the intended business meaning. XLSX imports its active worksheet.

## Expected fixture totals
Across August, September and October there are 30,180 records. Each month has 10,000 completed and 60 pending records. Failure counts are 300, 380 and 1,110. Use these checks to detect an import or filter error before presenting an operational interpretation.

## Source revisions and analytical results
Keep originals and normalized data under the same immutable revision. Saved calculations identify their dataset version, metric, date range and filters. A source replacement can become current after review without changing the evidence behind an earlier cited answer.

## Unsupported fields
No request duration, region, customer identity, gateway reference, attempt number, settlement timestamp or deployment identifier is supplied. Do not fabricate them from another column. Ask for an appropriate evidence source when a question requires one of those fields.
""",
    "incident_communication_templates.md": """# Synthetic incident communication templates

These are example communication structures, not historical messages that were actually sent. No real employee identity, contact detail or customer information is included. All quoted operational numbers refer to the fictional fixture.

## Initial assessment
State the observed symptom, affected channel, time window, source and next check. Example: October completed-transaction failure rate is 11.10%, compared with 3.80% in September. Investigation is focused on the E-wallet concentration. The definitive root cause and exact recovery time are not yet established by the available evidence.

## Impact update
Include the population and unit. Example: October has 1,110 failed out of 10,000 completed transactions, with 60 additional pending records excluded from that denominator. This describes transaction outcomes. It does not establish the number of unique customers affected or a confirmed monetary loss.

## Channel contribution update
Separate contribution from rate and share. Example: E-wallet contributes 548 of the 730 additional failures versus September, approximately 75.07%. Its October channel failure rate is 16.20%. Its share of October failures is approximately 58.38%. Keep these labels when copying a chart into a summary.

## Hypothesis update
Distinguish observed evidence from possible explanations. Example: failed October E-wallet records are labeled GATEWAY_TIMEOUT and mapped to PG-A. Gateway, network and client-deadline explanations remain hypotheses until corroborated. Do not announce a faulty deployment without deployment or trace evidence.

## Mitigation proposal
Name the approver role, intended change, prerequisites, observation window and rollback criteria. Explain which measurements will test the proposal. A proposed traffic-routing change is not an observed successful mitigation, and a healthy alternative must be verified to support the affected payment method.

## Handoff
Include current impact, resolved questions, unresolved hypotheses, decisions, next check and owner role. Link exact source revisions and analytical filters. A handoff should make it possible to reproduce the calculation without relying on private conversation context or a screenshot with missing dates.

## Recovery update
State the verification evidence, not only that a chart looks better. Check failure rate and completed volume together; add latency, pending age and duplicate indicators when their sources exist. The packaged dataset cannot verify all of those dimensions, so missing checks should remain explicit.

## Closure note
Separate restored service, final root-cause confirmation, reconciliation and follow-up actions. Record reviewer role and evidence for each completed condition. If a condition remains unresolved, say so. This corpus does not contain a verified resolution timestamp, completed remediation ticket or finalized settlement ledger.

## Executive summary
A concise summary can communicate the 7.30 percentage-point aggregate increase and the concentrated E-wallet contribution. It should retain a statement of uncertainty and a link to the supporting calculation. Brevity does not justify changing a denominator or turning an association into a proven cause.
""",
}

FAILOVER_SECTIONS = sections("""
## Purpose and approval boundary
This fictional policy describes prerequisites for changing payment routing. It is a design reference, not proof that a specific alternative gateway is available. The seeded CSV maps E-wallet to PG-A and other channels to PG-B, but contains no controlled routing experiment or verified failover outcome.

The incident commander approves a bounded intervention after its assumptions are documented. Keep the approver role, change identifier, affected method, expected effect and rollback condition together. An unrecorded routing change cannot later be presented as a verified cause of recovery.

## Capability and capacity checks
Confirm payment-method support, identity and idempotency semantics, status lookup, capacity, monitoring and reconciliation coverage. A generally healthy gateway is not automatically a valid alternative for every method. This reference does not assert that PG-B can accept E-wallet traffic.

Record evidence for each prerequisite and identify unresolved checks. Verify both terminal success and uncertain-outcome behavior in an appropriate test environment. Do not use an incident chart as a substitute for an approved capability contract or capacity assessment.

## Canary plan
Define a limited exposure, an observation window and a consistent comparison metric. Preserve operation identity and channel labels so outcomes remain attributable. Canary percentages and durations are intentionally not invented here; they require the owner's approved capacity and risk limits.

Observe completed volume alongside failures, since a falling error rate can hide traffic loss. Keep the intervention record separate from the outcome dataset. Changes in traffic mix or missing observations should be reported before interpreting a rate difference.

## Guardrails and rollback
Specify conditions for stopping or reversing the intervention, including unexpected failure growth, missing traffic, reconciliation uncertainty or duplicate indicators. A rollback is another controlled change that also needs verification, ownership and an audit trail.

Do not infer safe retries from a timeout. Stable identity, downstream status checks and bounded concurrency remain necessary during routing changes. The transaction fixture has no attempt-level log and cannot prove that duplicate operations were avoided.

## Verification evidence
Check the same rate definition and date boundaries before and after a change, then add latency, pending-age and duplicate evidence when available. The original CSV supports transaction counts and rates but lacks several of those telemetry fields.

Document which checks succeeded, which remain unresolved and who reviewed them. A planned verification procedure is not evidence that recovery occurred. Avoid reporting a precise recovery time unless a suitable observation source supports it.

## Change record and review
Retain the change identifier, approver role, scope, start and end observations, decision rationale, rollback outcome and evidence links. Compare intended effects with observed results, while recording confounding factors and missing data.

Use the outcome to improve readiness rather than retrospectively invent a clean causal story. This policy complements the incident playbook and the gateway integration reference. It does not supply new observed incident events or alter the synthetic transaction records.
""")

REVIEW_SECTIONS = sections("""
## Review scope and evidence inventory
This fictional checklist guides a payment-reliability review. Identify the dataset revision, incident report, procedures, metric dictionary and available telemetry before making a finding. A source inventory should distinguish recorded outcomes, normative policies and proposed investigations.

Define which questions the review can answer and which need another source. The NTI fixture supports exact transaction counts and rates. It cannot establish unique customer impact, measured latency, settlement delay or a definitive root cause.

## Numerical validation
Recalculate monthly populations and failure rates from records. Confirm that pending states are excluded from the completed denominator. Compare the three-month trend with the documented 3.00%, 3.80% and 11.10% rates before interpreting the apparent October deterioration.

For a contribution bridge, verify that channel changes sum to the total increase. E-wallet, Bank transfer, QRIS and Card contribute 548, 70, 70 and 42 additional failures versus September. A correct chart preserves those underlying counts and labels the percentage denominator.

## Integration and uncertainty checks
Review operation identity, downstream status lookup, timeout handling, retry bounds and reconciliation evidence. A caller timeout does not prove that a payment failed. A status snapshot does not reveal the full sequence of transport attempts.

The gateway reference is a design checklist, not an observed provider trace. Identify the actual contractual and telemetry evidence needed before accepting a technical cause or claiming that an uncertain operation is safe to replay.

## Monitoring and recovery checks
Inspect rates and completed volume together. Determine whether latency, queue depth, pending age and duplicate indicators have trustworthy sources. A dashboard cannot demonstrate a missing metric by relabeling a different quantity.

Define recovery conditions before reviewing a mitigation. Mark unverified conditions explicitly and separate service recovery from reconciliation completion. The seeded incident narrative proposes response steps without supplying a complete measured recovery record.

## Communication and causal claims
Check that summaries distinguish observations, hypotheses, proposed actions and verified results. Percentage points, relative changes, channel failure rates and shares of failures need distinct labels. A short executive summary must retain those distinctions.

Reject unsupported claims about a faulty deployment, financial loss or unique affected customers. Request the missing evidence rather than filling the gap with a plausible narrative. A process diagram should show either sourced steps or a clearly labeled illustrative proposal.

## Sign-off and follow-up
Record reviewer role, source revisions, unresolved questions, action owners and verification artifacts. A follow-up action is complete only when its stated success criterion has evidence. Keep prevention, detection, mitigation and learning actions separate.

Preserve the original evidence and create new document or data revisions for later corrections. The review should remain reproducible after sources evolve. All case material here is synthetic and is intended for a public technical demonstration rather than real operational use.
""")

RECONCILIATION_SECTIONS = sections("""
## Purpose and scope
This is a fictional reconciliation handbook. It describes how to resolve uncertain payment outcomes when authorized downstream evidence is available. It does not supply a settlement ledger or resolve the pending rows in the NTI fixture.

## Intake population
Select the period and channel explicitly and retain the imported source revision. The original fixture includes 60 pending records per month, including 15 per channel. Keep that population distinct from completed transactions used for success and failure rates.

## Matching requirements
Match a stable internal identity to a downstream gateway reference and an authorized status or settlement record. Amount and date alone are insufficient identifiers. The CSV has an internal transaction_id but no gateway-reference or settlement-reference column.

## Outcome classification
Separate confirmed success, confirmed failure, unresolved and disputed cases. Record the supporting source and observation time for any classification. Do not infer success from a blank error category or label a pending amount a confirmed financial loss.

## Uncertain and conflicting evidence
An unavailable status endpoint, a delayed record and a contradictory terminal result need different next steps. Preserve both observations when sources disagree and escalate through an approved role-based workflow. Avoid repeated payment creation while the original operation remains uncertain.

## Corrections and auditability
Keep the original imported record intact. Apply a verified correction through a new version that identifies its source, reviewer role and observation time. Earlier analytical answers remain pinned to their original evidence rather than changing silently after reconciliation.

## Reporting and communications
Report unresolved counts and attempted values with clear definitions. A pending-value sum is not a measured loss estimate. Use the communication templates to separate what is known, what requires another source and the next responsible check.

## Closure conditions
Record the reviewed outcome, evidence reference, accountable role and unresolved exceptions before closing a case. This handbook supplies a checklist rather than an observed closure record. No precise settlement delay or final financial adjustment can be calculated from the packaged CSV alone.
""")


def generate_extra_documents(
    folder: Path, pdf_writer: Callable[[Path, str, list[tuple[str, list[str]]]], None]
) -> list[Path]:
    paths = []
    for name, content in TEXT_DOCUMENTS.items():
        path = folder / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    for name, title, content in [
        ("routing_and_failover_policy.pdf", "Routing and failover policy", FAILOVER_SECTIONS),
        ("reliability_review_checklist.pdf", "Reliability review checklist", REVIEW_SECTIONS),
    ]:
        path = folder / name
        pdf_writer(path, title, content)
        paths.append(path)
    path = folder / "reconciliation_handbook.docx"
    document = Document()
    document.add_heading("Synthetic reconciliation handbook", 0)
    for heading, paragraphs in RECONCILIATION_SECTIONS:
        document.add_heading(heading, 1)
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
    document.add_heading("Minimum evidence fields", 1)
    table = document.add_table(rows=1, cols=3)
    for cell, text in zip(table.rows[0].cells, ["Field", "Purpose", "In the CSV?"], strict=True):
        cell.text = text
    for row in [
        ["Internal transaction ID", "Identify the imported operation", "Yes"],
        ["Gateway reference", "Join an authorized downstream record", "No"],
        ["Terminal outcome", "Record an evidence-backed result", "Only current fixture state"],
        ["Settlement reference", "Verify a settlement movement", "No"],
        ["Observation time", "Explain when the evidence was checked", "No"],
        ["Reviewer role", "Record an accountable decision", "No"],
    ]:
        for cell, text in zip(table.add_row().cells, row, strict=True):
            cell.text = text
    document.save(path)
    paths.append(path)
    return paths
