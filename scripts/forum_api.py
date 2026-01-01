#!/usr/bin/env python3
"""
Forum GraphQL API Client

Fetches posts and comments from LessWrong, EA Forum, and Alignment Forum.
Supports following users and topics/tags.
No authentication required - uses public GraphQL API.

API Documentation: https://www.lesswrong.com/posts/LJiGhpq8w4Badr5KJ/graphql-tutorial-for-lesswrong-and-effective-altruism-forum
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library not installed. Run: pip install requests")
    sys.exit(1)

# Forum configurations
FORUMS = {
    "lesswrong": {
        "name": "LessWrong",
        "url": "https://www.lesswrong.com/graphql",
        "base_url": "https://www.lesswrong.com",
        "aliases": ["lw", "less-wrong"]
    },
    "eaforum": {
        "name": "EA Forum",
        "url": "https://forum.effectivealtruism.org/graphql",
        "base_url": "https://forum.effectivealtruism.org",
        "aliases": ["ea", "effective-altruism", "ea-forum"]
    },
    "alignmentforum": {
        "name": "Alignment Forum",
        "url": "https://www.alignmentforum.org/graphql",
        "base_url": "https://www.alignmentforum.org",
        "aliases": ["af", "alignment", "alignment-forum"]
    }
}

SKILL_DIR = Path(__file__).parent.parent
CONFIG_FILE = SKILL_DIR / "config.json"


def resolve_forum(forum_input):
    """Resolve a forum name or alias to its canonical key."""
    forum_input = forum_input.lower().strip()

    # Direct match
    if forum_input in FORUMS:
        return forum_input

    # Check aliases
    for key, config in FORUMS.items():
        if forum_input in config["aliases"]:
            return key

    raise ValueError(f"Unknown forum: {forum_input}. Valid options: {', '.join(FORUMS.keys())}")


def get_forum_url(forum):
    """Get the GraphQL URL for a forum."""
    forum_key = resolve_forum(forum)
    return FORUMS[forum_key]["url"]


def get_forum_base_url(forum):
    """Get the base URL for a forum."""
    forum_key = resolve_forum(forum)
    return FORUMS[forum_key]["base_url"]


def load_config():
    """Load configuration from config.json."""
    if not CONFIG_FILE.exists():
        return {
            "subscriptions": [],
            "digest_days": 7,
            "output_dir": "digests"
        }
    with open(CONFIG_FILE) as f:
        return json.load(f)


def graphql_query(query, variables=None, forum="lesswrong"):
    """Execute a GraphQL query against a forum's API."""
    url = get_forum_url(forum)

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        raise Exception(f"GraphQL errors: {data['errors']}")

    return data.get("data", {})


# ============================================================================
# User-related queries
# ============================================================================

def get_user_by_slug(slug, forum="lesswrong"):
    """Fetch user details by their URL slug/username."""
    query = """
    query GetUser($slug: String!) {
      user(input: { selector: { slug: $slug } }) {
        result {
          _id
          username
          displayName
          slug
          karma
        }
      }
    }
    """

    data = graphql_query(query, {"slug": slug}, forum)
    user = data.get("user", {}).get("result")

    if not user:
        raise Exception(f"User not found: {slug}")

    return user


def get_user_posts(user_id, since_date=None, limit=50, forum="lesswrong"):
    """Fetch posts by a user, optionally filtered by date."""
    query = """
    query GetUserPosts($userId: String!, $limit: Int) {
      posts(input: {
        terms: {
          view: "userPosts",
          userId: $userId,
          limit: $limit
        }
      }) {
        results {
          _id
          title
          slug
          pageUrl
          postedAt
          baseScore
          voteCount
          commentCount
          contents {
            markdown
          }
        }
      }
    }
    """

    data = graphql_query(query, {"userId": user_id, "limit": limit}, forum)
    posts = data.get("posts", {}).get("results", [])

    # Filter by date if specified
    if since_date:
        posts = [
            p for p in posts
            if datetime.fromisoformat(p["postedAt"].replace("Z", "+00:00")) >= since_date
        ]

    return posts


