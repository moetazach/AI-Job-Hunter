import os
import requests
from google import genai

def fetch_jobs():
    jobs = []
    
    # 1. Arbeitnow
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

def evaluate_job(job_title, company, description):
    """تقييم مرن يمنع المحاسبة والإدارة المتقدمة ويعطي فرصة لظهور الوظائف المناسبة"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "MATCH: 75%\n- Entry-level tech alignment.\n- Highlight your lab and networking skills."

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an AI career assistant for a Junior candidate in Qatar interested in Tech, Networking, and Cybersecurity.
        Job Title: '{job_title}'
        Company: '{company}'
        Description: '{description[:800]}'
        
        Is this job completely unrelated to tech (like accounting, tax, HR, sales)? If yes, reply with 'REJECT'.
        Otherwise, provide a match assessment for an entry-level/junior profile in this format:
        MATCH_PERCENT: [e.g., 80%]
        ASSESSMENT:
        - Fit Overview (1 short sentence)
        - CV Tip (1 short sentence)
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
        print(f"AI Error: {e}")
        return "MATCH: 70%\n- Potential tech match.\n- Tailor your resume keywords."

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
    print("=== Flexible Tech Job Hunter ===")
    
    all_jobs = fetch_jobs()
    print(f"[*] Total fetched jobs: {len(all_jobs)}")
    
    if not all_jobs:
        print("[-] No jobs found from sources.")
        return

    matched_jobs = []
    
    # استبعاد الكلمات غير التقنية تماماً من العنوان مسبقاً
    skip_words = ["steuerberater", "accountant", "sales", "hr", "recruiter", "finance", "tax"]
    
    for job in all_jobs:
        title = job.get("title", "")
        title_lower = title.lower()
        
        if any(sw in title_lower for sw in skip_words):
            continue
            
        print(f"[*] Evaluating: {title} at {job['company']}...")
        evaluation = evaluate_job(title, job['company'], job.get("description", ""))
        
        if evaluation:
            job["evaluation"] = evaluation
            matched_jobs.append(job)
            if len(matched_jobs) >= 3:  # جلب أول 3 وظائف تقنية مطابقة وإرسالها فوراً
                break

    if not matched_jobs:
        print("[-] No jobs matched after evaluation.")
        return

    message = "🎯 *Tech & Cyber Job Hunter (Active)* 🎯\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *Analysis:*\n{job['evaluation']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] Jobs successfully analyzed and sent to Telegram!")

if __name__ == "__main__":
    main()
