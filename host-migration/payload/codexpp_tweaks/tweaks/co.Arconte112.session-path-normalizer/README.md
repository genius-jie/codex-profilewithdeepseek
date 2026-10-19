# Session Path Normalizer

Codex Desktop may keep a running thread under a Windows extended path such as
`\\?\C:\...\rollout.jsonl` while the persisted thread index still asks to
resume `C:\...\rollout.jsonl`. That string mismatch can produce a stale-path
resume failure even though both paths point at the same file.

This Codex++ tweak runs in the main process and keeps
`threads.rollout_path` in the isolated Codex++ `state_5.sqlite` database in the
extended Windows path form used by running sessions. Database triggers handle
new and changed rows immediately; a slower periodic pass repairs rows that
were written while the database was unavailable.

It only updates absolute Windows drive paths for unarchived threads. It does
not move or delete session files. The renderer stale-path guard is debounced,
and lifecycle teardown is receiver-bound so a tweak reload cannot leave old
timers or database connections running in the background.
