# RAG evaluation

Administrators can open **Evaluation** for the selected chatbot, create test cases and run a measured evaluation of the actual production graph. Each case contains a question and a reviewed reference answer. Optional expected sources and literal evidence phrases diagnose retrieval failures. The NTI corpus has five editable example cases covering the evidence-fields table, the timeout SOP, pending records, evidence limits and exact monthly analytics.

## Running an evaluation

1. Sign in as administrator and choose the chatbot whose corpus you want to test.
2. Open Evaluation, then create cases or load the NTI examples. Review their references before treating them as ground truth.
3. Choose up to ten enabled cases, the Ragas metrics and a cost limit. The default is $0.25 and the maximum is $2 per run. All runs generate actual chatbot answers. Disabling all judge metrics retains generation and deterministic evidence checks.
4. Watch results update, or leave and return later. The database-leased worker continues independently of the browser. Stop preserves completed work. Worker loss requires an explicit new evaluation rather than replaying uncertain provider calls.
5. Inspect each response against its reference, open the cited immutable source revisions, read the retrieved passages and exact tool results, and export the complete JSON result.

Test-case edits affect future runs. Removing a case hides it from the case library while earlier runs retain their snapshots. Run history is per chatbot and owner; test conversations stay out of normal chat history.

## Metrics

All four Ragas scores range from zero to one. The interface displays them as percentages. Higher is better. A failed, undefined or skipped metric remains unavailable and is excluded from the mean; a real zero remains zero. Each mean shows its scored sample count.

| Stage | Metric | Interpretation |
| --- | --- | --- |
| Retrieval | Context precision | Ragas average precision over the retrieved ranking, using judge relevance verdicts against the reference answer. This is not a raw cosine similarity or simple fraction of relevant passages. |
| Retrieval | Context recall | Fraction of claims in the reference answer that the retrieved evidence supports. The reference is a proxy for relevant information, not an exhaustive labeling of the corpus. |
| Answer | Faithfulness | Fraction of response claims supported by the evidence given to generation. It does not by itself prove that the evidence or answer is correct in the real world. |
| Answer | Factual correctness | Ragas claim-level F1 between response and reference, using claim decomposition and inference checks in both directions. |

Separate deterministic diagnostics are expected-source recall, source reciprocal rank in citation order and case-insensitive literal phrase coverage in passages plus exact tool output. These are labeled separately from Ragas scores. A missing source or phrase requirement yields no score. Phrase coverage does not evaluate paraphrase quality or answer correctness.

References: [Ragas context precision](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/), [context recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/), [faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/), [factual correctness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/factual_correctness/).

## Execution and accounting

The API snapshots the selected cases and the chatbot's active permanent knowledge revisions. Each case creates a separate internal conversation and calls the same `execute_run` LangGraph entry point as ordinary chat. Its snapshot includes the same source and dataset IDs. References and evaluation instructions never enter the generation prompt. For analytical questions, evaluation adds the actual saved analytical result to the contexts supplied to the judge, so numerical claims can be assessed against computed evidence.

Ragas 0.4.3 collection metrics use an `InstructorBaseRagasLLM` adapter that delegates structured JSON generation to the existing compatible-provider transport. Pydantic validates the judge output. No automatic repair retries or separate untracked SDK calls are made. Ragas telemetry is disabled. The compatible LangChain Community dependency is pinned because the Ragas release imports legacy VertexAI modules at import time.

The current judge uses the configured Chat model and records its configuration version. A profile change between queueing and execution, or between cases, interrupts the evaluation with an explicit error. Actual generator calls also record model/version in the provider ledger. A separate judge provider is a future extension.

Every generator, planner, query-embedding and judge call goes through the provider-attempt ledger. The existing budget lock reserves conservative cost before the call. Evaluation reservations aggregate the batch stream and all child answer streams, enforcing both the evaluation cost limit and the normal daily limit. Unknown or interrupted charges retain their reservations. No private reasoning is stored. Results expose reported tokens, recorded cost and an explicit count of calls with unavailable cost.

The chat worker prioritizes normal chat jobs over waiting evaluation jobs. A running evaluation handles cases and metrics sequentially and renews its lease. The frontend polls saved progress every 1.8 seconds while the selected run is active. Returning to the view reloads the durable run rather than restarting it.

## Quality limits

The five NTI examples are an authored demonstration set. Their results do not establish retrieval recall over all possible questions, a universal hallucination rate or an independently validated production benchmark. The same generator/judge model can share biases. Judge outputs can vary even when references and corpus revisions remain fixed. Low or unexpected scores need case-level inspection and reference review.

A local five-case run on 6 November 2026 completed 78 generator/embedding/judge calls in 232.37 seconds for $0.0263225758 recorded cost. It scored context precision 0.9786, context recall 1.0000, faithfulness 0.9780 and factual-correctness F1 0.4220, with five scored samples per metric and no metric errors. These are observations from that run, not acceptance thresholds. The responses included claims beyond the brief references and one unexpected language switch on an English question. The answer prompt now states the current question's language explicitly. Reference coverage, answer verbosity and language behavior need further evaluation; a low reference F1 is not interchangeable with a hallucination rate.

For stronger evidence, expand the set with held-out questions, bilingual paraphrases, hard negatives, genuine unanswerable requests and human-reviewed references. Use a separately configured judge and multiple repetitions when comparing models or chunking policies. Keep sample counts, errors, cost and versioned evidence beside the scores.
