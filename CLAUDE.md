# charts-next

## Work Tracking

Work items are GitHub issues on the org-wide "KubeMQ" project board
(https://github.com/orgs/kubemq-io/projects/2). The procedure is
https://github.com/kubemq-io/kubemq-server/blob/master/docs/github-workflow.md: an issue lives in the
repo whose code changes (this repo's usual areas: area/chart); every PR body starts with
`Closes #N` (or `Refs #N` for a slice); merged-but-unreleased work carries `release/pending`;
releases are milestones. Labels here are managed by `scripts/github/labels.sh` in kubemq-server.
