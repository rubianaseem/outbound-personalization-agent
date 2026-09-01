#!/usr/bin/env python3
"""
Outbound Personalization Agent (v2 — evidence-gathering)
-----------------------------------------------------------
Drafts outbound sequences from live account context, at scale.

Like the other v2 agents, this keeps a persistent "brain" file per
contact (brain/<contact>.json + a human-readable .md rendering) that
accumulates context across multiple runs: intent signals, trigger
events (funding, job changes, tech-stack mentions, etc.), and what
was already sent to them. Every new sequence draft is generated FROM
that accumulated context, not from a single row of a spreadsheet, and
--batch drafts sequences for every contact you're tracking in one run
("at scale").

Usage:
    python outbound_personalization_agent.py --input sample_contacts.csv
    python outbound_personalization_agent.py --batch
    python outbound_personalization_agent.py --show "Jordan Lee"
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

BRAIN_DIR = "brain"

TONE_BY_ROLE = {
    "cmo": "peer-to-peer, strategic, ROI-and-brand-outcome focused",
    "cro": "peer-to-peer, revenue and pipeline focused, blunt",
    "vp marketing": "strategic but tactical, team-efficiency focused",
    "vp sales": "pipeline and quota focused, no fluff",
    "director": "practical, process and workflow focused",
    "manager": "hands-on, day-to-day pain focused",
}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def load_brain(slug: str) -> dict:
    path = os.path.join(BRAIN_DIR, f"{slug}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "contact_name": None,
        "contact_title": None,
        "company": None,
        "industry": None,
        "trigger_events": [],
        "intent_signals": [],
        "sequences_sent": [],
        "evidence_log": [],
    }


def save_brain(slug: str, brain: dict):
    os.makedirs(BRAIN_DIR, exist_ok=True)
    with open(os.path.join(BRAIN_DIR, f"{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(brain, f, indent=2)
    render_markdown(slug, brain)


def render_markdown(slug: str, brain: dict):
    lines = [f"# {brain['contact_name']} — {brain['company']}", ""]
    lines.append("## Profile")
    lines.append(f"- Title: {brain.get('contact_title') or 'Unknown'}")
    lines.append(f"- Industry: {brain.get('industry') or 'Unknown'}")
    lines.append("")
    lines.append("## Trigger events")
    for t in brain["trigger_events"]:
        lines.append(f"- {t['date']}: {t['event']}")
    lines.append("")
    lines.append("## Intent signals")
    for s in brain["intent_signals"]:
        lines.append(f"- {s['date']}: {s['signal']}")
    lines.append("")
    lines.append("## Sequences sent")
    for s in brain["sequences_sent"]:
        lines.append(f"- {s['date']}: {s['angle']}")
    lines.append("")
    if brain.get("latest_sequence"):
        seq = brain["latest_sequence"]
        lines.append(f"## Latest drafted sequence ({seq['date']})")
        lines.append(f"Angle: {seq['angle']}")
        lines.append("")
        lines.append(seq["body"])
    with open(os.path.join(BRAIN_DIR, f"{slug}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def ingest_row(brain: dict, row: dict, today: str) -> list:
    changes = []
    brain["contact_name"] = row["contact_name"]
    brain["contact_title"] = row["contact_title"]
    brain["company"] = row["company"]
    brain["industry"] = row["industry"]

    trigger_event = row.get("trigger_event", "").strip()
    if trigger_event and trigger_event not in [t["event"] for t in brain["trigger_events"]]:
        brain["trigger_events"].append({"date": today, "event": trigger_event})
        changes.append(f"trigger: {trigger_event}")

    intent_signal = row.get("intent_signal", "").strip()
    if intent_signal and intent_signal not in [s ["signal"] for s in brain["intent_signals"]]:
        brain["intent_signals"].append({"date": today, "signal": intent_signal})
        changes.append(f"signal: {intent_signal}")

    brain["evidence_log"].append(
        {"date": today, "note": ", ".join(changes) if changes else "checked in, no new context"}
    )
    return changes


def build_context_summary(brain: dict) -> str:
    parts = []
    if brain["trigger_events"]:
        parts.append("Trigger events: " + "; ".join(t["event"] for t in brain["trigger_events"]))
    if brain["intent_signals"]:
        parts.append("Intent signals: " + "; ".join(s["signal"] for s in brain["intent_signals"]))
    if brain["sequences_sent"]:
        parts.append(
            "Already sent: " + "; ".join(s["angle"] for s in brain["sequences_sent"])
            + " (do not repeat these angles)"
        )
    return " | ".join(parts) if parts else "No accumulated context yet — this is a cold first touch."


def generate_sequence_templated(brain: dict) -> tuple:
    title = (brain["contact_title"] or "").lower()
    tone = next((v for k, v in TONE_BY_ROLE.items() if k in title), "professional, direct")
    trigger = brain["trigger_events"][-1]["event"] if brain["trigger_events"] else None
    signal = brain["intent_signals"][-1]["signal"] if brain["intent_signals"] else None

    if trigger:
        angle = f"reference: {trigger}"
        opener = f"Noticed {brain['company']} {trigger.lower()} — congrats."
    elif signal:
        angle = f"reference: {signal}"
        opener = f"Saw {brain['company']} {signal.lower()}."
    else:
        angle = "cold intro, ICP fit"
        opener = f"Reaching out because {brain['company']} looks like a strong fit for what we do in {brain['industry']}."

    body = (
        f"DAY 1 / Subject: quick thought for {brain['company']}\n"
        f"{opener} Given your role as {brain['contact_title']}, thought this might be relevant. "
        f"(tone: {tone})\n\n"
        f"DAY 4 / Subject: re: {brain['company']}\n"
        f"Following up — happy to share how similar {brain['industry']} teams are approaching this.\n\n"
        f"DAY 9 / Subject: closing the loop\n"
        f"Last note from me — if timing's off, no worries, I'll check back next quarter.\n"
        f"(Set ANTHROPIC_API_KEY for an AI-drafted, fully personalized version.)"
    )
    return angle, body


def generate_sequence_ai(brain: dict) -> tuple:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return generate_sequence_templated(brain)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        context = build_context_summary(brain)
        prompt = (
            f"Draft a 3-email outbound sequence (Day 1, Day 4, Day 9) to "
            f"{brain['contact_name']}, {brain['contact_title']} at "
            f"{brain['company']} ({brain['industry']}). Live account context: "
            f"{context}. Ground every email in this context — do not write a "
            f"generic template. Format each email exactly as:\n"
            f"DAY N / Subject: ...\n<body>\n\n"
            f"Keep each body under 80 words. Do not repeat any angle already sent."
        )
        response = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        body = response.content[0].text.strip()
        trigger = brain["trigger_events"][-1]["event"] if brain["trigger_events"] else None
        signal = brain["intent_signals"][-1]["signal"] if brain["intent_signals"] else None
        angle = f"AI-drafted from: {trigger or signal or 'ICP fit'}"
        return angle, body
    except Exception as exc:  # pragma: no cover
        angle, body = generate_sequence_templated(brain)
        return angle, f"(AI generation failed: {exc} — templated fallback below)\n\n{body}"


def process_row(row: dict, today: str):
    slug = slugify(row["contact_name"])
    brain = load_brain(slug)
    changes = ingest_row(brain, row, today)

    angle, body = generate_sequence_ai(brain)
    brain["latest_sequence"] = {"date": today, "angle": angle, "body": body}
    brain["sequences_sent"].append({"date": today, "angle": angle})
    save_brain(slug, brain)

    print(f"\nContact: {brain['contact_name']} ({brain['contact_title']}, {brain['company']})")
    print(f"New context this run: {', '.join(changes) if changes else '(none)'}")
    print(f"Sequence angle: {angle}")
    print(f"\n{body}\n")
    print(f"Brain file: {BRAIN_DIR}/{slug}.md")


def batch(today: str):
    if not os.path.isdir(BRAIN_DIR):
        print("No contacts tracked yet — run --input against a CSV first.")
        return
    files = sorted(f for f in os.listdir(BRAIN_DIR) if f.endswith(".json"))
    if not files:
        print("No contacts tracked yet — run --input against a CSV first.")
        return

    print(f"BATCH DRAFTING — {len(files)} contact(s) at scale, from accumulated context\n")
    for filename in files:
        slug = filename[:-5]
        brain = load_brain(slug)
        angle, body = generate_sequence_ai(brain)
        brain["latest_sequence"] = {"date": today, "angle": angle, "body": body}
        brain["sequences_sent"].append({"date": today, "angle": angle})
        save_brain(slug, brain)
        print(f"--- {brain['contact_name']} ({brain['company']}) — angle: {angle} ---")
        print(body)
        print()


def show_contact(name: str):
    slug = slugify(name)
    path = os.path.join(BRAIN_DIR, f"{slug}.md")
    if not os.path.exists(path):
        print(f"No brain file found for '{name}'.")
        return
    with open(path, encoding="utf-8") as f:
        print(f.read())


def main():
    parser = argparse.ArgumentParser(description="Draft outbound sequences from accumulated live account context.")
    parser.add_argument("--input", help="Path to a contacts CSV file (ingests as new context, drafts a sequence)")
    parser.add_argument("--batch", action="store_true", help="Draft fresh sequences for every tracked contact, at scale")
    parser.add_argument("--show", help="Show the accumulated brain file for a contact")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")

    if args.batch:
        batch(today)
    elif args.show:
        show_contact(args.show)
    elif args.input:
        if not os.path.exists(args.input):
            print(f"Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        with open(args.input, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                process_row(row, today)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
