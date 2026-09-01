#!/usr/bin/env python3
"""
Outbound Personalization Agent
--------------------------------
Generates a personalized 3-touch outbound email sequence per contact,
grounded in an actual trigger signal rather than generic copy.

Usage:
    python outbound_personalization_agent.py --input sample_contacts.csv
"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

SEQUENCE_DAYS = [0, 3, 7]

TONE_BY_ROLE = {
    "founder": "direct, ROI-focused, respects their time",
    "ceo": "direct, ROI-focused, respects their time",
    "vp": "strategic, references team/process impact",
    "director": "strategic, references team/process impact",
    "manager": "practical, day-to-day workflow focused",
    "coordinator": "practical, day-to-day workflow focused",
}


@dataclass
class Contact:
    name: str
    title: str
    company: str
    trigger_event: str
    pain_point: str
    sequence: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Contact":
        return cls(
            name=d["name"],
            title=d["title"],
            company=d["company"],
            trigger_event=d["trigger_event"],
            pain_point=d["pain_point"],
        )


def tone_for(title: str) -> str:
    title_lower = title.lower()
    for keyword, tone in TONE_BY_ROLE.items():
        if keyword in title_lower:
            return tone
    return "professional, consultative"


def generate_sequence_templated(contact: Contact) -> list[dict]:
    """Fallback sequence used when no API key is set. Still personalized
    via string substitution, just not AI-written."""
    return [
        {
            "day": 0,
            "subject": f"re: {contact.trigger_event.lower()}",
            "body": (
                f"Hi {contact.name.split()[0]}, noticed {contact.company} "
                f"{contact.trigger_event.lower()} — thought it'd be worth "
                f"a quick note on {contact.pain_point.lower()}. Open to a "
                f"15-min chat this week?"
            ),
        },
        {
            "day": 3,
            "subject": f"following up on {contact.pain_point.lower()}",
            "body": (
                f"Hi {contact.name.split()[0]}, circling back — most teams "
                f"dealing with {contact.pain_point.lower()} find it helps to "
                f"see a live example rather than a deck. Happy to show one."
            ),
        },
        {
            "day": 7,
            "subject": "closing the loop",
            "body": (
                f"Hi {contact.name.split()[0]}, last note from me — if "
                f"{contact.pain_point.lower()} isn't a priority right now "
                f"that's completely fine, feel free to reach out whenever "
                f"it becomes one."
            ),
        },
    ]


def generate_sequence_ai(contact: Contact) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    tone = tone_for(contact.title)
    prompt = (
        f"Write a 3-email outbound sequence (Day 0, Day 3, Day 7) to "
        f"{contact.name}, {contact.title} at {contact.company}. Trigger "
        f"event: {contact.trigger_event}. Their likely pain point: "
        f"{contact.pain_point}. Tone: {tone}. Each email should be short "
        f"(3-4 sentences), reference the trigger event naturally (not "
        f"awkwardly), and end with a low-friction call to action. "
        f"Format your response as:\n"
        f"DAY 0\nSubject: ...\nBody: ...\n\nDAY 3\nSubject: ...\nBody: ...\n\n"
        f"DAY 7\nSubject: ...\nBody: ..."
    )
    response = client.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()

    sequence = []
    blocks = text.split("DAY ")
    for block in blocks[1:]:
        lines = block.strip().split("\n")
        day_num = lines[0].strip().rstrip(":")
        subject = ""
        body_lines = []
        in_body = False
        for line in lines[1:]:
            if line.lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
            elif line.lower().startswith("body:"):
                in_body = True
                body_lines.append(line.split(":", 1)[1].strip())
            elif in_body:
                body_lines.append(line.strip())
        sequence.append(
            {"day": day_num, "subject": subject, "body": " ".join(body_lines).strip()}
        )
    return sequence or generate_sequence_templated(contact)


def generate_sequence(contact: Contact) -> list[dict]:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return generate_sequence_templated(contact)
    try:
        return generate_sequence_ai(contact)
    except Exception:
        return generate_sequence_templated(contact)


def load_contacts(path: str) -> list[Contact]:
    with open(path, newline="", encoding="utf-8") as f:
        return [Contact.from_dict(row) for row in csv.DictReader(f)]


def main():
    parser = argparse.ArgumentParser(description="Generate personalized outbound sequences.")
    parser.add_argument("--input", required=True, help="Path to a contacts CSV file")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    for contact in load_contacts(args.input):
        sequence = generate_sequence(contact)
        print(f"\nContact: {contact.name}, {contact.title} @ {contact.company}")
        print(f"Trigger: {contact.trigger_event}")
        for email in sequence:
            print(f"\n--- Email (Day {email['day']}) ---")
            print(f"Subject: {email['subject']}")
            print(email["body"])


if __name__ == "__main__":
    main()
