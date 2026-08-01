import os
import requests
from google import genai
from duckduckgo_search import DDGS

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

def fetch_cybersecurity_jobs():
    jobs = []
    
    # قائمة موسعة جداً تضم عشرات المسميات الوظيفية للمبتدئين في الأمن السيبراني والشبكات
    keywords = [
        "junior cybersecurity analyst remote OR Gulf OR Canada",
        "SOC analyst tier 1 entry level hiring",
        "junior network security engineer remote",
        "cybersecurity intern python go security",
        "junior incident responder remote Europe Canada",
        "information security analyst junior",
        "junior vulnerability analyst remote",
        "cyber security specialist entry level",
        "network administrator junior security",
        "IT security graduate program Gulf Europe"
    ]
    
    try:
        with DDGS() as ddgs:
            for q in keywords:
                print(f"[*] Searching security roles for: {q}")
                results = ddgs.text(q, max_results=3)
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
                            "source": "DDGS Security Search"
                        })
    except Exception as e:
        print(f"Search Error: {e}")

    # خطة بديلة لجلب وظائف إضافية في حال احتاج النظام نتائج أوسع
    if len(jobs) < 5:
        print("[*] Fetching fallback tech jobs from Remotive API...")
        try:
            res = requests.get("https://remotive.com/api/remote-jobs?category=software-dev&limit=15", timeout=10)
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
            print(f"API Fallback Error: {e}")

    return jobs

def ai_deep_evaluate_job(job_title, company, description):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "MATCH: 80%\n- Cybersecurity role match.\n- Check details."

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an advanced AI Career Agent for Moatez, a Junior Cybersecurity, SOC Analyst, Network Security, and Python/Go Developer.
        Analyze this job posting meticulously based on its JOB DESCRIPTION and Title:
        
        Job Title: '{job_title}'
        Company: '{company}'
        Full Description / Snippet: '{description[:700]}'
        
        STRICT RULES:
        1. REJECT immediately (output ONLY 'REJECT') if the job requires Senior, Lead, Manager, Director levels, or is completely non-tech (sales, HR, accounting, law, nursing).
        2. Even if the title is generic, if the JOB DESCRIPTION mentions security monitoring, logs, SOC, firewalls, network packet analysis, Python/Go scripting, or entry-level IT/security tasks, ACCEPT IT.
        3. Prioritize Cybersecurity, SOC Analyst, Network Security, and Junior IT/Scripting roles.
        
        If it matches, output in this exact format:
        MATCH_PERCENT: [e.g., 90%]
        ASSESSMENT:
        - Fit Overview (1 smart sentence on why the job description suits a junior cybersecurity/SOC profile)
        - CV Tip (1 actionable sentence on what to highlight from home labs or certifications)
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
        return None

def main():
    print("=== Expanded Cybersecurity & SOC AI Hunter Started ===")
    
    all_jobs = fetch_cybersecurity_jobs()
    print(f"[*] Total collected jobs to evaluate: {len(all_jobs)}")
    
    if not all_jobs:
        send_telegram_message("⚠️ Security Job Hunter ran, but no jobs were found.")
        return

    matched_jobs = []
    for job in all_jobs:
        title = job.get("title", "")
        company = job.get("company", "")
        
        if any(w in title.lower() for w in ["sales", "accountant", "nurse", "legal", "hr", "manager", "director", "senior", "lead", "principal"]):
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
