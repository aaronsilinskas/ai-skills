# Workflow labels

The **workflow labels**: the GitHub labels the workflows and skills apply, which every project's repo holds.
Their colours and descriptions are a home setting: the home marker's `[[workflow_labels]]` tables, which replace the whole set.
Unset, a home gets `kaizen`'s default set (`DEFAULT_WORKFLOW_LABELS` in the `kaizen.shared.labels` module).
`kaizen project labels [<project>]` creates the ones a project's repo lacks (`--dry-run` prints the plan); it never edits a label already there, and warns when one differs.
Which role or stage each label marks is in the home's `triage-labels.md`.

This home's set, with each label's colour and description:

{{workflow_labels}}
