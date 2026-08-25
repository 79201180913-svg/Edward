# Edward local storage

The `SQLiteStore` class owns Edward's local analytics database.

Default layout:

```text
data/
└── edward.db
```

The database is created automatically on first use. No separate database server is required.

`walk_forward_runs` stores immutable Walk-Forward experiment results. `analysis_snapshots` stores point-in-time analysis decisions and can reference the Walk-Forward run used by the decision.
