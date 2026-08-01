import os
import requests
import xml.etree.ElementTree as ET
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

def fetch_from_global_protected_web():
    """بحث متقدم عبر الويب يتجاوز الحظر ويستهدف المواقع العالمية، الخليج، كندا وأوروبا"""
    jobs = []
    
    # استعلامات دقيقة تستهدف الوظائف المخفية وصعبة الوصول للمبتدئين في الدول المستهدفة
    advanced_queries = [
        "site:linkedin.com/jobs 'junior cybersecurity analyst' OR 'SOC analyst' entry level remote OR UAE OR Canada OR Europe",
        "site:boards.greenhouse.io 'junior' OR 'entry level' cybersecurity OR network engineer OR python",
        "site:lever.co 'junior' python OR go developer OR SOC analyst remote OR Europe OR Canada",
        "junior cybersecurity analyst job openings Gulf Saudi UAE Qatar 2026",
        "entry level network engineer remote hiring Canada Estonia Poland Portugal"
    ]
    
    try:
        with DDGS() as ddgs:
            for q in advanced_queries:
                print(f"[*] Querying protected networks with: {q}")
                results = ddgs.text(q, max_results=4)
                for r in results:
                    url = r.get("href", "")
                    title = r.get("title", "")
                    body = r.get("body", "")
                    if url and title:
                        jobs.append({
                            "title": title,
                            "company": "Global / Protected Platform",
                            "location": "Gulf / Canada / Low-Competition Europe / Remote",
                            "description": body if body else title,
                            "url": url,
                            "source": "AI Web-Search Agent"
                        })
    except Exception as e:
        print(f"DuckDuckGo Advanced Search Error: {e}")
        
    return jobs

def ai_deep_evaluate_job(job_title, company, description):
    """وكيل تحليل ذكي يدرس الوظيفة ويطابقها مع مهاراتك"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "MATCH: 80%\n- Tech role match.\n- Check details."

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an advanced AI Career Agent for Moatez, a Junior Cybersecurity, SOC Analyst, Network Engineer, and Python/Go Developer.
        Analyze this job posting harvested from global protected boards, Gulf, Canadian, or low-competition European markets:
        
        Job Title: '{job_title}'
        Company: '{company}'
        Description: '{description[:600]}'
        
        STRICT RULES:
        1. REJECT immediately (output ONLY 'REJECT') if the job requires Senior, Lead, Manager, Director levels, or is completely non-tech (sales, HR, accounting, law, nursing).
        2. Prioritize Entry-level, Junior, or Intern roles in Cybersecurity, Networking, IT Support, or Scripting (Python/Go).
        
        If it is a great fit, output in this exact format:
        MATCH_PERCENT: [e.g., 90%]
        ASSESSMENT:
        - Fit Overview (1 smart sentence on why this suits a junior profile in this region)
        - CV Tip (1 actionable sentence to tailor the CV for this specific role)
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
    print("=== AI Protected-Web Job Hunter Started ===")
    
    # جلب الوظائف من أعماق الويب والمواقع العالمية المحمية
    all_jobs = fetch_from_global_protected_web()
    print(f"[*] Total harvested web jobs: {len(all_jobs)}")
    
    if not all_jobs:
        send_telegram_message("⚠️ AI Web Hunter ran, but no jobs were found.")
        return

    matched_jobs = []
    for job in all_jobs:
        title = job.get("title", "")
        company = job.get("company", "")
        
        # تصفية أولية سريعة
        if any(w in title.lower() for w in ["sales", "accountant", "nurse", "legal", "hr", "manager", "director", "senior", "lead", "principal"]):
            continue
            
        # التحليل العميق بالذكاء الاصطناعي
        evaluation = ai_deep_evaluate_job(title, company, job.get("description", ""))
        if evaluation:
            job["evaluation"] = evaluation
            matched_jobs.append(job)
            if len(matched_jobs) >= 5: # اختيار أفضل 5 فرص مطابقة بدقة
                break

    if not matched_jobs:
        print("[-] No matching entry-level tech jobs found after AI analysis.")
        send_telegram_message("⚠️ AI Web Hunter ran, but all harvested jobs were filtered out.")
        return

    message = "🌐 *AI Global & Protected-Web Job Hunter* 🌐\n\n"
    for i, job in enumerate(matched_jobs, 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Platform/Source: {job['source']}\n"
        message += f"📍 Region: {job['location']}\n"
        message += f"🤖 *AI Analysis:*\n{job['evaluation']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    send_telegram_message(message)
    print("[+] AI-harvested web results successfully sent to Telegram!")

if __name__ == "__main__":
    main()
