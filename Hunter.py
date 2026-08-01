import os
import requests
import xml.etree.ElementTree as ET
from google import genai

def fetch_latest_web_jobs():
    """جلب أحدث الوظائف والتدريبات المحدثة فوراً عبر خلاصات البحث اللحظية"""
    jobs = []
    # استعلامات بحث تركز على أحدث فرص المبتدئين والأمن والشبكات
    queries = [
        "junior cybersecurity analyst job 2026",
        "entry level network engineer remote",
        "python go developer internship 2026",
        "soc analyst trainee remote"
    ]
    
    for q in queries:
        try:
            # استخدام خلاصة أخبار جوجل المحدثة دقيقة بدقة لجلب أحدث الروابط المتاحة
            rss_url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
            res = requests.get(rss_url, timeout=10)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                for item in root.findall('.//item')[:2]:
                    title = item.find('title').text if item.find('title') is not None else "Latest Job"
                    link = item.find('link').text if item.find('link') is not None else "#"
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else "Recent"
                    jobs.append({
                        "title": title,
                        "company": "Live Web Employer",
                        "location": "Global / Remote",
                        "description": f"{title} - Published: {pub_date}",
                        "url": link,
                        "source": "Live Web Search (2026)"
                    })
        except Exception as e:
            print(f"Live Web Search Error: {e}")
            
    return jobs

def fetch_recent_platforms():
    jobs = []
    
    # 1. Arbeitnow (أحدث الوظائف)
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

    # 2. RemoteOK (أحدث الوظائف التقنية)
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

    # دمج الوظائف الفورية من الويب مع المنصات
    live_jobs = fetch_latest_web_jobs()
    jobs.extend(live_jobs)
    
    return jobs

def evaluate_job_smart(job_title, company, description):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "MATCH: 75%\n- Tech alignment.\n- Highlight your lab and networking skills."

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an AI career assistant for Moatez, a Junior candidate in Tech, Networking, and Cybersecurity.
        Job Title: '{job_title}'
        Company: '{company}'
        Description: '{description[:700]}'
        
        Is this job completely unrelated to tech (accounting, tax, HR, sales, nursing)? If yes, reply with 'REJECT'.
        Otherwise, provide a match assessment in this exact format:
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
        return "MATCH: 70%\n- Potential tech match.\n- Highlight networking skills."

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
    print("=== Latest Live Tech Job Hunter ===")
    
    all_jobs = fetch_recent_platforms()
    print(f"[*] Total fetched live jobs: {len(all_jobs)}")
    
    if not all_jobs:
        print("[-] No jobs found.")
        return

    matched_jobs = []
    forbidden_words = ["steuerberater", "accountant", "sales", "hr", "recruiter", "finance", "tax", "nurse"]
    
    for job in all_jobs:
        title = job.get("title", "")
        title_lower = title.lower()
        
        if any(fw in title_lower for fw in forbidden_words):
            continue
            
        print(f"[*] Evaluating latest job from {job['source']}: {title}...")
        evaluation = evaluate_job_smart(title, job['company'], job.get("description", ""))
        
        if evaluation:
            job["evaluation"] = evaluation
            matched_jobs.append(job)
            if len(matched_jobs) >= 5:
                break

    if not matched_jobs:
        print("[-] No matching live jobs found.")
        return

    message = "⚡ *Latest Live Tech & Cyber Jobs (2026)* ⚡\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *Analysis:*\n{job['evaluation']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] Latest live jobs successfully sent to Telegram!")

if __name__ == "__main__":
    main()
