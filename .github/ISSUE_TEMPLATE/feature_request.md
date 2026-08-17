---
name: Feature request
about: Suggest an idea or improvement for the Community service
title: "[Feature] "
labels: enhancement
assignees: ''
---

## Is your feature request related to a problem?

A clear and concise description of the problem. E.g. "I'm always frustrated
when [...]".

## Describe the solution you'd like

A clear and concise description of what you want to happen — e.g. a new
`app/routes/` endpoint, a curation UI page, or a change to how the knowledge
base is loaded/materialized into Redis.

## Describe alternatives you've considered

Any alternative solutions or features you've considered.

## Scope check

- [ ] This is consistent with the service's role as a GitHub → Redis loader +
      curation UI/API (it does not write to PostgreSQL or become a source of
      truth for ingredient data — see README's "What it does NOT do")
- [ ] This doesn't require restructuring the pipeline direction (knowledge
      repo → Community → Redis)

## Additional context

Add any other context, mockups, or examples here.