def get_user_comments(user_id, since_date=None, limit=100, forum="lesswrong"):
    """Fetch comments by a user, optionally filtered by date."""
    query = """
    query GetUserComments($userId: String!, $limit: Int) {
      comments(input: {
        terms: {
          view: "profileComments",
          userId: $userId,
          limit: $limit
        }
      }) {
        results {
          _id
          postedAt
          pageUrl
          baseScore
          voteCount
          post {
            _id
            title
            slug
          }
          contents {
            markdown
            plaintextDescription
          }
        }
      }
    }
    """

    data = graphql_query(query, {"userId": user_id, "limit": limit}, forum)
    comments = data.get("comments", {}).get("results", [])

    # Filter by date if specified
    if since_date:
        comments = [
            c for c in comments
            if datetime.fromisoformat(c["postedAt"].replace("Z", "+00:00")) >= since_date
        ]

    return comments


def fetch_user_activity(slug, days=7, forum="lesswrong"):
    """Fetch all recent activity for a user.

    Returns a dict with user info, posts, and comments from the last N days.
    """
    user = get_user_by_slug(slug, forum)
    since_date = datetime.now().astimezone() - timedelta(days=days)

    posts = get_user_posts(user["_id"], since_date, forum=forum)
    comments = get_user_comments(user["_id"], since_date, forum=forum)

    return {
        "forum": forum,
        "user": user,
        "posts": posts,
        "comments": comments,
        "since_date": since_date.isoformat(),
        "fetched_at": datetime.now().isoformat()
    }


# ============================================================================
# Topic/Tag-related queries
# ============================================================================

def get_tag_by_slug(slug, forum="lesswrong"):
    """Fetch tag/topic details by slug.

    The API doesn't support direct slug lookup, so we fetch tags and filter.
    """
    query = """
    query GetTags($limit: Int) {
      tags(input: {
        terms: {
          view: "allTagsAlphabetical",
          limit: $limit
        }
      }) {
        results {
          _id
          name
          slug
          postCount
        }
      }
    }
    """

    data = graphql_query(query, {"limit": 500}, forum)
    tags = data.get("tags", {}).get("results", [])

    # Find the tag by slug
    slug_lower = slug.lower()
    for tag in tags:
        if tag.get("slug", "").lower() == slug_lower:
            return tag

    raise Exception(f"Tag/topic not found: {slug}")


def search_tags(query_str, limit=10, forum="lesswrong"):
    """Search for tags/topics by name."""
    query = """
    query SearchTags($limit: Int) {
      tags(input: {
        terms: {
          view: "allTagsAlphabetical",
          limit: $limit
        }
      }) {
        results {
          _id
          name
          slug
          postCount
        }
      }
    }
    """

    # Note: The forum API doesn't have a proper search, so we fetch and filter
    data = graphql_query(query, {"limit": 200}, forum)
    tags = data.get("tags", {}).get("results", [])

    # Filter by query string (case-insensitive)
    query_lower = query_str.lower()
    matching = [t for t in tags if query_lower in t["name"].lower()]

    return matching[:limit]


def get_posts_by_tag(tag_id, since_date=None, limit=50, forum="lesswrong"):
    """Fetch posts with a specific tag, optionally filtered by date."""
    query = """
    query GetTagPosts($tagId: String!, $limit: Int) {
      posts(input: {
        terms: {
          view: "tagRelevance",
          tagId: $tagId,
          limit: $limit
        }
      }) {
        results {
          _id
          title
          slug
          pageUrl
          postedAt
          baseScore
          voteCount
          commentCount
          user {
            displayName
            slug
          }
          contents {
            markdown
          }
        }
      }
    }
    """

    data = graphql_query(query, {"tagId": tag_id, "limit": limit}, forum)
    posts = data.get("posts", {}).get("results", [])

    # Filter by date if specified
    if since_date:
        posts = [
            p for p in posts
            if datetime.fromisoformat(p["postedAt"].replace("Z", "+00:00")) >= since_date
        ]

    return posts


def fetch_topic_activity(slug, days=7, forum="lesswrong"):
    """Fetch all recent posts for a topic/tag.

    Returns a dict with tag info and posts from the last N days.
    """
    tag = get_tag_by_slug(slug, forum)
    since_date = datetime.now().astimezone() - timedelta(days=days)

    posts = get_posts_by_tag(tag["_id"], since_date, forum=forum)

    return {
        "forum": forum,
        "topic": tag,
        "posts": posts,
        "since_date": since_date.isoformat(),
        "fetched_at": datetime.now().isoformat()
    }


