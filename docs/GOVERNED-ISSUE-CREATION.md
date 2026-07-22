# Governed GitHub issue creation

Executor version `0.8.3` supports the `issue-create` operation for creating one
or more GitHub issues in one bounded execution.

The operation is declarative. Each entry in `inputs.issues` contains exactly a
`title` and `body`. Titles are non-empty single-line UTF-8 text of at most 256
bytes. Bodies are non-empty UTF-8 text of at most 65536 bytes. One operation may
contain between one and 25 issues.

The only enabled authorization fields are `interrogate` and `issue`.
Labels, assignees, milestones, projects, issue updates, closure, pull requests,
free-form commands, and arbitrary API endpoints are not supported.

`expected_mutations.issues` contains an ordered entry for every input issue with
the SHA-256 digests of its title and body. The executor rejects any mismatch.

For each issue, the executor posts a JSON payload to the repository issue
endpoint, records the returned issue number and immutable node identifier, and
then reads the issue back. Completion requires exact agreement on number, node
identifier, title, body, and open state.

If creation fails before a remote mutation can have occurred, the result is
`pre-mutation-failed`. Once any creation attempt has begun, failure is reported
as `partial-remote-mutation`; already verified issues remain recorded in the
single result artifact. A fully verified operation reports
`publication-completed`.

The user command remains:

```sh
./scripts/governed-execute ~/Downloads/<unique-operation-name>.operation.json
```
