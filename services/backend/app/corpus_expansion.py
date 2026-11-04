"""Substantive synthetic reference material; policies are examples, not measured outcomes."""

CORPUS_VERSION = "nti-expanded-2026-11"


def sections(markdown: str) -> list[tuple[str, list[str]]]:
    return [
        (
            heading.strip(),
            [paragraph.strip() for paragraph in body.split("\n\n") if paragraph.strip()],
        )
        for section in markdown.strip().split("## ")[1:]
        for heading, _, body in [section.partition("\n")]
    ]


INCIDENT_APPENDIX = sections("""
## Evidence inventory and boundaries
The transaction CSV is the authoritative numerical source for this fictional case. It contains transaction identifiers, local timestamps, channel, terminal or pending status, an IDR amount, an error category and a gateway identifier. The incident narrative adds interpretation and proposed response steps. It does not supply additional observed gateway latency, network packet captures, deployment events or customer complaints.

Use the source revision and extraction page when recording evidence. A retrieved passage is an explanation, not a substitute for aggregating the transaction table. An answer about an unrecorded quantity must identify the missing evidence. In particular, this corpus cannot establish actual financial loss, settlement delay, regional impact or a verified recovery time.

## Completed and pending populations
Each month has 10,000 completed transactions and 60 pending transactions. Completed means SUCCESS plus FAILED in this fixture; it does not mean that every completed transaction succeeded. Each channel contributes 15 pending records monthly. Pending records count toward total transaction volume but are excluded from the completed-transaction failure-rate denominator.

An investigator should state the population before comparing percentages. October has 10,060 total records, 10,000 completed records and 1,110 failures. Dividing failures by all records would answer a different question. Pending transactions also require reconciliation before a financial or operational closure claim can be made. The supplied fixture deliberately keeps their final outcome unknown.

## Reconstructing the incident timeline
The report's investigation window is 15-21 October 2026 in Asia/Jakarta. The synthetic generator places failed October E-wallet transactions in that window. Other channel failures and successful transactions remain distributed through the month. This construction supports a daily channel breakdown, while making clear that it is a designed demonstration rather than a production incident measurement.

Build the timeline from transaction timestamps and distinguish the observation time from the time an engineer noticed an alert. The narrative says a synthetic alert was raised on 15 October, but no alert-event dataset is supplied. Do not invent a first-alert minute, investigation duration or precise mitigation timestamp. Those require separate operational records.

## Channel-volume controls
Completed monthly volume is held constant across the three months: 4,000 E-wallet, 3,000 Bank transfer, 2,000 QRIS and 1,000 Card transactions. Consequently, monthly rate changes can be compared without a changing completed-channel mix in this particular fixture. This simplifying assumption should be disclosed when presenting the demonstration.

In real operational data, a different mix can move the aggregate rate even if each channel's reliability is unchanged. A reviewer should therefore inspect both rates and denominators. The constant-volume assumption here is not a general property of payments. It also says nothing about the distribution of transaction amounts or the number of distinct users.

## September-to-October contribution bridge
September had 380 failed transactions and October had 1,110, an increase of 730. E-wallet increased from 100 to 648 failures, Bank transfer from 120 to 190, QRIS from 100 to 170, and Card from 60 to 102. The channel increases are therefore 548, 70, 70 and 42; they sum exactly to 730.

E-wallet's contribution to that increase is 548 divided by 730, approximately 75.07%. Its share of October failures is a different calculation, 648 divided by 1,110, approximately 58.38%. Its October failure rate is another quantity, 648 divided by 4,000, or 16.20%. A useful answer names which of these three percentages it is discussing.

## Percentage points and relative changes
The aggregate completed-transaction failure rate changed from 3.80% in September to 11.10% in October. Subtracting rates gives a 7.30 percentage-point increase. Dividing that difference by the September rate gives approximately 192.11% relative growth. These measures use different units and should never share an unlabeled axis.

For E-wallet, the rate rose from 2.50% to 16.20%, a 13.70 percentage-point change. Since E-wallet represents 40% of completed volume, its weighted contribution to the aggregate rate change is 5.48 percentage points. This identity depends on the fixture's fixed channel volumes; it is not an estimated causal effect of a gateway intervention.

## Error-category interpretation
Every failed October E-wallet record carries GATEWAY_TIMEOUT and gateway PG-A. Other failed records carry DECLINED in this simplified dataset. Successful and pending rows have no failure error category. These labels describe the recorded outcome classification; they are not complete distributed traces or a detailed taxonomy of processor responses.

A timeout can reflect a slow downstream service, a network issue, an overloaded client, or a response received after the caller's deadline. The category alone does not identify the failing component. Preserve the distinction between an observed error code and a confirmed root cause, and ask for gateway and network telemetry before selecting among those hypotheses.

## Gateway attribution and confounding
All E-wallet rows use PG-A and the other channels use PG-B. Because channel and gateway are coupled in this fixture, their effects cannot be separated by merely comparing those groups. A higher E-wallet failure rate is consistent with a PG-A problem, but also with a channel-specific integration issue or a workload difference.

To distinguish these possibilities, an investigation would need overlapping traffic, a controlled routing experiment, or corroborating traces. None is supplied as observed evidence. The report's alternative-routing mitigation is an illustrative response proposal; the transaction table does not contain a reliable before-and-after gateway experiment or measured evidence that routing fixed the incident.

## Daily segmentation and sample size
Daily failure rates should use each day's completed transactions for the selected channel as the denominator. Summing failures and dividing by summed completed transactions gives the monthly rate. Taking an unweighted average of daily percentages can produce a different result when daily volume varies, even though monthly channel totals are fixed.

Inspect the count alongside any daily percentage. A large percentage based on very few completed transactions is less informative than the same percentage over a large population. The dataset supports descriptive daily aggregation, but contains no calibrated anomaly model or significance test. A chart should not silently turn a visual spike into a statistically confirmed change point.

## Missing operational telemetry
The dataset contains timestamps, but no request-duration or latency column. It therefore cannot support a measured p50, p95 or p99 latency chart. It also lacks queue depth, retry count, response payloads, device type, region, customer identity and settlement timestamps. Do not derive these fields from the wording of an incident paragraph.

The next evidence request should identify the source, owner, period and join key needed. Gateway access logs could add duration; application traces could show deadline propagation; reconciliation exports could resolve outstanding payments. Until those sources are supplied, phrase any architecture or causal diagram as a hypothesis or illustrative workflow rather than a recovered production trace.

## Hypothesis register
The investigation can track four example hypotheses: gateway processing exceeded deadlines, network responses arrived late, retry amplification overloaded the integration, or a client configuration changed. Each is plausible in general. The supplied evidence directly supports only a concentration of recorded timeouts in a specific channel and interval.

For each hypothesis, record a discriminating observation and a rejection criterion. Correlated trace spans would help localize delay; request counts could reveal amplification; a configuration audit could verify a change. A hypothesis should not be promoted to a finding because it sounds technically convincing. The corpus intentionally leaves the definitive root cause unresolved.

## Routing mitigation decision
An alternative gateway must support the affected payment method, preserve transaction identity and expose an observable health signal before traffic is moved. This is a proposed operational checklist. The report does not assert that PG-B can process all E-wallet traffic or that production credentials and capacity are already available.

The incident commander should approve a bounded change and a rollback condition. Compare the same outcome metric and time zone before and after the change, and inspect duplicates and pending transactions as well as failures. Avoid declaring recovery from a transient improvement in one chart. The original CSV has no mitigation marker, so it cannot alone validate this intervention.

## Retry amplification risk
A timed-out caller may not know whether the downstream payment completed. Retrying the payment with a new identity can create a duplicate charge. Repeating it with the same idempotency key requires the downstream service's documented semantics and an explicit status check. Bounded retries do not eliminate uncertainty about a request already in flight.

The example response plan favors limiting concurrency, preserving a stable operation identifier and checking terminal status before replay. It does not assume every timeout is safe to retry. This dataset has transaction records rather than an attempt-level log, so it cannot measure the number of retries or prove that duplicate payments did or did not occur.

## Pending-transaction reconciliation
There are 60 pending rows in October, including 15 E-wallet rows. Their eventual outcome is not supplied. An operational team would compare the internal transaction identifier with a gateway reference and a reconciliation export, then record a terminal result or an explicit investigation state. The synthetic transaction table has no gateway-reference column for that join.

Do not label pending amounts as losses or reverse them automatically. Reconciliation decisions require evidence of the actual downstream outcome and an approved workflow. The portfolio application can show these records and explain why the rate excludes them, but it must not fabricate a settlement status or imply that the fictional incident was financially reconciled.

## Amount-based analysis limitations
Amounts are synthetic IDR values generated independently of the incident explanation. Summing a failed transaction's amount measures attempted transaction value, not money definitely lost. Summing successful amounts measures recorded successful value, not audited revenue. Fees, refunds, taxes, partial capture and settlement movements are not represented.

For an amount question, use the exact dataset tool and state the status filter and currency. If the requested financial concept needs unavailable fields, identify that gap. Do not multiply a failure rate by total value and present the product as a measured loss estimate. That shortcut assumes relationships and economic consequences absent from the fixture.

## Data-quality checks before interpretation
Before analysis, confirm the expected columns, parse timestamps in Asia/Jakarta, inspect supported status values, and verify that identifiers and row counts match the imported revision. CSV parsing and semantic mapping are separate checks: a syntactically valid file can still map the wrong field as a timestamp or payment channel.

Compare monthly completed and pending populations against the known fixture totals. Check nulls before silently excluding them. A changed import should produce a new revision with its own review, not overwrite evidence already cited by an older answer. If a validation fails, report the discrepancy before offering an operational interpretation of the resulting chart.

## Baseline selection and comparability
September is the immediate baseline for October and August supplies additional context. A previous-period comparison should use complete, comparable calendar windows and the same metric definition. The current analytics contract supports a current period versus its immediately preceding period; arbitrary nonadjacent month comparisons require a different explicit tool contract.

The fixture has no business-calendar adjustments, holiday labels or seasonality model. The observed three-month sequence does not establish an expected seasonal pattern. A reviewer can describe the increase and compare channel contributions while acknowledging that a longer historical series would be needed to characterize normal variation or forecast future failure rates.

## Proposed alert design
An example future alert would combine a channel failure-rate threshold with a minimum completed-transaction count, then require persistence across several windows before paging. Values should be tuned using representative historical traffic. This report specifies the structure of that proposal, not an implemented production threshold or an observed alert history.

Separate user-impact alerts from diagnostic signals. Gateway latency, timeout categories and retry concurrency may help explain a user-impact alert, but none should silently redefine its denominator. Every alert should link to the metric definition, time zone, affected channel, source window and runbook so the responder can reproduce the calculation rather than rely on a screenshot alone.

## Recovery verification design
A recovery review should compare failure rate, completed volume, timeout incidence, pending age and duplicate indicators over a sustained window. It should verify that traffic did not simply disappear or shift to an unobserved path. These are proposed acceptance dimensions; the provided records do not contain every required field.

Record which conditions can be checked from transaction data and which require external telemetry. The existing fixture can support count and rate breakdowns. It cannot establish pending age at a later observation time, latency recovery or duplicate-charge absence. Any final closure statement should remain qualified until the missing checks have evidence and an accountable reviewer.

## Communication and ownership
The fictional incident owner is Operations engineering. A useful handoff identifies the current impact, observed facts, unresolved hypotheses, actions taken, next check and responsible role. Avoid including customer details or credentials in an incident summary; this demonstration uses no actual customer data and no real employee identities.

Different audiences need different levels of detail, but the numbers and source references must remain consistent. An executive summary can state the 7.30 percentage-point increase and the concentrated E-wallet contribution. A technical appendix can explain denominators, confounding and missing telemetry. Neither version should imply confirmed causation or verified recovery that the evidence does not establish.

## Rollback evidence checklist
A routing or configuration change should have an identifier, approver, start time, expected effect, observation window and rollback trigger. Keep this change record separate from the outcome dataset so an analyst can distinguish an action from its measured result. No such observed change record is included in the CSV.

If failures rise, volume falls unexpectedly, reconciliation uncertainty grows or duplicate indicators change, the commander should reassess the intervention. A rollback is itself a controlled change with verification requirements. The chatbot can explain this decision structure and draw a labeled procedure diagram, but should not announce that an actual rollback occurred in the synthetic incident.

## Post-incident action register
Proposed actions are to improve timeout classification, add channel-aware alerting, exercise idempotency behavior, document routing prerequisites, and make reconciliation evidence easier to retrieve. Each action needs an owner role, due date, success criterion and verification artifact before it can be considered complete. This report does not fabricate completed tickets or implementation dates.

Distinguish prevention, detection, mitigation and learning actions. A lower timeout threshold may improve detection without fixing the underlying delay. A runbook update may improve response consistency without changing failure rates. Reviews should record the intended effect and the evidence needed to measure it, rather than assume that every action automatically increases reliability.

## Questions the corpus cannot answer
The available evidence cannot identify a named faulty deployment, the actual customer count affected, proven financial loss, precise recovery time, measured latency percentiles or the definitive technical root cause. It also cannot prove how the system would have performed with a different gateway. These are deliberate evidence boundaries for grounded-answer evaluation.

An appropriate response states what is known, names the missing source and proposes a next investigation step. It may still calculate the supported counts and rates or retrieve the response procedure. The absence of a definitive cause does not prevent useful analysis; it changes the strength and scope of the conclusion that can responsibly be drawn.

## Reviewer walkthrough and reproducibility
Start with the August-to-October trend, compare October with September, and decompose the 730 additional failures by channel. Inspect a dataset citation to verify the saved period and population. Open the gateway-timeout finding on physical page 7, then compare its cautious wording with the exact numerical result.

Next request the response procedure as a diagram and ask a deliberately unsupported latency or financial-loss question. The expected behavior is a useful supported answer with an explicit evidence gap. Record the source revision, metric definition and execution trace so another reviewer can reproduce the same calculation. All documents and records in this demonstration remain fictional.
""")


