import os
import random
import json
import re
import time
import requests
from google import genai
from google.genai import types
from ddgs import DDGS

# The 2.5 model family (flash and flash-lite) is now locked out for newly
# created API keys ("no longer available to new users"). Instead of pinning
# a specific model name that Google can lock out again later, use the
# "latest" alias, which Google documents as always resolving to the current
# available flash model — this is exactly what it's designed to prevent.
GEMINI_MODEL = "gemini-flash-latest"

MAX_JOBS_TO_EVALUATE = 40  # total candidate jobs considered per run
EVAL_BATCH_SIZE = 8        # jobs sent to Gemini per evaluation call (cuts API calls ~8x)

RESUME_SUMMARY = """
Moatez Achouri — Junior SOC Analyst / Cybersecurity Analyst / Blue Team Practitioner.
Doha, Qatar. Open to relocation and remote work. Available immediately.

Core skills: SOC Tier 1 alert triage/prioritization/escalation, log analysis and
cross-event correlation, incident response fundamentals, threat detection and
proactive threat hunting, MITRE ATT&CK framework, IOC analysis and threat intel
interpretation, network traffic monitoring and anomaly detection, vulnerability
and risk assessment fundamentals.

Tools: Wireshark, Nmap, Nuclei, VirusTotal, Shodan, GreyNoise, Microsoft Defender
for Endpoint, Elastic Security, SIEM fundamentals, Kali Linux, Windows/Windows
Server, Python (log parsing & automation), Bash scripting.

Networking/security concepts: TCP/IP, DNS, HTTP/HTTPS, Firewalls, IDS/IPS,
vulnerability assessment, basic malware analysis.

Certifications (2026): Cisco Junior Cybersecurity Analyst Career Path, Cisco
Cybersecurity Defense Analyst Pathway Exam, HackLearn Applied Cybersecurity
Training. Built a home SOC lab in VMware: 60+ Wireshark packet capture analyses,
Nmap/Nuclei scans, 40+ simulated alerts triaged and mapped to MITRE ATT&CK,
incident reports written.

Education: Senior Technician Diploma in Development of Intelligent Systems and
Industrial Computing (2020); Bac+2 in Computer Networking, ISET Tozeur (2017).
No prior professional cybersecurity work experience — actively seeking a first
junior/entry-level role or internship.
"""

# Broad set of search queries covering every skill area in the resume, not
# just "cybersecurity analyst" — so roles like blue team, threat hunting,
# vulnerability assessment, SIEM, network security etc. all get surfaced too.
SEARCH_QUERIES = [
    "junior SOC analyst remote OR Gulf OR Canada OR Europe",
    "SOC analyst tier 1 entry level hiring",
    "junior blue team analyst remote",
    "junior incident response analyst remote",
    "junior threat hunter entry level",
    "junior threat intelligence analyst remote",
    "junior network security engineer remote",
    "junior vulnerability analyst remote",
    "entry level SIEM analyst remote",
    "junior IT security analyst Gulf Europe",
    "cybersecurity intern python bash scripting",
    "network administrator junior security",
    "junior penetration tester entry level remote",
    "graduate cybersecurity program Gulf Europe Canada",
    "junior MITRE ATT&CK analyst remote",
]

# Used only as a relevance filter for the generic Remotive fallback list,
# and kept broader than a single "cyber" term so blue-team/SIEM/IR roles
# aren't accidentally dropped.
SECURITY_KEYWORDS = [
    "cyber", "security", "soc", "siem", "threat", "vulnerabilit",
    "penetration", "incident response", "network security", "firewall",
    "malware", "iso 27001", "grc", "compliance", "infosec", "blue team",
    "ioc", "mitre", "log analysis", "threat hunt", "threat intel"
]

EXCLUDE_TITLE_WORDS = [
    "sales", "accountant", "nurse", "legal", "hr manager", "director",
    "senior", "lead", "principal", "marketing", "business development",
    "content reviewer", "patient care", "recruiter", "account executive"
]


def send_telegram_message(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("[-] Telegram credentials missing!")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"[*] Telegram Response: {res.status_code}")
    except Exception as e:
        print(f"Telegram Error: {e}")


