---
name: forum-digest
description: This skill should be used when the user says "forum digest", "lw digest", "ea forum digest", "alignment forum digest", "lesswrong updates", "what has X posted on lesswrong/ea forum", "posts about [topic]", or mentions forum activity tracking. Creates digests of posts and comments from followed users or topics across LessWrong, EA Forum, and Alignment Forum.
---

# Forum digest

Track users and topics across LessWrong, EA Forum, and Alignment Forum. Generate digests of recent activity with special attention to belief updates and mind changes.

## Supported forums

| Forum | Key | Aliases | URL |
|-------|-----|---------|-----|
| LessWrong | `lesswrong` | `lw`, `less-wrong` | lesswrong.com |
| EA Forum | `eaforum` | `ea`, `effective-altruism` | forum.effectivealtruism.org |
| Alignment Forum | `alignmentforum` | `af`, `alignment` | alignmentforum.org |

## Prerequisites

1. **Python 3** with `requests` library:
   ```bash
   pip install requests
   ```

2. **Configure subscriptions**:
   ```bash
   cp ~/.claude/skills/forum-digest/config.example.json ~/.claude/skills/forum-digest/config.json
   ```

## Configuration

Edit `~/.claude/skills/forum-digest/config.json`:

```json
{
  "subscriptions": [
    {
      "type": "user",
      "forum": "lesswrong",
      "slug": "daniel-kokotajlo"
    },
    {
      "type": "topic",
      "forum": "eaforum",
      "slug": "ai-safety"
    }
  ],
  "digest_days": 7,
  "output_dir": "digests"
}
```

### Subscription types

**User subscriptions** track a specific person's posts and comments:
```json
{
  "type": "user",
  "forum": "lesswrong",
  "slug": "daniel-kokotajlo"
}
```

**Topic subscriptions** track all posts tagged with a topic:
```json
{
  "type": "topic",
  "forum": "eaforum",
  "slug": "ai-governance"
}
```

| Field | Description |
|-------|-------------|
| `type` | `user` or `topic` |
| `forum` | `lesswrong`, `eaforum`, or `alignmentforum` |
| `slug` | Username or topic slug (from the URL) |
| `digest_days` | Number of days to look back (default: 7) |
| `output_dir` | Directory for saved digest files |

## Workflow

When the user requests a forum digest:

### 1. Fetch activity

For each subscription, fetch recent activity:

**User subscriptions:**
```bash
python ~/.claude/skills/forum-digest/scripts/forum_api.py user-activity USERNAME --forum lw --days 7 --json
```

**Topic subscriptions:**
```bash
python ~/.claude/skills/forum-digest/scripts/forum_api.py topic-activity TOPIC-SLUG --forum ea --days 7 --json
```

### 2. Review content

For each post and comment retrieved:
- Read the full content (available in `contents.markdown`)
- Generate a brief 1-2 sentence summary
- Note the post/comment URL for linking

### 3. Detect belief updates

Analyse the content for indicators of belief changes:
- Phrases like "I was wrong", "I've updated", "I now think", "changed my mind"
- "I used to believe", "reconsidering", "I'm less confident"
- Explicit retractions or corrections
- Responses to criticism that acknowledge valid points

For detected updates, provide:
- A quote of the relevant passage
- Brief analysis of what changed and why

### 4. Generate digest

Format the output as markdown:

```markdown
# Forum digest
**Period:** [start date] - [end date]

---

## LessWrong

### @daniel-kokotajlo

#### Posts (2)

**[Post Title](url)** - [date]
[1-2 sentence summary]

#### Comments (5)

**On "[Parent Post Title](url)"** - [date]
[1-2 sentence summary of what they said]

---

## EA Forum

### Topic: AI governance

**[Post Title](url)** by @author - [date]
[1-2 sentence summary]

---

## Notable belief updates

**@daniel-kokotajlo** in [post/comment](url):
> "[relevant quote]"

[Analysis of the update - what they previously thought, what they now think, why]
```

### 5. Save and display

1. Display the digest in the terminal
2. Save to `~/.claude/skills/forum-digest/digests/YYYY-MM-DD.md`

## API commands

The Python script provides direct API access:

```bash
# List available forums
python forum_api.py list-forums

# User commands
python forum_api.py user daniel-kokotajlo --forum lw
python forum_api.py user-activity daniel-kokotajlo --forum lw --days 7
python forum_api.py user-activity daniel-kokotajlo --forum lw --days 7 --json
python forum_api.py posts daniel-kokotajlo --forum lw --days 14
python forum_api.py comments daniel-kokotajlo --forum ea --days 7

# Topic commands
python forum_api.py topic ai-safety --forum lw
python forum_api.py topic-activity ai-safety --forum lw --days 7
python forum_api.py topic-activity ai-safety --forum lw --days 7 --json
python forum_api.py search-topics "alignment" --forum af
```

## Finding users and topics

**Users**: Find the username from their profile URL:
- `lesswrong.com/users/USERNAME` → slug is `USERNAME`

**Topics**: Find the topic slug from the tag page URL:
- `lesswrong.com/tag/TOPIC-SLUG` → slug is `TOPIC-SLUG`
- You can also search: `python forum_api.py search-topics "query"`

## Troubleshooting

**"User not found"**: Check the username is correct (case-sensitive, use the URL slug not display name)

**"Tag/topic not found"**: Check the topic slug. Use `search-topics` to find the correct slug.

**No posts/comments returned**: The user/topic may not have activity recently. Try increasing `--days`

**Network errors**: The forum APIs are public but may rate-limit. Wait and retry.

## Notes

- All three forums use the same GraphQL API structure
- The APIs are public and require no authentication
- Rate limiting may apply for high-volume requests
- Comments include `plaintextDescription` for quick previews and `contents.markdown` for full text


## Update check

This is a shared skill. Before executing, check `~/.claude/skills/.update-config.json`.
If `auto_check_enabled` is true and `last_checked_timestamp` is older than `check_frequency_days`,
mention: "It's been a while since skill updates were checked. Run `/check-skill-updates` to see available updates."
Do NOT perform network operations - just check the local timestamp.

