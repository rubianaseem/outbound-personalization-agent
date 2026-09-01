# Outbound Personalization Agent

Takes account and contact signals in, generates a personalized 3-touch outbound email sequence out — grounded in what the account actually did (a specific page visited, a comparison viewed, a trial signal), not generic templated copy.

This mirrors the personalized outreach layer I built in production: triggering HubSpot outreach based on activation stage and ICP fit, rather than blasting the same sequence to everyone.

## What it does

1. Takes a contact/account record with signals (source, trigger event, industry, role, pain point tags)
2. Generates a 3-email sequence (Day 0, Day 3, Day 7) where each email references the actual trigger signal, not a placeholder
3. Adapts tone and angle based on role (a founder gets a different angle than a marketing ops manager)
4. Falls back to a clean templated sequence (with the signal substituted in) if no LLM key is set, so it still runs and is still personalized — just not AI-written

## Quick start

```bash
git clone https://github.com/rubianaseem/outbound-personalization-agent.git
cd outbound-personalization-agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY (optional)
python outbound_personalization_agent.py --input sample_contacts.csv
```

## Example output

```
Contact: Dana Reyes, VP RevOps @ Fjord Logistics
Trigger: Compared us against a competitor on G2 three days ago

--- Email 1 (Day 0) ---
Subject: saw you comparing options on G2
Hi Dana, noticed Fjord Logistics was checking us against [competitor] on G2 —
happy to send over the specific breakdown most RevOps leads ask about
(data sync reliability). Worth a quick look?

--- Email 2 (Day 3) ---
Subject: the sync reliability question
...

--- Email 3 (Day 7) ---
Subject: closing the loop
...
```

## Cost note

One LLM call generates all 3 emails together (~400-600 tokens total per contact) rather than 3 separate calls — keeps cost to roughly one call per contact regardless of sequence length.

## GTM tech stack this maps to

| Step | Tool used here | Swap with |
|---|---|---|
| Trigger signals in | Generic CSV | Clay (enrichment + trigger export), Apollo.io, a CDP export |
| Sequence generation | Anthropic API | Any LLM API (OpenAI, Gemini) — same prompt pattern |
| Sending the sequence | — | Instantly, Smartlead, Apollo sequences, HubSpot sequences |
| Reply/engagement tracking | — | Trellus, Amplemarket, Qualified |

## Customising for your stack

- `TONE_BY_ROLE` in the script maps job title keywords to a tone/angle — extend it for your ICP's common titles
- Swap `sample_contacts.csv` for live trigger events from Clay, a CDP, or your MAP's activity feed
- The 3-touch cadence (Day 0/3/7) is set in `SEQUENCE_DAYS` — change freely

## How this runs today (and what production would add)

**Trigger:** none built in — run manually (`python outbound_personalization_agent.py --input ...`) or schedule/trigger it whenever new trigger events land (a Clay webhook, a scheduled export pull). It doesn't watch for new contacts on its own.

**Action taken:** prints the generated 3-email sequence to your terminal. It does **not** send anything — no email is actually sent to the contact. You'd take this output and load it into your sending tool (Instantly, Smartlead, HubSpot/Apollo sequences).

**Self-learning:** no. Tone selection (`TONE_BY_ROLE`) is a hand-coded lookup, not a model that learns from reply/open rates. There's no feedback loop built in.

**Loop:** no persistent process — one pass over the contacts file, then it exits.

**What a production version would add:**
- A trigger from your enrichment/CDP tool (Clay webhook, or a scheduled pull of "new trigger events today")
- A write-back/send step: push the generated sequence into Instantly/Smartlead/HubSpot Sequences via their API rather than just printing it
- Reply/open tracking fed back in (via Trellus/Amplemarket/Qualified) so you could eventually see which trigger types and tones actually get replies
