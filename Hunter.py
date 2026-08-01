import os
import requests
from google import genai

def fetch_arbeitnow_jobs():
    """جلب الوظائف من منصة Arbeitnow"""
    url = "https://www.arbeitnow.com/api/job-board-api"
    jobs = []
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", [])
            for item in data:
                jobs.append({
                    "title": item.get("title"),
                    "company": item.get("company_name"),
                    "location": item.get("location"),
                    "url": item.get("url"),
                    "source": "Arbeitnow"
                })
    except Exception as e:
        print(f"Error fetching Arbeitnow: {e}")
    return jobs

def fetch_remoteok_jobs():
    """جلب الوظائف من منصة RemoteOK"""
    url = "https://remoteok.com/api"
    jobs = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data[1:]:
                jobs.append({
                    "title": item.get("position"),
                    "company": item.get("company"),
                    "location": item.get("location", "Remote"),
                    "url": item.get("url"),
                    "source": "RemoteOK"
                })
    except Exception as e:
        print(f"Error fetching RemoteOK: {e}")
    return jobs

def smart_filter_and_analyze_with_gemini(job_title, company):
    """استخدام Gemini كفلتر ذي صلة ومقييم للوظيفة"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an expert AI Cybersecurity Career Mentor and strict filter.
        Evaluate the job title: '{job_title}' at company '{company}'.
        
        Is this job strictly relevant to Cybersecurity, Information Security, SOC Analyst, Network Security, Incident Response, or Penetration Testing?
        
        Answer EXACTLY in this format:
        RELEVANT: [YES or NO]
        INSIGHTS:
        - Fit Score & Match Assessment (1 short sentence)
        - Key CV tip for this role (1 short sentence)
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        result_text = response.text.strip()
        
        if "RELEVANT: YES" in result_text.upper():
            # استخراج النص الخاص بالتحليلات فقط
            insights = result_text.split("INSIGHTS:")[-1].strip()
            return insights
        return None
    except Exception as e:
        print(f"AI Filter Error: {e}")
        return None

def send_telegram_message(message):
    """إرسال الرسالة عبر بوت تيليجرام"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("[-] Telegram credentials not found.")
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
        print(f"[-] Telegram Error: {e}")

def main():
    print("=== AI Cyber Job Hunter (Gemini Smart Filter) ===")
    
    all_jobs = fetch_arbeitnow_jobs() + fetch_remoteok_jobs()
    print(f"[*] Total fetched jobs: {len(all_jobs)}")
    
    matched_jobs = []
    
    # نفحص الوظائف ونترك الذكاء الاصطناعي يختار الوظائف الأمنية بدقة
    for job in all_jobs:
        title = job.get("title", "")
        company = job.get("company", "")
        
        # فحص أولي سريع للكلمات الأمنية لتوفير استهلاك الـ API
        cyber_clues = ["security", "cyber", "soc", "analyst", "infosec", "threat", "vulnerability", "incident", "pentest", "network"]
        if not any(clue in title.lower() for clue in cyber_clues):
            continue
            
        print(f"[*] AI Analyzing: {title} at {company}...")
        ai_insights = smart_filter_and_analyze_with_gemini(title, company)
        
        if ai_insights:
            job["insights"] = ai_insights
            matched_jobs.append(job)
            # نكتفي بأفضل 3 وظائف مطابقة تماماً في كل تشغيل
            if len(matched_jobs) >= 3:
                break

    if not matched_jobs:
        print("[-] No matching cybersecurity jobs found in this run.")
        return

    message = "🛡️ *AI Cyber Job Hunter - SOC & Security Roles* 🛡️\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *AI Insights:*\n{job['insights']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] Cyber job hunting and smart AI filtering completed successfully!")

if __name__ == "__main__":
    main()
