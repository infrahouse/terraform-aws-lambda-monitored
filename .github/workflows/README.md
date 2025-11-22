# GitHub Actions Workflows

This directory contains automated workflows for the terraform-aws-lambda-monitored module.

## Workflows

### terraform-review.yml - AI-Powered Code Review

Automated Terraform module review using Claude Code AI agent.

**Trigger:** Runs on every pull request

**What it does:**
- Reviews all code changes in the PR (Terraform, Python, docs, tests, etc.)
- Provides security, best practices, and architectural feedback
- Tracks progress across commits with incremental reviews
- Posts/updates a single PR comment with findings

#### How Incremental Reviews Work

1. **First Review:**
   - Analyzes all changes in the PR diff
   - Creates comprehensive review of security, functionality, and best practices
   - Posts review as PR comment

2. **Follow-up Reviews (after addressing issues):**
   - Downloads previous review from PR comment
   - Compares previous findings with current state
   - Marks issues with status:
     - ✅ **FIXED:** Previously flagged issues that are now resolved
     - ⚠️ **STILL PRESENT:** Issues that remain unaddressed
     - 🆕 **NEW:** New issues discovered in latest changes
   - Provides progress summary (e.g., "3 issues fixed, 1 still present, 2 new")
   - Updates the same PR comment (no spam)

3. **Concurrency Control:**
   - Only one review runs per PR at a time
   - New commits cancel in-progress reviews
   - Prevents redundant/overlapping reviews

#### Requirements

**Secrets:**
- `ANTHROPIC_API_KEY` - Required for Claude Code API access
  - Get your API key from https://console.anthropic.com/
  - Add to repository secrets: Settings → Secrets and variables → Actions

**Permissions:**
- `contents: read` - Read repository files
- `pull-requests: write` - Post/update PR comments

#### Cost Implications

**API Usage:**
- Review cost depends on PR size and complexity
- Typical review: $0.10 - $0.50 per PR
- Large PRs (100+ files): $1.00 - $3.00
- Follow-up reviews are cheaper (only reviewing delta)

**GitHub Actions Minutes:**
- ~5-15 minutes per review (Ubuntu runner)
- Free tier: 2,000 minutes/month for public repos
- Timeout: 20 minutes (prevents runaway costs)

**Recommendations:**
- Monitor usage in Anthropic Console
- Set up billing alerts
- Consider reviewing only Terraform files for cost savings (modify paths filter)

#### Configuration

**Timeout:**
```yaml
timeout-minutes: 20  # Adjust based on your needs
```

**Concurrency:**
```yaml
concurrency:
  group: terraform-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true
```

#### Artifacts

**Claude Output** (`claude-output.json`):
- Raw JSON output from Claude Code API
- Useful for debugging review issues
- Available for 90 days after workflow run
- Download from: Actions → Workflow run → Artifacts

#### Troubleshooting

##### Review is not running
- **Check:** Does the PR have any changes?
- **Check:** Is `ANTHROPIC_API_KEY` secret configured?
- **Solution:** Verify secret exists in repository settings

##### Review fails with "API key invalid"
- **Cause:** Missing or incorrect `ANTHROPIC_API_KEY`
- **Solution:** Regenerate API key at https://console.anthropic.com/
- **Solution:** Update secret in repository settings

##### Review times out after 20 minutes
- **Cause:** Very large PR or slow API response
- **Solution:** Increase `timeout-minutes` in workflow
- **Solution:** Break large PRs into smaller chunks
- **Solution:** Check Anthropic API status page

##### Previous review not found (incremental review not working)
- **Cause:** PR comment was deleted or workflow failed before posting
- **Solution:** Workflow will fall back to first review mode
- **Solution:** Previous review is reconstructed from PR comment automatically

##### Review comment is truncated
- **Cause:** GitHub comment size limit (65,536 characters)
- **Solution:** Review is automatically truncated with notice
- **Solution:** Download full review from claude-output.json artifact

##### Multiple reviews running simultaneously
- **Should not happen:** Concurrency control prevents this
- **If it happens:** Cancel duplicate workflows manually
- **Solution:** Check concurrency group configuration

##### Review finds too many false positives
- **Solution:** Customize the agent prompt in `.claude/agents/terraform-module-reviewer.md`
- **Solution:** Add project-specific guidelines to `.claude/CODING_STANDARD.md`
- **Solution:** Provide feedback in PR comments for agent to learn context

#### Customization

**Modify the review focus:**
Edit the prompts in workflow steps 86-92 and 96-107 to:
- Focus on specific file types
- Emphasize certain concerns (security, performance, cost)
- Add project-specific requirements

**Change review scope:**
```yaml
on:
  pull_request:
    paths:  # Add this to review only specific files
      - '**.tf'
      - '**.py'
```

**Adjust agent behavior:**
Modify `.claude/agents/terraform-module-reviewer.md` to:
- Add organization-specific standards
- Change severity thresholds
- Customize output format

#### Best Practices

1. **Review the review:** AI can miss context - always validate findings
2. **Engage with the bot:** Comment on false positives to improve future reviews
3. **Address critical issues first:** Focus on security/breaking changes
4. **Use incremental reviews:** Fix issues incrementally, don't wait for perfect PR
5. **Monitor costs:** Check Anthropic Console monthly for API usage

#### Learn More

- [Claude Code Documentation](https://code.claude.com/docs)
- [Anthropic API Pricing](https://www.anthropic.com/pricing#anthropic-api)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [InfraHouse Terraform Standards](https://github.com/infrahouse)

---

## Other Workflows

### terraform-CI.yml
Continuous integration checks for Terraform code quality and testing.

### terraform-CD.yml
Continuous deployment workflow for publishing the module.

### vuln-scanner-pr.yml
Security vulnerability scanning for dependencies.