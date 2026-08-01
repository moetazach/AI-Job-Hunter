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

def strict_cyber_networking_evaluation(job_title, company, description):
    """فلترة ذكية وصارمة تقبل حصرياً الأمن السيبراني، الشبكات، الدعم التقني، أو تطوير Python/Go للمبتدئين"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are a strict AI career filter for Moatez, a Junior Cybersecurity, SOC, and Networking candidate based in Qatar.
        Skills: Python, Go, Wireshark, Nmap, Networking, Home SOC Lab.
        
        Job Title: '{job_title}'
        Company: '{company}'
        Description: '{description[:800]}'
        
        STRICT EVALUATION RULES:
        1. The job MUST be related to Cybersecurity, SOC, Network Engineering, IT Support, or Python/Go development.
        2. REJECT immediately (output 'REJECT') if the job is:
           - Senior, Lead, Manager, or Director level.
           - Product Designer, UI/UX, or Designer.
           - Agriculture, farming, manufacturing, mechanical, accounting, HR, sales, or non-tech fields.
           - Web development in languages other than Python/Go (like generic frontend/PHP unless clearly entry-level tech, but prefer security/networks).
        
        If it passes, output in this exact format:
        MATCH_PERCENT: [e.g., 85%]
        ASSESSMENT:
        - Fit Overview (1 short sentence why it fits a junior security/networking profile)
        - CV Tip (1 short sentence)
        
        If it fails any rule, output ONLY the word 'REJECT'.
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
    print("=== Strict Cyber & Network Job Hunter ===")
    
    all_jobs = fetch_jobs()
    print(f"[*] Total fetched jobs: {len(all_jobs)}")
    
    if not all_jobs:
        print("[-] No jobs found.")
        return

    matched_jobs = []
    
    # قائمة حظر فورية للعناوين غير المرغوبة لتوفير الوقت
    forbidden_words = [
        "senior", "lead", "manager", "director", "designer", "vorarbeiter", 
        "brüterei", "steuerberater", "accountant", "sales", "hr", "nurse"
    ]
    
    for job in all_jobs:
        title = job.get("title", "")
        title_lower = title.lower()
        
        if any(fw in title_lower for fw in forbidden_words):
            continue
            
        print(f"[*] Strictly evaluating: {title} at {job['company']}...")
        evaluation = strict_cyber_networking_evaluation(title, job['company'], job.get("description", ""))
        
        if evaluation:
            job["evaluation"] = evaluation
            matched_jobs.append(job)
            if len(matched_jobs) >= 3:
                break

    if not matched_jobs:
        print("[-] No matching cyber/network jobs found in this run.")
        return

    message = "🛡️ *Pure Cyber & Network Junior Jobs* 🛡️\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *Analysis:*\n{job['evaluation']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] Clean cyber/network jobs sent to Telegram!")

if __name__ == "__main__":
    main()