SOP_APPENDIX = sections("""
## Intake and incident classification
Begin with a concise statement of the observed payment problem, the affected channel, the first known interval and the evidence source. Confirm that the metric is computed over a defined population before treating a screenshot or a user report as a quantified incident. The fictional lab distinguishes observations, hypotheses and proposed actions throughout the response.

Assign a commander and a note-taker by role rather than embedding personal contact information. Determine whether the issue concerns authorization, confirmation, settlement or reconciliation; the supplied transaction statuses do not represent every stage. This playbook is a demonstration procedure, so its roles and escalation paths are examples rather than a real company's operating policy.

## Establish a reproducible analysis window
Record the current period with an inclusive start and exclusive end in Asia/Jakarta. October is 2026-10-01 through 2026-11-01 exclusive; its immediate prior month is September. Preserve the selected dataset revision, channel filter and completed-transaction denominator when handing the analysis to another responder.

If a question uses last month, resolve it against the bot's documented reference month rather than silently adopting the viewer's current calendar. The NTI technical-test fixture uses October 2026. If multiple sources could answer a question, identify the intended dataset explicitly. Replacing a source should not change the evidence behind an already saved response.

## Verify data and metric mappings
Inspect the imported schema and example rows. Map the timestamp, status, channel and amount fields deliberately; verify date format and status labels. Count pending or unknown records separately from completed transactions. A dataset with a missing semantic mapping must be corrected before the application claims an exact failure-rate result.

For this fixture, check 10,000 completed and 60 pending records per month. Confirm October has 1,110 failures and September has 380. A mismatch may indicate an import, time-zone or filter problem. Investigate that discrepancy before changing an operational system based on the apparent trend. Keep a record of the mapping review and the source revision used.

## Build the channel contribution bridge
Compare absolute changes in failed transactions alongside changes in rates. For September to October, the channel increases are 548 E-wallet, 70 Bank transfer, 70 QRIS and 42 Card. Verify that the four changes add to the aggregate increase of 730. This bridge explains where the increase is concentrated without claiming why it happened.

Label contribution percentages separately from failure rates and shares of current failures. E-wallet's 75.07% contribution, 16.20% October failure rate and 58.38% share of October failures answer different questions. Use a bar chart and the exact result table. Avoid a composition chart when a rate or a signed contribution could misrepresent the denominator.

## Capture corroborating evidence
Request gateway health logs, request-duration telemetry, application traces and configuration history for the affected interval. Each evidence request should specify the source owner role, time zone, join key and minimum fields. Redact secrets and unnecessary customer data before sharing records with analysis or model services.

A timeout category is an investigation lead. To support a root-cause claim, identify evidence that distinguishes downstream slowness from a network delay or client deadline issue. Preserve contrary evidence and unresolved gaps. The NTI fixture contains no measured latency or deployment log, so a response based on this corpus alone must stop short of a definitive causal conclusion.

## Approve a bounded intervention
Before moving traffic, verify that an alternative gateway supports the affected payment method, has capacity, preserves idempotency and can be observed. Name the approver, intended effect, exposure bound and rollback condition. Treat these as prerequisites rather than assuming that any healthy gateway can accept any channel.

Prefer a small, reversible change with an explicit observation window. Keep the intervention record separate from the outcome calculation. A rate improvement immediately after a change is not sufficient proof of causation, particularly if volume also changes or the comparison windows differ. The example incident narrative proposes routing mitigation without supplying a measured experiment.

## Apply retry and idempotency controls
Use a stable operation identity across an uncertain payment attempt and check the downstream service's documented idempotency behavior. A timeout does not necessarily mean the payment failed. Check terminal status before replaying an operation when possible; do not create a new payment identity merely to obtain a quicker response.

Bound concurrency and attempt counts using an approved service-specific policy. This playbook does not invent a universally safe retry number. If the downstream outcome remains unknown, move the operation to a reconciliation workflow rather than retry indefinitely. Record every attempt and its status so later analysis can distinguish unique transactions from transport retries.

## Verify recovery without hiding impact
Review failure rate and completed volume together, then inspect gateway latency, pending age and duplicate indicators when those sources exist. A lower rate can be misleading if traffic has stopped or if errors are being relabeled as pending. Use consistent source windows and preserve the exact metric definition across the comparison.

Define a sustained recovery condition before declaring the incident resolved. The current fixture supports descriptive transaction counts and rates, but cannot validate every recovery dimension. Mark missing checks as pending evidence. Do not claim that the example mitigation worked simply because the runbook describes the intended verification procedure.

## Reconcile uncertain payments
Collect pending internal transaction identifiers and the corresponding gateway references, then compare them with an authorized reconciliation source. Classify confirmed success, confirmed failure and unresolved cases separately. Do not assume that a blank error category proves a pending operation succeeded, and do not convert attempted value into a confirmed loss.

October includes 60 pending records in the fixture, but no downstream reference or settlement export is supplied. The chatbot can display those records and explain the next step. Actual resolution requires evidence outside this corpus and an approved operational workflow. Preserve the original state and an audit record of any later correction.

## Communicate an evidence-based update
Use an update structure containing observed impact, current evidence, unresolved hypotheses, actions, next check and responsible role. Include the time window, denominator and units whenever quoting a percentage. Prefer clear source references over copied screenshots that omit filters or mix percentage points with relative growth.

For this synthetic incident, it is appropriate to say that October failures rose by 730 and E-wallet contributed approximately 75.07% of that increase. It is not appropriate to name a proven faulty deployment or confirmed financial loss. A concise update can communicate urgency while retaining those uncertainty boundaries.

## Close with explicit acceptance evidence
Closure requires an accountable reviewer, a documented impact calculation, a record of interventions and verification, and a plan for unresolved reconciliation cases. Distinguish restored service from completion of every follow-up action. A closure checklist is not itself proof that its conditions have been met.

Store the evidence and source versions used for each conclusion. If a root cause remains unresolved, label it unresolved and retain the next evidence request. The original NTI case intentionally does not include the telemetry needed for final causal confirmation. A well-grounded assistant should preserve that limitation rather than write an invented resolution narrative.

## Maintain and exercise the runbook
After review, assign each improvement a role owner, success criterion and verification artifact. Exercise the response using synthetic scenarios: a channel spike, a missing baseline, a changed mapping, an uncertain payment and an unavailable telemetry source. Check whether the responder can reproduce the numbers and explain the remaining evidence gap.

Update the runbook through a new document revision so older incident answers retain their cited procedure. A source-based flowchart should follow the actual sequence in the selected revision and identify any illustrative branches. Keep credentials, real customer identifiers and private contact lists out of the public demonstration corpus.
""")


