import os
import requests
from google import genai
from duckduckgo_search import DDGS

def fetch_duckduckgo_jobs():
    """البحث الحقيقي والمباشر في الإنترنت عبر DuckDuckGo دون أي مفاتيح"""
    jobs = []
    queries = [
        "junior cybersecurity analyst job 2026",
        "entry level network engineer remote",
        "python go developer internship 2026",
        "soc analyst trainee remote"
    ]
    
    with DDGS() as ddgs:
        for q in queries:
            try:
                # جلب أحدث نتائج البحث (الروابط والعناوين)
                results = ddgs.text(q, max_results=3)
                for r in results:
                    jobs.append({
                        "title": r.get("title"),
                        "company": "Web / Direct Search",
                        "location": "Global / Remote",
                        "description": r.get("body", r.get("title")),
                        "url": r.get("href"),
                        "source": "DuckDuckGo Web Search"
                    })
            except Exception as e:
                print(f"DuckDuckGo Error for '{q}': {e}")
                
    return jobs

def strict_evaluate_job(job_title, company, description):
    """فلترة صارمة بالذكاء الاصطناعي لضمان مطابقة التخصص"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are a strict AI career filter for Moatez, a Junior Cybersecurity, SOC, and Networking candidate.
        Job Title: '{job_title}'
        Company: '{company}'
        Description: '{description[:800]}'
        
        STRICT RULES:
        1. The job MUST be strictly related to Cybersecurity, SOC, Network Engineering, IT Support, or Python/Go Development.
        2. REJECT immediately (output ONLY 'REJECT') if the job is Senior, Manager, or non-tech (accounting, HR, sales, law, agriculture).
        
        If it passes, output in this exact format:
        MATCH_PERCENT: [e.g., 85%]
        ASSESSMENT:
        - Fit Overview (1 short sentence)
        - CV Tip (1 short sentence)
        
        If it fails, output ONLY 'REJECT'.
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
    print("=== DuckDuckGo Web Search Job Hunter ===")
    
    all_jobs = fetch_duckduckgo_jobs()
    print(f"[*] Total web results fetched: {len(all_jobs)}")
    
    if not all_jobs:
        print("[-] No jobs found.")
        return

    matched_jobs = []
    for job in all_jobs:
        title = job.get("title", "")
        print(f"[*] Evaluating: {title}...")
        evaluation = strict_evaluate_job(title, job['company'], job.get("description", ""))
        
        if evaluation:
            job["evaluation"] = evaluation
            matched_jobs.append(job)
            if len(matched_jobs) >= 4:
                break

    if not matched_jobs:
        print("[-] No matching tech jobs found.")
        return

    message = "🦆 *DuckDuckGo Web Search Jobs* 🦆\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *Analysis:*\n{job['evaluation']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] DuckDuckGo verified jobs sent to Telegram!")

if __name__ == "__main__":
    main()