# ============================================================================
# Output formatting
# ============================================================================

def format_date(iso_date):
    """Format ISO date string as readable date."""
    dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    return dt.strftime("%b %d, %Y")


def print_user_activity(activity):
    """Print a summary of user activity."""
    user = activity["user"]
    posts = activity["posts"]
    comments = activity["comments"]
    forum_name = FORUMS.get(activity.get("forum", "lesswrong"), {}).get("name", "Forum")

    print(f"\n{'='*60}")
    print(f"[{forum_name}] {user.get('displayName', user['slug'])} (@{user['slug']})")
    print(f"Karma: {user.get('karma', 'N/A')}")
    print(f"{'='*60}")

    print(f"\nPosts ({len(posts)}):")
    if posts:
        for post in posts:
            date = format_date(post["postedAt"])
            score = post.get("baseScore", 0)
            print(f"  [{date}] {post['title']} (score: {score})")
            print(f"    {post.get('pageUrl', '')}")
    else:
        print("  No posts in this period.")

    print(f"\nComments ({len(comments)}):")
    if comments:
        for comment in comments[:10]:  # Show first 10
            date = format_date(comment["postedAt"])
            score = comment.get("baseScore", 0)
            post_title = comment.get("post", {}).get("title", "Unknown post")
            contents = comment.get("contents", {}) or {}
            excerpt = contents.get("plaintextDescription", "")[:100]
            print(f"  [{date}] On: {post_title} (score: {score})")
            print(f"    \"{excerpt}...\"")
            print(f"    {comment.get('pageUrl', '')}")
        if len(comments) > 10:
            print(f"  ... and {len(comments) - 10} more comments")
    else:
        print("  No comments in this period.")

    print()


def print_topic_activity(activity):
    """Print a summary of topic activity."""
    topic = activity["topic"]
    posts = activity["posts"]
    forum_name = FORUMS.get(activity.get("forum", "lesswrong"), {}).get("name", "Forum")

    print(f"\n{'='*60}")
    print(f"[{forum_name}] Topic: {topic['name']}")
    print(f"Total posts: {topic.get('postCount', 'N/A')}")
    if topic.get("description", {}).get("plaintextDescription"):
        desc = topic["description"]["plaintextDescription"][:200]
        print(f"Description: {desc}...")
    print(f"{'='*60}")

    print(f"\nRecent posts ({len(posts)}):")
    if posts:
        for post in posts:
            date = format_date(post["postedAt"])
            score = post.get("baseScore", 0)
            author = post.get("user", {}).get("displayName", "Unknown")
            print(f"  [{date}] {post['title']} by {author} (score: {score})")
            print(f"    {post.get('pageUrl', '')}")
    else:
        print("  No posts in this period.")

    print()


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Forum API Client for LessWrong, EA Forum, and Alignment Forum",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Forums:
  lesswrong (lw)      - LessWrong.com
  eaforum (ea)        - forum.effectivealtruism.org
  alignmentforum (af) - alignmentforum.org

Examples:
  Fetch user activity from LessWrong:
    python forum_api.py user-activity daniel-kokotajlo

  Fetch user activity from EA Forum:
    python forum_api.py user-activity habryka --forum ea

  Fetch topic activity:
    python forum_api.py topic-activity ai-safety --days 14

  Search for topics:
    python forum_api.py search-topics "alignment"

  Get user info:
    python forum_api.py user daniel-kokotajlo

  Get topic info:
    python forum_api.py topic ai-safety --forum lw
