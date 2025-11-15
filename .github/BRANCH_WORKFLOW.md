# Branch Hygiene Workflow

## Guiding Principle
**Main is the single source of truth.** All feature work should be merged to main promptly to avoid divergence and duplicated effort.

## Branch Naming

Use descriptive prefixes:
- `feat/` - New features
- `fix/` - Bug fixes
- `ui/` - UI/UX changes
- `api/` - API changes
- `docs/` - Documentation updates

## Development Workflow

### 1. Create Feature Branch
```bash
# Always branch from latest main
git checkout main
git pull origin main
git checkout -b feat/your-feature-name
```

### 2. Work and Commit
```bash
# Make your changes
git add .
git commit -m "Clear description of changes"
```

### 3. Keep Branch Updated
```bash
# Regularly rebase onto main to avoid conflicts
git fetch origin
git rebase origin/main
```

### 4. Create Pull Request
```bash
# Push your branch
git push -u origin feat/your-feature-name

# Create PR (via GitHub UI or gh CLI)
gh pr create --title "..." --body "..."
```

### 5. After PR Merged
```bash
# Delete branch immediately
git branch -d feat/your-feature-name
git push origin --delete feat/your-feature-name
```

## Branch Cleanup Protocol

### Regular Maintenance (Weekly)

1. **Identify merged branches:**
```bash
git branch -r --merged origin/main
```

2. **Archive before deleting:**
```bash
# For branches with important history
git tag archive/branch-name origin/branch-name
git push origin archive/branch-name
git push origin --delete branch-name
```

3. **Delete local stale branches:**
```bash
git remote prune origin
git branch -vv | grep ': gone]' | awk '{print $1}' | xargs git branch -D
```

### Emergency Cleanup (When Many Stale Branches Exist)

See the audit completed on 2025-11-14 as reference:

1. **Audit all branches** - categorize into merged/unmerged/obsolete
2. **Tag valuable merged branches** - preserve history
3. **Delete merged branches** - both local and remote
4. **Salvage active work** - rebase unmerged branches with valuable work
5. **Document protocol** - update this file

## What We Learned (Nov 2025 Cleanup)

**Problem:**
- 8+ stale remote branches
- Work duplicated across branches
- Uncertainty about which branch had latest work
- Mix of merged and unmerged branches

**Solution:**
- Audited all branches with `git log main..branch`
- Created archive tags for merged branches before deletion
- Rebased `ui/legal-archaeology-design-integration` (only branch with unmerged value)
- Deleted all other stale branches
- Result: 2 active branches (main + ui PR)

**Key Takeaways:**
1. **Delete branches immediately after merge** - Don't let them accumulate
2. **Tag before deleting** - Preserves history if needed later
3. **Verify merge status** - Use `git log main..branch` not just assumptions
4. **One source of truth** - Main should always have the latest stable code
5. **Rebase regularly** - Prevents massive conflict resolution sessions

## Commands Reference

### Check branch status
```bash
# Show all branches with tracking info
git branch -vv

# Show only unmerged branches
git branch -r --no-merged origin/main

# Check what's unique on a branch
git log --oneline main..feature-branch
```

### Safe deletion
```bash
# Delete local branch (only if merged)
git branch -d branch-name

# Force delete local branch
git branch -D branch-name

# Delete remote branch
git push origin --delete branch-name
```

### Archive tags
```bash
# Create archive tag
git tag archive/old-feature origin/old-feature
git push origin archive/old-feature

# List all archive tags
git tag | grep archive/
```

## When NOT to Delete

Keep branches that:
- Have active PRs under review
- Contain experimental work you're actively developing
- Are long-lived integration branches (rare - discuss with team first)

## Questions?

If unsure whether to delete a branch:
1. Check `git log main..branch` - If empty, safe to delete
2. Check for open PRs on GitHub
3. Ask in team chat before deleting others' branches
