---
name: ship
description: Ship a change the user has already agreed on. You build it and open a PR (a separate implementer sub-agent does, only if the user asks for one), an independent reviewer sub-agent reviews it, and the PR is merged once CI passes. Do not use while the change is still being discussed or designed.
---

# Ship an agreed change

You run this workflow and, by default, are the implementer: you write the code and a sub-agent writes the review. Only if the user asks for a separate agent to implement the change does a sub-agent write the code too, and you orchestrate.

The sub-agents are plain subagents, not agent-team teammates: each one reports once, when its turn ends, and stays reachable by name with SendMessage for later rounds. A repository that enables agent teams should set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` in its `.claude/settings.json`.

## Repository config

Everything specific to this repository is in `.claude/skill-config/ship.md`, at the repo root. Read it first. Its sections are named below as "the config's *Section*". If the file is missing, tell the user and ask what the checks and the after-merge steps are. Don't guess them. A section the config leaves out means there is nothing extra to do at that step.

Sub-agents don't load this skill or read the config unless told to, so every brief names the config's path.

## 1. Preconditions

- The user has agreed on the change. If the design or scope is still open, settle it with the user first.
- Do what the config's *Before starting* says, and keep any notes it asks for. The after-merge step may use them.

## 2. Implementer

Implement the change yourself, under the rules below, unless the user asked for a separate implementer. In that case spawn a named sub-agent, reachable with SendMessage. Its brief must include the agreed design, what is out of scope, these rules, the ones for a separate implementer further down, and the config's path.

- Work in your own git worktree under your scratchpad directory, on a feature branch from an up-to-date default branch: `git -C <repo> fetch && git -C <repo> worktree add <dir> -b <branch> origin/<default-branch>`. Never push directly to the default branch.
- Before every push, run the config's *Checks before every push* for what you changed, and any of its *Extra checks* that apply. Every check must pass.
- Use conventional commits that end with the Co-Authored-By line. Open the PR with `gh pr create` and end its body with the Claude Code line. Start the reviewer (step 3) right away (a separate implementer instead sends the lead the PR number, see below), then wait for CI with `gh pr checks <n> --watch` and fix any failing job. The review and CI run in parallel, and neither waits for the other.
- After `gh pr checks <n> --watch`, handle any bot the config's *Automated PR reviewers* lists. Read the summary (`gh pr view <n> --comments`) and inline comments (`gh api repos/{owner}/{repo}/pulls/<n>/comments`) for the current head. Do the same after every later push.
- To address a review on the PR, read the findings yourself from the PR: review bodies and summary comments with `gh pr view <n> --comments`, inline comments with `gh api repos/{owner}/{repo}/pulls/<n>/comments`.
- Fix every reviewer and automated-reviewer finding by default. Only one that conflicts with the agreed requirements or that you judge wrong stays unfixed for now, and step 4 says who decides it.

Only for a separate implementer:

- Run builds, tests and other checks in the foreground with a long `timeout` (up to 600000 ms). Don't start them with `run_in_background` and wait for a completion notice: an idle sub-agent is not reliably woken by it and stalls. For anything longer, use Monitor with a loop that ends when the process exits.
- Right after `gh pr create`, send the lead the PR number with SendMessage, so it can start the reviewer, then carry on with CI yourself.
- The lead may tell you to drop a nit. Report the findings you left unfixed, each with a one-line reason.
- Your final answer is your report: PR number, head SHA, check results, findings you didn't fix (each with its one-line reason), and open questions or conflicts, if any. Don't also send it with SendMessage.
- Don't merge. Stay available for review rounds.

## 3. Reviewer (fresh named sub-agent)

- Spawn it as soon as the PR is open, while CI and any automated reviewer are still running. It doesn't wait for them and doesn't report on CI.
- Spawn it with `model: "fable"`. If that spawn (or a later re-review message) fails because Fable credits or usage limits are exhausted, or the model is unavailable, spawn a fresh reviewer with `model: "opus"` and the same brief, and tell the user the review ran on Opus.
- Brief it with the PR number, the stated intent, the agreed requirements and the config's path. Leave out the implementer's reasoning, also when that is your own, the automated reviewers' comments and your own opinions. It may see the bots' comments on the PR, but it forms its own view.
- It reviews `gh pr diff <n>` and reads surrounding code for context.
- It checks the diff against the repository's CLAUDE.md conventions and the config's *Review rules*.
- If it builds, it uses its own worktree. It never checks out branches in the main clone.
- It follows the separate implementer's rule for long-running commands: run them in the foreground with a long `timeout`, or poll with Monitor. It never waits for a background completion notice.
- It labels each finding blocking or nit and posts them with `gh pr review <n> --comment`. It cannot approve, because it runs on the PR author's account. The review starts with exactly one verdict:
  - `LGTM`: merge as is.
  - `LGTM after nits`: no blocking findings; merge once the listed nits are fixed, without another full review.
  - `Changes requested`: at least one blocking finding; re-review after the fixes.
- Every review, re-review and nit check names the head SHA it covers, read from `gh pr view <n> --json headRefOid` when it starts.
- Its final answer is the verdict, that SHA and a one-line summary per finding. It doesn't also send it with SendMessage.

## 4. Iterate

- The PR is the single source of truth for findings; don't retype them. A separate implementer gets a short message such as "address the review on #<n>", plus any nit to drop and why. It fixes all the others by default.
- When a separate implementer reports a finding it judged wrong, decide it yourself: drop it, or tell it to fix it after all.
- When you are the implementer, you don't rule on findings against your own code. Fix them, nits included, or ask the user, with the finding and your reason in one line.
- Ask the user about requirement or product questions, including conflicts with the agreed requirements. Don't decide them yourself.
- After the fixes are pushed:
  - `LGTM after nits`, separate implementer: read the new commits' diff yourself. If they do what the nits asked and nothing else, go to step 6. Otherwise ask the reviewer to re-review.
  - `LGTM after nits`, you are the implementer: ask the reviewer to check that the new commits do what the nits asked and nothing else. If they do, go to step 6. Otherwise treat it as `Changes requested`.
  - `Changes requested`: ask the reviewer to re-review the new commits.
- Ask for these checks and re-reviews as soon as the fixes are pushed, without waiting for CI, which runs in parallel again.
- CI and automated-reviewer fixes can be pushed while the reviewer is working. If its review covers an older SHA than the head and no nit check covers the commits in between, ask it to review them too, even on `LGTM`.
- Watch for stalls. When a sub-agent's turn ends without the expected result (no review on the PR in `gh pr view <n> --json reviews`, or no PR or push), message it at once to check its command's result itself and finish. If it stalls again, take over the check yourself.

## 5. Cap

If blocking findings remain after 3 fix rounds, stop and bring the disagreement to the user.

## 6. Merge

A verdict alone doesn't merge. First wait for whichever of CI and the review is still running: the verdict or nit check must cover the head commit, and `gh pr checks <n> --watch` must have finished on it, with any automated review of that head handled.

If the user asked to review the PR themselves, stop before merging: remove the worktrees as below so `--delete-branch` works, report the verdict and what to look at, and merge only when they say so. Step 7 still applies afterwards.

On `LGTM` (or `LGTM after nits` with the nits checked), first remove the implementer's worktree, yours or a sub-agent's, and the reviewer's if it built (`git worktree remove <dir>`), or `--delete-branch` fails on the branch still checked out there. Check that the checks listed in the config's *Merge* pass on the head commit (`gh pr checks <n>`). Then merge without asking, with the method the config names (squash if it names none): `gh pr merge <n> --squash --delete-branch --match-head-commit <sha>`. Don't use `--admin`; if a check fails, fix it yourself or send it back to a separate implementer. Then tell the user what landed, what wasn't verified (e.g. nothing was tried in a browser) and any open follow-ups.

## 7. After merge

From the repo root of the main clone:

1. Run `git pull` on the default branch.
2. Do what the config's *After merge* says.
3. Once the change is merged, stop the sub-agents with TaskStop so none linger. Spawn fresh ones for the next change.
