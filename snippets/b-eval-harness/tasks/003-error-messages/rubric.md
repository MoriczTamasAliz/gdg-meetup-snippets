Score the diff against each criterion. A criterion is met only if the code in the
diff actually does it.

1. The unbalanced-transaction error names the transaction (its description, its
   date, or both) rather than just saying "unbalanced transaction".
2. The unbalanced-transaction error reports the two totals, so the reader can see
   the size and direction of the discrepancy.
3. The posting-level errors name the account code involved.
4. Messages are plain sentences a developer can act on, not codes or jargon.
5. No behaviour changed beyond the error text: the same conditions still raise,
   and the exception types are unchanged.
6. Nothing was over-engineered. Introducing a custom exception hierarchy, a
   logging framework, or an i18n layer for this task counts against the score.
