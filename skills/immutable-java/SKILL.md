---
name: immutable-java
description: Immutability rules for Java, and a check for the ones ArchUnit can't see. Use when writing, changing or reviewing Java in a repository that has a .claude/skill-config/immutable-java.md (records, DTOs, services, parsers, repositories, Spring beans), and before pushing a Java change there.
---

# Immutable Java

Values don't change once built, and objects keep no state that changes. Local mutation inside a method is fine: building a map in a loop and returning it unmodifiable doesn't let anyone see it change.

## Repository config

Read `.claude/skill-config/immutable-java.md` at the repo root first. It names this repository's collection-copy helper, what enforces rule 1, its exceptions and its allowlist for mutable fields. Where it differs from a default below, it wins. If the file is missing, follow the defaults and tell the user the repository has no config.

## Rules

1. **Fields are `final`.**
   - Spring: constructor injection; `@Value` goes on constructor or `@Bean` method parameters, never on a field.
   - A test seam such as a clock is a `final` field set by a second constructor.
2. **Values are records**, changed with `@Builder(toBuilder = true)`, which returns a new one. No `@Data`, `@Setter` or `@With`, and no setters you write yourself.
3. **A record with a `List`, `Set` or `Map` component copies it in a compact constructor**, with the helper the config names:
   ```java
   public Order {
       lines = List.copyOf(lines);
   }
   ```
   - The default helpers are `List.copyOf`, `Set.copyOf` and `Map.copyOf`. They throw on nulls, and `Map.copyOf` loses iteration order. If a repository's data can hold nulls or depends on order, it needs its own helper, and the config names it.
   - Lombok's `@NonNull` on a component still runs before the copy.
   - Static constants go before the compact constructor, the constructor before the methods.
4. **A method that fills a collection returns it unmodifiable.**
   - In a stream: `.toList()`, `Collectors.toUnmodifiableSet()`, `Collectors.toUnmodifiableMap(...)`. Use the last two only when no element, key or value is null and the order doesn't matter.
   - After a loop: `return Collections.unmodifiableList(results);` (or `Map`/`Set`), which keeps nulls and order and doesn't copy.
   - `List.copyOf`/`Set.copyOf` only where nulls can't occur, e.g. a NOT NULL column.
   - A mutable collector inside another one (`groupingBy(..., Collectors.toList())`) is fine when the result goes into a record, which copies it.
5. **No counters or "last seen" fields.** Pass the position or the time in: `IntStream.range(0, list.size()).mapToObj(i -> ...)`. Read `Instant.now()` once and pass it on, so the items of one run share it.
6. **Don't reuse a Lombok builder** for several objects. Each `build()` takes the builder's current state, so start each object with its own `builder()` or `of(...)`.
7. **Hot paths wrap instead of copying.** Where profiling shows the copies matter, `Collections.unmodifiableMap` around a map the code just built replaces the deep copy. The config lists the known ones. Any other exception needs a measured reason and a comment that says why.

## State that has to change

Some state has to change: a lock, a rate limiter's timestamp, a cache that is refreshed. Keep it, but:

- Prefer one `volatile` reference to an immutable value, swapped whole, or a field that is only written under `synchronized`/a lock.
- A `final` field holding a lock or atomic needs nothing extra.
- A per-run memo is a `final` field with mutable contents, scoped to one run and never shared. Keep it private to that run.
- A new non-final field goes wherever the config says the allowlist is. Tell the user why it can't be final.

## Before you push

From the repo root:

```bash
python3 -I "${CLAUDE_SKILL_DIR}/check.py"            # every main source the config covers
python3 -I "${CLAUDE_SKILL_DIR}/check.py" $(git diff --name-only origin/main...HEAD)   # only what the branch changed
```

If the skill was not loaded in your session, as for a sub-agent, use `~/.claude/skills/immutable-java/check.py`. The script reads `.claude/skill-config/immutable-java.json` from the directory you run it in, so run it from the root of your checkout or worktree.

- **Errors** (exit 1): a record with a collection component that has no compact constructor, or one that doesn't copy or wrap every such component; Lombok `@Data`, `@Setter` or `@With`. Fix them.
- **Warnings**: `Collectors.toList()`/`toSet()`, and `return new ArrayList<>(...)` and similar. Fix those that are returned or stored. Leave a collector that rule 4 allows.
- Then run the repository's tests, including whatever the config says enforces rule 1.

## When reviewing

The script reads the source text, so it can't tell a mutable collection that leaves a method in a variable from one that doesn't. Also look for:

- a collection from a record or another method that is changed with `add`/`put`/`remove`/`sort`, which now throws `UnsupportedOperationException`. Copy it locally first (`new HashSet<>(config.failedTables())`);
- a helper object that counts or remembers between calls (rule 5);
- a `List.copyOf`/`Map.copyOf`/`toUnmodifiableMap` that can now see a null, or a map whose order matters.