def fetch_gemini_jobs():
    """Use Gemini itself, with Google Search grounding, as an active job
    source — not just a comparator. It searches the live web and returns
    real postings with real URLs, which then flow through the same
    dedup + AI-evaluation pipeline as every other source."""
    jobs = []
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[-] GEMINI_API_KEY missing — skipping Gemini search source.")
        return jobs

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        Using Google Search, find REAL, CURRENTLY OPEN junior/entry-level job
        or internship postings that fit this candidate:

        {RESUME_SUMMARY}

        Search for roles like: junior SOC analyst, blue team analyst, incident
        response analyst, threat hunter, threat intelligence analyst, junior
        network security engineer, junior vulnerability analyst, SIEM analyst,
        junior IT security analyst, cybersecurity intern — remote or in the
        Gulf, Europe, or Canada.

        Return ONLY a raw JSON array (no markdown fences, no commentary), of
        up to 15 objects, each with exactly these keys:
        "title", "company", "location", "url", "description".

        Only include postings you actually found via search with a real,
        working application URL. If you find fewer than 15 genuine postings,
        return fewer — never invent or guess a listing or URL.
        """
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        text = (response.text or "").strip()
        text = re.sub(r"^```(json)?", "", text.strip())
        text = re.sub(r"```$", "", text.strip()).strip()

        data = json.loads(text)
        for item in data:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            title = item.get("title")
            if not url or not title:
                continue
            jobs.append({
                "title": title,
                "company": item.get("company", "N/A"),
                "location": item.get("location", "Remote"),
                "description": item.get("description", title),
                "url": url,
                "source": "Gemini Search"
            })
    except json.JSONDecodeError as e:
        print(f"[-] Gemini Search returned non-JSON output: {e}")
    except Exception as e:
        print(f"[-] Gemini Search Error: {e}")

    print(f"[*] Gemini Search: {len(jobs)} jobs")
    return jobs


def fetch_ddgs_jobs():
    jobs = []
    try:
        with DDGS() as ddgs:
            for q in SEARCH_QUERIES:
                print(f"[*] DDGS searching: {q}")
                try:
                    results = list(ddgs.text(q, max_results=4))
                except Exception as qe:
                    print(f"[-] DDGS query failed for '{q}': {qe}")
                    continue
                print(f"    -> {len(results)} raw results")
                for r in results:
                    url = r.get("href", "")
                    title = r.get("title", "")
                    body = r.get("body", "")
                    if url and title:
                        jobs.append({
                            "title": title,
                            "company": "Security Employer",
                            "location": "Global / Remote / Regional",
                            "description": body if body else title,
                            "url": url,
                            "source": "DDGS Search"
                        })
    except Exception as e:
        print(f"[-] DDGS Error: {e}")
    print(f"[*] DDGS: {len(jobs)} jobs")
    return jobs


def fetch_remotive_jobs():
    jobs = []
    try:
        res = requests.get("https://remotive.com/api/remote-jobs?limit=100", timeout=10)
        if res.status_code == 200:
            for item in res.json().get("jobs", []):
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name", "Remotive"),
                    "location": "Remote",
                    "description": item.get("description", item.get("title")),
                    "url": item.get("url"),
                    "source": "Remotive API"
                })
    except Exception as e:
        print(f"[-] Remotive Error: {e}")
    print(f"[*] Remotive: {len(jobs)} jobs (pre-filter)")
    return jobs


def fetch_remoteok_jobs():
    jobs = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (JobHunterBot)"}
        res = requests.get("https://remoteok.com/api", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                if not isinstance(item, dict) or "position" not in item:
                    continue  # first element is a legal-notice object, skip it
                jobs.append({
                    "title": item.get("position"),
                    "company": item.get("company", "RemoteOK"),
                    "location": "Remote",
                    "description": item.get("description", item.get("position", "")),
                    "url": item.get("url") or f"https://remoteok.com{item.get('slug', '')}",
                    "source": "RemoteOK API"
                })
    except Exception as e:
        print(f"[-] RemoteOK Error: {e}")
    print(f"[*] RemoteOK: {len(jobs)} jobs (pre-filter)")
    return jobs


def fetch_arbeitnow_jobs():
    jobs = []
    try:
        res = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=10)
        if res.status_code == 200:
            for item in res.json().get("data", []):
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name", "Arbeitnow"),
                    "location": "Remote" if item.get("remote") else item.get("location", "N/A"),
                    "description": item.get("description", item.get("title", "")),
                    "url": item.get("url"),
                    "source": "Arbeitnow API"
                })
    except Exception as e:
        print(f"[-] Arbeitnow Error: {e}")
    print(f"[*] Arbeitnow: {len(jobs)} jobs (pre-filter)")
    return jobs


def fetch_jobicy_jobs():
    jobs = []
    try:
        res = requests.get("https://jobicy.com/api/v2/remote-jobs?count=50", timeout=10)
        if res.status_code == 200:
            for item in res.json().get("jobs", []):
                jobs.append({
                    "title": item.get("jobTitle", item.get("title", "")),
                    "company": item.get("companyName", "Jobicy"),
                    "location": "Remote",
                    "description": item.get("jobExcerpt", item.get("jobDescription", "")),
                    "url": item.get("url"),
                    "source": "Jobicy API"
                })
    except Exception as e:
        print(f"[-] Jobicy Error: {e}")
    print(f"[*] Jobicy: {len(jobs)} jobs (pre-filter)")
    return jobs


def fetch_weworkremotely_jobs():
    jobs = []
    import xml.etree.ElementTree as ET
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    ]
    for feed_url in feeds:
        try:
            res = requests.get(feed_url, timeout=10)
            if res.status_code != 200:
                continue
            root = ET.fromstring(res.content)
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = (item.findtext("description") or "").strip()
                if title and link:
                    jobs.append({
                        "title": title,
                        "company": "WeWorkRemotely",
                        "location": "Remote",
                        "description": desc if desc else title,
                        "url": link,
                        "source": "WeWorkRemotely RSS"
                    })
        except Exception as e:
            print(f"[-] WeWorkRemotely feed error ({feed_url}): {e}")
    print(f"[*] WeWorkRemotely: {len(jobs)} jobs (pre-filter)")
    return jobs


def fetch_cybersecurity_jobs():
    all_jobs = []

    # DDGS and Gemini Search are already security-targeted, so keep as-is.
    all_jobs.extend(fetch_ddgs_jobs())
    all_jobs.extend(fetch_gemini_jobs())

    # These are general job boards, so every job from them must pass a
    # security-relevance keyword filter before being added.
    general_sources = (
        fetch_remotive_jobs()
        + fetch_remoteok_jobs()
        + fetch_arbeitnow_jobs()
        + fetch_jobicy_jobs()
        + fetch_weworkremotely_jobs()
    )

    kept = 0
    for job in general_sources:
        title = (job.get("title") or "")
        desc = (job.get("description") or "")
        blob = (title + " " + desc).lower()
        if any(k in blob for k in SECURITY_KEYWORDS):
            all_jobs.append(job)
            kept += 1
    print(f"[*] General job boards: {kept}/{len(general_sources)} passed the security-keyword filter")

    # Dedup by URL across all sources.
    seen_urls = set()
    deduped = []
    for job in all_jobs:
        url = job.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(job)

    print(f"[*] Total unique jobs across all sources: {len(deduped)}")
    return deduped


def ai_batch_evaluate(jobs_batch):
    """Evaluate several jobs in ONE Gemini call instead of one call per job.
    This is what keeps us inside the free-tier daily request quota now that
    hundreds of candidate jobs are being collected per run. Returns a dict
    mapping batch-index -> {match, match_percent, fit_overview, cv_tip}."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[-] GEMINI_API_KEY missing — skipping AI evaluation batch (jobs rejected).")
        return {}

    listing = ""
    for i, job in enumerate(jobs_batch):
        desc = (job.get("description") or "")[:400]
        listing += f"\n[{i}] Title: {job['title']} | Company: {job.get('company','')}\nDescription: {desc}\n"

    prompt = f"""
    CANDIDATE RESUME:
    {RESUME_SUMMARY}

    Below is a numbered list of {len(jobs_batch)} job postings. For EACH one,
    decide if it's a realistic, worthwhile application for this candidate.

    STRICT RULES:
    1. REJECT (match=false) if the job requires Senior/Lead/Manager/Director
       level or years of professional experience the candidate doesn't have,
       or is unrelated to the candidate's skills (sales, HR, accounting, law,
       nursing, marketing, business development, patient care, etc.).
    2. ACCEPT (match=true) if it reasonably matches ANY cluster of the
       candidate's skills: SOC/blue team monitoring, incident response, log
       analysis, threat hunting/intel, IOC/MITRE ATT&CK, network security
       monitoring, vulnerability assessment, SIEM, or junior IT/security
       roles involving Python or Bash scripting.
    3. Judge fit against THIS resume specifically, not a generic checklist.

    JOB POSTINGS:
    {listing}

    Return ONLY a raw JSON array (no markdown fences, no commentary), with
    exactly one object per job IN ORDER, each with these keys:
    "index" (the number in brackets above),
    "match" (true or false),
    "match_percent" (integer 0-100, 0 if match is false),
    "fit_overview" (1 sentence, empty string if match is false),
    "cv_tip" (1 sentence naming a specific tool/cert/lab item from the resume, empty string if match is false)
    """

    for attempt in range(2):  # one retry on rate-limit errors
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            text = (response.text or "").strip()
            text = re.sub(r"^```(json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
            data = json.loads(text)
            results = {}
            for item in data:
                if isinstance(item, dict) and "index" in item:
                    results[item["index"]] = item
            return results
        except json.JSONDecodeError as e:
            print(f"[-] Batch eval returned non-JSON output: {e}")
            return {}
        except Exception as e:
            msg = str(e)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                if attempt == 0:
                    print("[-] Rate limited, waiting 20s and retrying batch once...")
                    time.sleep(20)
                    continue
                print(f"[-] Batch AI Agent Error (gave up after retry): {e}")
                return {}
            print(f"[-] Batch AI Agent Error: {e}")
            return {}
    return {}


def main():
    print("=== Expanded Cybersecurity & SOC AI Hunter Started ===")

    all_jobs = fetch_cybersecurity_jobs()
    print(f"[*] Total collected jobs to evaluate: {len(all_jobs)}")

    if not all_jobs:
        send_telegram_message("⚠️ Security Job Hunter ran, but no jobs were found.")
        return

    random.shuffle(all_jobs)
    all_jobs = all_jobs[:MAX_JOBS_TO_EVALUATE]
    # Pre-filter obviously irrelevant titles before spending any AI calls on them.
    all_jobs = [j for j in all_jobs if not any(w in (j.get("title") or "").lower() for w in EXCLUDE_TITLE_WORDS)]
    print(f"[*] Evaluating {len(all_jobs)} jobs with AI in batches of {EVAL_BATCH_SIZE}")

    matched_jobs = []
    for start in range(0, len(all_jobs), EVAL_BATCH_SIZE):
        if len(matched_jobs) >= 5:
            break
        batch = all_jobs[start:start + EVAL_BATCH_SIZE]
        results = ai_batch_evaluate(batch)
        for i, job in enumerate(batch):
            r = results.get(i)
            if r and r.get("match"):
                job["evaluation"] = (
                    f"MATCH_PERCENT: {r.get('match_percent', 0)}%\n"
                    f"ASSESSMENT:\n"
                    f"- {r.get('fit_overview', '')}\n"
                    f"- {r.get('cv_tip', '')}"
                )
                matched_jobs.append(job)
                if len(matched_jobs) >= 5:
                    break
        time.sleep(2)  # small pacing gap between batch calls

    if not matched_jobs:
        print("[-] No matching cybersecurity entry-level jobs found.")
        send_telegram_message("⚠️ Security Job Hunter ran, but all jobs were filtered out by the AI profile match.")
        return

    message = "🛡️ *Expanded Cybersecurity & SOC Job Opportunities* 🛡️\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *AI Description Analysis:*\n{job['evaluation']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"

    send_telegram_message(message)
    print("[+] Expanded cybersecurity results successfully sent to Telegram!")


if __name__ == "__main__":
    main()
