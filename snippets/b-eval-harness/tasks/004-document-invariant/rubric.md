Score the diff against each criterion. A criterion is met only if the text in the
diff actually does it.

1. States the invariant correctly: within one transaction, total debits equal
   total credits.
2. Explains why the rule exists, rather than only restating it.
3. Explains what a debit and a credit mean here, since the reader is assumed not
   to know.
4. Includes a concrete worked example with real account codes and amounts.
5. Accurate about this code specifically: it should match what Posting and
   Transaction actually enforce, including that a posting carries either a debit
   or a credit but not both.
6. Proportionate. A docstring of roughly 10 to 25 lines is right; an essay is not.
7. No behaviour changed.
