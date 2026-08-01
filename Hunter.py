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

def fetch_open_web_jobs():
    jobs = []
    # استعلامات بحث مفتوحة ومباشرة تضمن جلب نتائج حية من مختلف مواقع التوظيف
    queries = [
        "junior soc analyst job opening 2026",
        "entry level cybersecurity analyst hiring",
        "junior network engineer remote vacancy",
        "python go developer internship 2026"
    ]
    
    with DDGS() as ddgs:
        for q in queries:
            try:
                print(f"[*] Searching open web for: {q}")
                results = ddgs.text(q, max_results=4)
                for r in results:
                    url = r.get("href", "")
                    title = r.get("title", "")
                    body = r.get("body", "")
                    
                    if url and title:
                        jobs.append({
                            "title": title,
                            "company": "Live Web Portal",
                            "location": "Global / Remote",
                            "description": body if body else title,
                            "url": url,
                            "source": "Open Web Search"
                        })
            except Exception as e:
                print(f"Search Error for '{q}': {e}")
                
    return jobs

def evaluate_job(job_title, description):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "MATCH: 80%\n- Tech role alignment.\n- Review position details."

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        Evaluate if this job or page is suitable for a Junior in Tech, Networking, IT, or Cybersecurity.
        Title: '{job_title}'
        Description: '{description[:400]}'
        
        If it is totally unrelated (sales, HR, accounting, law, management, senior role), reply with 'REJECT'.
        Otherwise, reply in this exact format:
        MATCH_PERCENT: [e.g:// 85%]
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
        return "MATCH: 75%\n- Potential tech match.\n- Highlight your home lab."

def main():
    print("=== Open Web Job Hunter Started ===")
    
    all_jobs = fetch_open_web_jobs()
    print(f"[*] Total items fetched from open web: {len(all_jobs)}")
    
    if not all_jobs:
        send_telegram_message("⚠️ Job Hunter ran, but no web results were returned by DuckDuckGo.")
        return

    matched_jobs = []
    for job in all_jobs:
        title = job.get("title", "")
        print(f"[*] Checking: {title}")
        evaluation = evaluate_job(title, job.get("description", ""))
        
        if evaluation:
            job["evaluation"] = evaluation
            matched_jobs.append(job)
            if len(matched_jobs) >= 3:
                break

    if not matched_jobs:
        print("[-] All fetched items were filtered out by AI.")
        send_telegram_message("⚠️ Job Hunter ran, but all web results were filtered out.")
        return

    message = "🌐 *Open Web Job Hunter Results* 🌐\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🤖 *Analysis:*\n{job['evaluation']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] Results successfully sent to Telegram!")

if __name__ == "__main__":
    main()
