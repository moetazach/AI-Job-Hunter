import os
import requests
from google import genai

def fetch_jobs_with_descriptions():
    jobs = []
    
    # 1. Arbeitnow (تتضمن أحياناً تفاصيل مختصرة أو الوصف الكامل)
    try:
        res = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=10)
        if res.status_code == 200:
            for item in res.json().get("data", []):
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": item.get("location", "Remote"),
                    "description": item.get("description", item.get("title")),
                    "url": item.get("url"),
                    "source": "Arbeitnow"
                })
    except Exception as e:
        print(f"Arbeitnow Error: {e}")

    # 2. RemoteOK
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get("https://remoteok.com/api", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for item in data[1:]:
                jobs.append({
                    "title": item.get("position"),
                    "company": item.get("company"),
                    "location": item.get("location", "Remote"),
                    "description": item.get("description", item.get("position")),
                    "url": item.get("url"),
                    "source": "RemoteOK"
                })
    except Exception as e:
        print(f"RemoteOK Error: {e}")

    # 3. Remotive
    try:
        res = requests.get("https://remotive.com/api/remote-jobs", timeout=10)
        if res.status_code == 200:
            for item in res.json().get("jobs", []):
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": "Remote",
                    "description": item.get("description", item.get("title")),
                    "url": item.get("url"),
                    "source": "Remotive"
                })
    except Exception as e:
        print(f"Remotive Error: {e}")

    return jobs

def deep_analyze_job_description(job_title, company, description):
    """قراءة وتحليل وصف الوظيفة بالكامل والتأكد من إمكانية التقديم عليها"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an expert AI Career Mentor for a Junior Cybersecurity, SOC, and Networking candidate based in Qatar.
        Candidate Profile:
        - Skills: Python, Go, Wireshark, Nmap, Networking, Home SOC Lab.
        - Level: Junior / Intern / Entry-level.
        
        Job Info:
        - Title: '{job_title}'
        - Company: '{company}'
        - Description snippet: '{description[:1500]}'
        
        Evaluate based on these strict criteria:
        1. Is it strictly a Junior, Entry-Level, or Internship role in Tech/Cyber/Networking/Development? (Reject Senior, Lead, Manager).
        2. Is it unrelated to non-tech fields (accounting, HR, sales, tax)?
        3. Can a remote junior or someone seeking an internship/entry role realistically apply based on the description requirements?
        
        Answer EXACTLY in this format:
        RELEVANT: [YES or NO]
        MATCH_PERCENT: [e.g., 85%]
        ASSESSMENT:
        - Fit & JD Analysis (1 short sentence explaining why the job description suits a junior)
        - CV Tip (1 short sentence)
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip()
        if "RELEVANT: YES" in text.upper():
            return text.split("MATCH_PERCENT:")[-1].strip()
        return None
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def send_telegram_message(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def main():
    print("=== JD-Analyzed Junior Tech Job Hunter ===")
    
    all_jobs = fetch_jobs_with_descriptions()
    print(f"[*] Total fetched jobs with descriptions: {len(all_jobs)}")
    
    matched_jobs = []
    
    global_skip_words = [
        "senior", "lead", "principal", "manager", "director", "steuerberater", 
        "sales", "hr", "recruiter", "accountant", "finance", "tax", "marketing"
    ]
    
    for job in all_jobs:
        title = job.get("title", "")
        title_lower = title.lower()
        
        if any(sw in title_lower for sw in global_skip_words):
            continue
            
        print(f"[*] Analyzing Job Description for: {title} at {job['company']}...")
        evaluation = deep_analyze_job_description(title, job['company'], job['description'])
        
        if evaluation:
            job["evaluation"] = evaluation
            matched_jobs.append(job)
            if len(matched_jobs) >= 3:
                break

    if not matched_jobs:
        print("[-] No matching junior jobs found after JD analysis.")
        return

    message = "🎯 *JD-Verified Junior Tech Jobs* 🎯\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *JD Analysis & Match:*\nMATCH_PERCENT: {job['evaluation']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] Verified jobs successfully sent to Telegram!")

if __name__ == "__main__":
    main()
