import os
import requests

# === إعدادات الكلمات المفتاحية للأمن السيبراني ===
CYBER_KEYWORDS = [
    "security", "cyber", "soc", "analyst", "pentest", 
    "infosec", "vulnerability", "incident", "threat", "gnoc"
]

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

def send_telegram_message(message):
    """إرسال الرسالة عبر بوت تيليجرام"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("[-] Telegram credentials not found in environment variables.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("[+] Telegram message sent successfully!")
        else:
            print(f"[-] Failed to send Telegram message: {response.text}")
    except Exception as e:
        print(f"[-] Error sending Telegram message: {e}")

def main():
    print("=== AI Job Hunter (Telegram Integrated) ===")
    
    # جلب الوظائف
    all_jobs = fetch_arbeitnow_jobs() + fetch_remoteok_jobs()
    print(f"[+] Total raw jobs fetched: {len(all_jobs)}")
    
    # فلترة وظائف الأمن السيبراني
    filtered_jobs = []
    for job in all_jobs:
        title = job.get("title", "").lower()
        if any(keyword in title for keyword in CYBER_KEYWORDS):
            filtered_jobs.append(job)
            
    print(f"[+] Filtered cybersecurity jobs: {len(filtered_jobs)}")
    
    if not filtered_jobs:
        print("[-] No matching cybersecurity jobs found today.")
        return

    # إعداد رسالة تيليجرام
    message = "🚨 *AI Job Hunter - New Cybersecurity Jobs* 🚨\n\n"
    for i, job in enumerate(filtered_jobs[:10], 1):
        message += f"*{i}. {job['title']}*\n"
        message += f"🏢 Company: {job['company']}\n"
        message += f"📍 Location: {job['location']}\n"
        message += f"🌐 Source: {job['source']}\n"
        message += f"🔗 [Apply Here]({job['url']})\n\n"
    
    # إرسال النتائج عبر البوت
    send_telegram_message(message)

if __name__ == "__main__":
    main()
