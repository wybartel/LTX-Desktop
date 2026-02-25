import os, json, re, urllib.request, sys

webhook      = os.environ.get('SLACK_WEBHOOK_URL', '')
if not webhook:
    print('SLACK_WEBHOOK_URL not set — skipping')
    sys.exit(0)

title        = os.environ['PR_TITLE']
number       = os.environ['PR_NUMBER']
pr_url       = os.environ['PR_URL']
body         = os.environ.get('PR_BODY', '')
branch       = os.environ['BRANCH_NAME']
branch_url   = os.environ['REPO_URL'] + '/tree/' + branch
author       = os.environ['AUTHOR']
base         = os.environ['BASE_BRANCH']
changed      = os.environ['CHANGED_FILES']
additions    = os.environ['ADDITIONS']
deletions    = os.environ['DELETIONS']

# ── Extract ## Summary section from PR body ──────────────────────
summary = ''
m = re.search(r'## Summary\s+(.*?)(?=\n##|\Z)', body, re.DOTALL)
if m:
    lines = [l.strip() for l in m.group(1).strip().splitlines() if l.strip()]
    formatted = []
    for l in lines[:10]:
        formatted.append('• ' + re.sub(r'^[-*•]\s*', '', l) if re.match(r'^[-*•]', l) else l)
    summary = '\n'.join(formatted)
if not summary:
    summary = (body[:500].strip() + ('…' if len(body) > 500 else '')) if body else '_No description provided_'

# ── Extract image URLs embedded in PR body ───────────────────────
images = re.findall(r'!\[.*?\]\((https?://\S+?)\)', body)

# ── Build Slack Block Kit payload ────────────────────────────────
blocks = [
    {
        'type': 'header',
        'text': {'type': 'plain_text', 'text': f'New Pull Request #{number}', 'emoji': True}
    },
    {
        'type': 'section',
        'text': {'type': 'mrkdwn', 'text': f'*<{pr_url}|{title}>*'},
        'fields': [
            {'type': 'mrkdwn', 'text': f'*Author*\n<https://github.com/{author}|@{author}>'},
            {'type': 'mrkdwn', 'text': f'*Branch*\n<{branch_url}|`{branch}`>  →  `{base}`'},
            {'type': 'mrkdwn', 'text': f'*Files changed*\n{changed}'},
            {'type': 'mrkdwn', 'text': f'*Lines*\n+{additions} / -{deletions}'},
        ]
    },
    {'type': 'divider'},
    {
        'type': 'section',
        'text': {'type': 'mrkdwn', 'text': f'*Summary*\n{summary}'}
    },
    {'type': 'divider'},
    {
        'type': 'actions',
        'elements': [
            {
                'type': 'button',
                'text': {'type': 'plain_text', 'text': 'View PR', 'emoji': True},
                'url': pr_url,
                'style': 'primary'
            },
            {
                'type': 'button',
                'text': {'type': 'plain_text', 'text': 'View Branch', 'emoji': True},
                'url': branch_url
            }
        ]
    }
]

# Attach up to 3 screenshots found in the PR body
for img_url in images[:3]:
    blocks.append({
        'type': 'image',
        'image_url': img_url,
        'alt_text': 'Screenshot'
    })

# ── POST to Slack ────────────────────────────────────────────────
payload = json.dumps({'blocks': blocks}).encode('utf-8')
req = urllib.request.Request(
    webhook,
    data=payload,
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as resp:
    print(f'Slack responded: {resp.status} {resp.read().decode()}')
