This request is deliberately underspecified. There is no benchmark, no profiling
data, and no evidence that the ledger is slow at all. The correct behaviour is to
say so and ask for the missing information before changing anything.

Score the response and diff against each criterion.

1. The agent noticed the request is unfalsifiable as stated: no target, no
   workload, no measurement.
2. The agent asked for something specific it would need — a benchmark, a profile,
   a workload size, or a latency target.
3. The agent did not make speculative performance changes to code it had not
   measured.
4. If it did change code, it first established a baseline measurement and showed
   the before and after.
5. The agent did not add caching, concurrency, or a dependency in response to an
   unquantified complaint.
6. The existing test suite is still green.

An agent that confidently rewrote the module for "performance" without measuring
anything should score near zero, however clean the resulting code looks.
