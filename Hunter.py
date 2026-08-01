import os
import random
import json
import re
import requests
from google import genai
from google.genai import types
from ddgs import DDGS

MAX_JOBS_TO_EVALUATE = 40  # cap AI calls per run now that many sources are combined

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
            model='gemini-2.5-flash',
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


def ai_deep_evaluate_job(job_title, company, description):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[-] GEMINI_API_KEY missing — skipping AI evaluation (job rejected).")
        return None  # do NOT fabricate a match; reject instead

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an advanced AI Career Agent working for the candidate described below.
        Compare the JOB POSTING against the CANDIDATE RESUME and decide if it's a
        realistic, worthwhile application for this specific person.

        CANDIDATE RESUME:
        {RESUME_SUMMARY}

        JOB POSTING:
        Title: '{job_title}'
        Company: '{company}'
        Description / Snippet: '{description[:900]}'

        STRICT RULES:
        1. REJECT immediately (output ONLY 'REJECT') if the job requires Senior, Lead, Manager,
           Director, or multiple years of professional experience the candidate doesn't have,
           or is completely unrelated to the candidate's skills (sales, HR, accounting, law,
           nursing, marketing, business development, patient care, content moderation, etc.).
        2. ACCEPT if the description reasonably matches ANY cluster of the candidate's skills:
           SOC/blue team monitoring, incident response, log analysis, threat hunting/intel,
           IOC/MITRE ATT&CK work, network security monitoring, vulnerability assessment, SIEM,
           or junior IT/security roles involving Python or Bash scripting.
        3. Judge fit against THIS resume specifically, not a generic cybersecurity checklist —
           reference the candidate's actual tools/certs/lab experience where relevant.

        If it matches, output in this exact format:
        MATCH_PERCENT: [e.g., 90%]
        ASSESSMENT:
        - Fit Overview (1 sentence on why this posting suits this specific candidate's resume)
        - CV Tip (1 actionable sentence on what from the resume — lab work, certs, tools — to highlight)
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip()
        if "REJECT" in text.upper():
            return None
        return text
    except Exception as e:
        print(f"AI Agent Error: {e}")
        return None  # fail closed, not a fake 80% match


def main():
    print("=== Expanded Cybersecurity & SOC AI Hunter Started ===")

    all_jobs = fetch_cybersecurity_jobs()
    print(f"[*] Total collected jobs to evaluate: {len(all_jobs)}")

    if not all_jobs:
        send_telegram_message("⚠️ Security Job Hunter ran, but no jobs were found.")
        return

    random.shuffle(all_jobs)
    all_jobs = all_jobs[:MAX_JOBS_TO_EVALUATE]  # cap AI calls now that sources are much larger
    print(f"[*] Evaluating up to {len(all_jobs)} jobs with AI")

    matched_jobs = []
    for job in all_jobs:
        title = job.get("title", "")
        company = job.get("company", "")

        if any(w in title.lower() for w in EXCLUDE_TITLE_WORDS):
            continue

        evaluation = ai_deep_evaluate_job(title, company, job.get("description", ""))
        if evaluation:
            job["evaluation"] = evaluation
            matched_jobs.append(job)
            if len(matched_jobs) >= 5:
                break

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