"""
    )

    parser.add_argument("--forum", "-f", default="lesswrong",
                        help="Forum to query: lesswrong (lw), eaforum (ea), alignmentforum (af)")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # User info
    user_parser = subparsers.add_parser("user", help="Get user info")
    user_parser.add_argument("slug", help="User slug/username")

    # User activity
    user_activity_parser = subparsers.add_parser("user-activity", help="Get user activity")
    user_activity_parser.add_argument("slug", help="User slug/username")
    user_activity_parser.add_argument("--days", "-d", type=int, default=7,
                                       help="Number of days to look back (default: 7)")
    user_activity_parser.add_argument("--json", "-j", action="store_true",
                                       help="Output as JSON")

    # Topic info
    topic_parser = subparsers.add_parser("topic", help="Get topic/tag info")
    topic_parser.add_argument("slug", help="Topic slug")

    # Topic activity
    topic_activity_parser = subparsers.add_parser("topic-activity", help="Get topic activity")
    topic_activity_parser.add_argument("slug", help="Topic slug")
    topic_activity_parser.add_argument("--days", "-d", type=int, default=7,
                                        help="Number of days to look back (default: 7)")
    topic_activity_parser.add_argument("--json", "-j", action="store_true",
                                        help="Output as JSON")

    # Search topics
    search_parser = subparsers.add_parser("search-topics", help="Search for topics/tags")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", "-l", type=int, default=10,
                                help="Maximum results (default: 10)")

    # Posts by user
    posts_parser = subparsers.add_parser("posts", help="Get user posts")
    posts_parser.add_argument("slug", help="User slug/username")
    posts_parser.add_argument("--days", "-d", type=int, default=7,
                               help="Number of days to look back")
    posts_parser.add_argument("--json", "-j", action="store_true",
                               help="Output as JSON")

    # Comments by user
    comments_parser = subparsers.add_parser("comments", help="Get user comments")
    comments_parser.add_argument("slug", help="User slug/username")
    comments_parser.add_argument("--days", "-d", type=int, default=7,
                                  help="Number of days to look back")
    comments_parser.add_argument("--json", "-j", action="store_true",
                                  help="Output as JSON")

    # List forums
    subparsers.add_parser("list-forums", help="List available forums")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        forum = args.forum if hasattr(args, 'forum') else "lesswrong"

        if args.command == "list-forums":
            print("Available forums:")
            for key, config in FORUMS.items():
                aliases = ", ".join(config["aliases"])
                print(f"  {key} ({aliases})")
                print(f"    {config['name']}: {config['base_url']}")

        elif args.command == "user":
            user = get_user_by_slug(args.slug, forum)
            print(json.dumps(user, indent=2))

        elif args.command == "user-activity":
            activity = fetch_user_activity(args.slug, args.days, forum)
            if args.json:
                print(json.dumps(activity, indent=2, default=str))
            else:
                print_user_activity(activity)

        elif args.command == "topic":
            topic = get_tag_by_slug(args.slug, forum)
            print(json.dumps(topic, indent=2))

        elif args.command == "topic-activity":
            activity = fetch_topic_activity(args.slug, args.days, forum)
            if args.json:
                print(json.dumps(activity, indent=2, default=str))
            else:
                print_topic_activity(activity)

        elif args.command == "search-topics":
            topics = search_tags(args.query, args.limit, forum)
            print(f"Topics matching '{args.query}':")
            for topic in topics:
                print(f"  {topic['name']} (slug: {topic['slug']}, posts: {topic.get('postCount', 'N/A')})")

        elif args.command == "posts":
            user = get_user_by_slug(args.slug, forum)
            since_date = datetime.now().astimezone() - timedelta(days=args.days)
            posts = get_user_posts(user["_id"], since_date, forum=forum)
            if args.json:
                print(json.dumps(posts, indent=2))
            else:
                print(f"Posts by {args.slug} (last {args.days} days):")
                for post in posts:
                    print(f"  - {post['title']}")
                    print(f"    {post.get('pageUrl', '')}")

        elif args.command == "comments":
            user = get_user_by_slug(args.slug, forum)
            since_date = datetime.now().astimezone() - timedelta(days=args.days)
            comments = get_user_comments(user["_id"], since_date, forum=forum)
            if args.json:
                print(json.dumps(comments, indent=2))
            else:
                print(f"Comments by {args.slug} (last {args.days} days): {len(comments)}")
                for comment in comments[:10]:
                    post_title = comment.get("post", {}).get("title", "Unknown")
                    print(f"  - On: {post_title}")
                    print(f"    {comment.get('pageUrl', '')}")

    except requests.HTTPError as e:
        print(f"HTTP Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