CHANNEL_SECTIONS = sections("""
## E-wallet authorization and confirmation
E-wallet represents 4,000 completed transactions per month and is mapped to PG-A. In October it has 648 failures, all labeled GATEWAY_TIMEOUT and placed within 15-21 October. Its 16.20% rate is computed over completed E-wallet transactions, not over every channel or over all E-wallet records including pending states.

The mapping couples gateway and channel, so it cannot isolate their causal effects. Request gateway and application telemetry before attributing the pattern to a specific component. Pending E-wallet transactions require a separate status check; there are 15 in each month.

## Bank transfer confirmation
Bank transfer represents 3,000 completed transactions per month and uses PG-B. Failed records increase from 80 in August to 120 in September and 190 in October. October's completed-transaction failure rate is approximately 6.33%. The 70 additional failures versus September contribute approximately 9.59% of the aggregate increase.

Transfer confirmation and actual settlement are distinct operational concepts. The fixture does not contain a bank settlement timestamp or bank reference, so it cannot establish funds-arrival duration, final settlement value or a bank-specific cause for a decline.

## QRIS confirmation
QRIS represents 2,000 completed transactions per month and uses PG-B. It has 80, 100 and 170 failures in August, September and October respectively. The October failure rate is 8.50%, and its additional 70 failures versus September account for approximately 9.59% of the increase across all channels.

The dataset's channel label identifies a payment method, not a customer segment, merchant category or geography. It also lacks QR-session creation and expiry events. Do not interpret a generic decline category as proof of a specific QR lifecycle failure.

## Card authorization and capture
Card represents 1,000 completed transactions per month and uses PG-B. Failures increase from 40 to 60 to 102 across the three months. October's failure rate is 10.20%; the 42 additional failures versus September represent approximately 5.75% of the total increase in failures.

Authorization, capture, refund and settlement stages are not modeled separately. Amounts should not be described as captured revenue without the necessary lifecycle fields. No cardholder information, issuer category or authentication outcome is included in the synthetic corpus.

## Shared status vocabulary
SUCCESS and FAILED are terminal outcomes for the fixture's completed population. PENDING is included in total records but excluded from completed-transaction rates. All four channels have 15 pending rows per month. Missing or unfamiliar states in a new upload need an explicit semantic mapping and exclusion disclosure.

The word completed is therefore a population definition, not a synonym for successful. A response should state which records contribute to the numerator and denominator. Count and rate questions can legitimately use different populations when those definitions are made explicit.

## Channel and gateway relationships
The fixture maps E-wallet to PG-A and Bank transfer, QRIS and Card to PG-B. A relationship diagram can display these recorded associations. It should not replace them with an unsupported routing topology or imply that a gateway supports an alternative method merely because an incident playbook discusses failover.

A causal diagram needs stronger evidence than a mapping table. Use labels such as observed association or proposed investigation where appropriate. The reference contains no network topology, service deployment manifest or independently observed gateway-capability catalog.

## Volume and rate comparisons
Compare a channel's failure rate against its own completed volume and its failed count against the aggregate impact. Larger channels can contribute more failures despite a lower rate. In this fixture monthly channel volumes are constant, which simplifies interpretation, but the application should still show denominators.

An unweighted mean of channel percentages would overrepresent smaller channels. Aggregate rates should be calculated by summing failures and completed transactions, then dividing. The same caution applies when comparing daily percentages with a monthly total.

## Time-zone and calendar conventions
CSV timestamps are local Asia/Jakarta values. Period filters use inclusive starts and exclusive ends. October covers 2026-10-01 through 2026-11-01 exclusive. Offset or UTC timestamps in a different uploaded dataset must be converted before applying the same local-calendar boundaries.

The bot's reference month is October 2026. Historical comparison should state the actual resolved period instead of relying on an ambiguous phrase such as last month. No business-day calendar or holiday adjustment is part of this reference.

## Error taxonomy and limitations
GATEWAY_TIMEOUT is recorded for failed October E-wallet transactions; DECLINED covers the other failures in the simplified fixture. Blank error categories occur on successful or pending rows. These labels are deliberately coarse and do not encode the complete downstream response or a verified technical fault.

Do not infer retry counts, request duration or customer behavior from an error label. Those require an attempt log, latency telemetry or an appropriate consented source. The reference supports error-category description while preserving the boundary around causal and behavioral claims.

## Amount and currency conventions
Amounts are synthetic integer IDR values. An exact sum or average should identify the requested status population and period. Failed attempted value, successful transaction value and audited revenue are different concepts. Refunds, fees, settlement movements and realized losses cannot be reconstructed from the available columns.

If a financial term is ambiguous, explain the supported quantity before displaying a chart. Do not treat a failed amount as a confirmed loss or assume that pending transactions have no financial effect. Their eventual outcome is intentionally not provided.

## Reconciliation evidence requirements
Resolving a pending transaction would require a downstream reference, an authorized status or settlement source, and an audited decision. The fixture has internal identifiers but no gateway-reference field. A source-record preview can show the pending rows without claiming their final outcome.

Preserve the original imported revision when later outcomes become available. A new data revision can support a new analysis, while an older answer remains tied to the evidence it actually used. The public demonstration should never expose real payment identifiers or credentials.

## Source and procedure navigation
Use the incident report for the observed October pattern, the playbook for a proposed response sequence, this reference for channel semantics, and the metric dictionary for formulas and exclusions. Use the transaction dataset for exact calculations. These sources complement one another rather than providing interchangeable evidence.

Physical PDF pages are available for the report and playbook. Native DOCX extraction uses section anchors, since a reliable rendered page number is not supplied by the parser. A citation should open the actual supporting location instead of inventing a page or highlight region.

## Common analytical mistakes
Avoid confusing a rate with a share, a percentage-point difference with relative growth, a pending state with success, or a timeout category with a definitive cause. Avoid estimating counts from retrieved document chunks when the dataset tool can compute them exactly.

The October E-wallet examples illustrate all three percentage concepts: 16.20% channel failure rate, 58.38% share of October failures and 75.07% contribution to the increase versus September. Naming the denominator makes the comparison understandable and reproducible.

## Review questions and evidence gaps
A reviewer can ask for each channel's three-month trend, the October contribution bridge, pending-record counts, or the documented timeout response. The corpus cannot answer actual latency percentiles, number of unique customers, final settlement delay or definitive financial loss because their required fields are absent.

A useful unsupported-answer response identifies the missing source and suggests the next check. It can still provide the supported calculation or procedure. The application should make that distinction visible through result citations, source revisions and its execution inspector.
""")


