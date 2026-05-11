# Evaluation Protocol

OpenRepoBench evaluates coding agents under reproducible task conditions.

## Tracks

1. Patch-only
2. Agent without internet
3. Agent with public tests
4. Agent with internet
5. Human baseline

These tracks must not be mixed on the same leaderboard.

## Primary metric

Resolved rate:

```text
resolved = required tests pass AND no forbidden behavior
```

## Required disclosure

Submissions should disclose:

- Model name and version
- Agent framework
- Tool access
- Internet access
- Temperature and sampling settings
- Number of attempts
- Whether test feedback was used
- Token usage
- Cost estimate
