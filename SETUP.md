# Setup Guide

## 1. Where this installs

Plain Python script, nothing installed system-wide.

```bash
git clone https://github.com/rubianaseem/outbound-personalization-agent.git
cd outbound-personalization-agent

python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

## 2. Run it with sample data

```bash
python outbound_personalization_agent.py --input sample_contacts.csv
```

Runs entirely offline using the templated fallback (see below).

## 3. Add your API key for AI-written sequences

```bash
cp .env.example .env
```

Add to `.env`:

```
ANTHROPIC_API_KEY=your_key_here
```

Get one at https://console.anthropic.com/. Without it, you still get a personalized sequence (the trigger event and pain point are substituted into a template) — just not AI-written copy.

## 4. Connecting real trigger data

The script needs one row per contact with a specific trigger event and pain point — here's how to get that from common tools:

**Clay**
Clay is the natural fit here — set up a Clay table that enriches contacts and flags trigger events (G2 visit, trial start, content download), then export the table as CSV in the same column format as `sample_contacts.csv`, or set up a Clay webhook that POSTs new triggered contacts to a small endpoint this script reads.

**Apollo.io**
Use Apollo's People Search/Enrichment API to pull contact + company data, then combine with your own trigger detection (from your MAP or product analytics) to fill in `trigger_event`.

**A CDP or MAP activity feed (HubSpot, Segment)**
Most MAPs can export "contacts who did X in the last N days" — that list, with the trigger event as a column, is exactly this script's input format.

## 5. Sending the generated sequence

This script generates the copy — it doesn't send emails. Once you have the sequence text, the natural next step is feeding it into whatever you send with:

- **Instantly / Smartlead** — both accept sequences via API; write a small script that takes this tool's output and creates a campaign step
- **HubSpot sequences** — paste generated copy into a HubSpot sequence template, or use the Sequences API to create one programmatically
- **Apollo sequences** — same idea, via Apollo's Sequences API

## 6. Using this repo with an AI coding assistant (Cursor, Claude Code, Codex, Grok)

**Cursor** — open the folder, ask in chat (Cmd+L): *"Add a function that pulls trigger events from a Clay webhook payload and converts them into Contact objects"*

**Claude Code** — `cd` into the folder, run `claude`, ask the same way — it reads the existing `Contact` class and matches the pattern

**Codex CLI** — `cd` into the folder, run `codex`, same approach

**Grok (or any chat-only assistant)** — paste `outbound_personalization_agent.py`'s contents into the chat with your request, then copy the suggested code back into the file

## Troubleshooting

- **"ModuleNotFoundError"** — activate the virtual environment, re-run `pip install -r requirements.txt`
- **Sequences look templated, not AI-written** — `ANTHROPIC_API_KEY` isn't set or `.env` isn't in the script's folder
- **AI-generated emails aren't parsing correctly** — the model's output format drifted from the expected `DAY N / Subject: / Body:` structure; the script falls back to the template automatically in this case, but you can tighten the prompt in `generate_sequence_ai()` if it happens often
