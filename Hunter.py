import os
import requests
from google import genai

def fetch_jobs():
    """جلب الوظائف من المنصات العالمية للبحث عن فرص Remote ومبتدئين"""
    jobs = []
    
    # 1. Arbeitnow (أوروبا والعالم)
    try:
        res = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=10)
        if res.status_code == 200:
            for item in res.json().get("data", []):
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": item.get("location", "Remote"),
                    "url": item.get("url"),
                    "source": "Arbeitnow"
                })
    except Exception as e:
        print(f"Arbeitnow Error: {e}")

    # 2. RemoteOK (وظائف عن بعد عالمية)
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
                    "url": item.get("url"),
                    "source": "RemoteOK"
                })
    except Exception as e:
        print(f"RemoteOK Error: {e}")

    # 3. Remotive (وظائف تقنية وأمنية عن بعد)
    try:
        res = requests.get("https://remotive.com/api/remote-jobs", timeout=10)
        if res.status_code == 200:
            for item in res.json().get("jobs", []):
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": "Remote",
                    "url": item.get("url"),
                    "source": "Remotive"
                })
    except Exception as e:
        print(f"Remotive Error: {e}")

    return jobs

def evaluate_job_with_gemini(job_title, company, location):
    """تقييم الوظيفة وحساب نسبة التطابق مع تركيز على Juniors والـ Remote وحالة قطر"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "MATCH: 75%\n- Potential entry-level match.\n- Tailor CV for tech roles."

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an expert AI Career Mentor for a candidate based in Qatar, seeking Junior / Internship roles in Cybersecurity, SOC, Network Engineering, or IT Support, with a preference for Remote or roles providing relocation/sponsorship.
        
        Candidate Profile:
        - Location: Qatar
        - Education: Senior Technician in Intelligent Systems & Industrial Computing, Computer Networking diploma.
        - Skills: Python, Go, Wireshark, Nmap, Nuclei, Shodan, Packet Tracer, Home SOC Lab.
        
        Job Details:
        - Title: '{job_title}'
        - Company: '{company}'
        - Location: '{location}'
        
        Evaluate this job and provide:
        MATCH_PERCENT: [e.g., 85%]
        ASSESSMENT:
        - Fit Overview (1 short sentence explaining why it fits a junior profile / remote / Qatar market)
        - Actionable CV Tip (1 short sentence)
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return "MATCH: 70%\n- Good technical match for entry-level.\n- Highlight your lab and networking skills."

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
    print("=== Targeted Junior & Remote Job Hunter ===")
    
    all_jobs = fetch_jobs()
    print(f"[*] Total fetched jobs: {len(all_jobs)}")
    
    if not all_jobs:
        print("[-] No jobs found.")
        return

    # كلمات مفتاحية تستهدف المبتدئين، التدريب، الأمن، والشبكات
    target_keywords = [
        "junior", "intern", "internship", "entry", "trainee", 
        "security", "cyber", "soc", "analyst", "network", "support", "it"
    ]
    
    matched_jobs = []
    
    for job in all_jobs:
        title = job.get("title", "")
        title_lower = title.lower()
        
        # اختيار الوظائف التي تحتوي على كلمات مفتاحية لمستوى مبتدئ أو أمن/شبكات
        if any(kw in title_lower for kw in target_keywords):
            print(f"[*] Analyzing: {title} at {job['company']}...")
            analysis = evaluate_job_with_gemini(title, job['company'], job['location'])
            job["analysis"] = analysis
            matched_jobs.append(job)
            
            if len(matched_jobs) >= 4:  # جلب أفضل 4 فرص مطابقة في كل عملية تشغيل
                break

    if not matched_jobs:
        # إذا لم يجد كلمات مطابقة تماماً، يأخذ أول 3 وظائف كاحتياط
        for job in all_jobs[:3]:
            job["analysis"] = evaluate_job_with_gemini(job['title'], job['company'], job['location'])
            matched_jobs.append(job)

    message = "🎯 *Junior & Remote Cyber/Tech Job Hunter* 🎯\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *AI Analysis & Match:*\n{job['analysis']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] Targeted jobs analyzed and sent to Telegram!")

if __name__ == "__main__":
    main()