METRIC_APPENDIX = """
## Total transaction volume
Count every record in the selected period and channel, including pending states. The fixture has 10,060 records per month and 30,180 across all three months. This population differs from completed volume and does not represent unique users or distinct payment attempts after deduplication.

## Completed transaction volume
Count SUCCESS plus FAILED records. Each month has 10,000 completed records. Monthly completed volumes by channel are 4,000 E-wallet, 3,000 Bank transfer, 2,000 QRIS and 1,000 Card. Completed describes the terminal population and includes failures.

## Successful transaction count and success rate
Count SUCCESS records for the numerator. Success rate is SUCCESS divided by SUCCESS plus FAILED, multiplied by 100. The monthly success rates are 97.00%, 96.20% and 88.90%. Pending records are excluded, and a zero completed denominator has an undefined rate rather than a fabricated zero.

## Failed transaction count
Count FAILED records in the selected scope. Counts are 300, 380 and 1,110 for August, September and October. They are descriptive outcomes, not a direct measure of unique affected customers, lost money or the number of failed downstream attempts.

## Pending transaction population
Count PENDING records separately. There are 60 per month, including 15 per channel. Their eventual terminal status is not supplied. Pending records belong in total volume but not in the completed-transaction rate denominator. A reconciliation claim requires an additional outcome source.

## Percentage-point change
Subtract the baseline rate from the current rate. October's 11.10% minus September's 3.80% equals a 7.30 percentage-point increase. Retain the unit in text, tooltips and tables. This subtraction is different from relative percentage growth.

## Relative percentage change
Divide the current-minus-baseline difference by the baseline and multiply by 100. October's rate increase is approximately 192.11% relative to September. A zero baseline makes relative change undefined; display that condition instead of infinity or an invented percentage.

## Absolute failure-count change
Subtract baseline failed count from current failed count. October has 730 more failures than September. This quantity can be decomposed additively by channel when both windows use the same source definition. It is not itself a percentage or an estimate of an intervention's causal effect.

## Contribution to the increase
Divide a channel's change in failed transactions by the change in total failed transactions and multiply by 100. E-wallet contributes 548/730, or approximately 75.07%. Negative contributions can offset increases. A zero total change makes this percentage undefined. Preserve both absolute changes alongside the percentage.

## Share of current failures
Divide a channel's current failed count by the total current failed count. E-wallet represents 648/1,110, or approximately 58.38%, of October failures. This share differs from the channel failure rate and from contribution to a change. A composition chart is appropriate only for a complete, nonnegative population.

## Channel failure rate
Divide failed transactions for a channel by that channel's completed transactions. October rates are 16.20% E-wallet, approximately 6.33% Bank transfer, 8.50% QRIS and 10.20% Card. Do not divide one channel's failures by the aggregate completed volume and label it a channel rate.

## Weighted aggregation
Aggregate rates are calculated from summed numerators and denominators. An unweighted average of daily or channel percentages generally differs when populations vary. This fixture holds monthly channel volumes constant, but daily volume still varies. Show completed counts when interpreting a percentage trend.

## Time windows and timestamp interpretation
Start dates are inclusive and end dates are exclusive. Calendar boundaries use Asia/Jakarta. A UTC or offset timestamp must be converted before filtering against those boundaries. The seed's naive timestamps already use local time. Record the resolved dates in the result citation.

## Baseline contract
The comparison tool uses the immediately preceding comparable period. October's monthly baseline is September. Explicit nonadjacent month comparisons are outside that tool contract and must not silently become a different comparison. Missing baseline groups remain undefined rather than treated as zero.

## Amount sums
An amount sum is the exact total of the mapped amount column over the selected records. State IDR, period and status population. Attempted failed value is not confirmed financial loss; successful value is not audited revenue. Fees, refunds and settlement movements are absent.

## Amount averages
An average amount is a mean over the selected records with valid mapped amounts. State the population and do not average already aggregated group means without weighting. A result describes synthetic transaction amounts, not customer spending behavior or a causal incident effect.

## Error-category counts
The error column records GATEWAY_TIMEOUT on failed October E-wallet rows and DECLINED on the other failures. It is empty for successful and pending records. A category count describes recorded labels. It does not establish request latency, retry count, component ownership or definitive root cause.

## Precision and presentation
Compute from underlying records and round for display. Show rates to a sensible precision while retaining exact counts and denominators in the data table. Explain whether a change is percentage points or relative percent. Never reconstruct exact totals from rounded chart labels or approximate retrieval scores.

## Missing evidence and unavailable metrics
No latency, region, unique-user identifier, attempt count, deployment history or settlement timestamp is supplied. Metrics requiring those fields are unavailable. An assistant should state the missing source and offer a supported analysis instead of inventing values or extracting an approximate answer from narrative prose.

## Visual and citation contract
Charts use the authorized analytics result and expose its table. A dataset citation preserves revision, period and channel filters and opens matching source records. Document citations support context and procedure, while the dataset supports numbers. Source-grounded diagrams must distinguish observed associations from illustrative response steps.
"""
