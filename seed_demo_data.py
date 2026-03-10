"""
Demo Data Seeder
================
Populates the database with realistic sample data for Lagos and Kano states
so that the analysis pipeline can produce a meaningful sample report.

This simulates what the scrapers would collect from Nairaland, Twitter, Reddit,
and Facebook when run with real API credentials.

Usage:
    python seed_demo_data.py         # Seed data then run full analysis pipeline
    python seed_demo_data.py --only   # Seed data only (no analysis)
"""

import sys
import os
import hashlib
import random
from datetime import datetime, timedelta

from storage.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


# Realistic sample posts for Lagos State
LAGOS_POSTS = [
    # --- Babajide Sanwo-Olu (incumbent, APC) ---
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Babajide Sanwo-Olu has done well with the Blue Line rail project. Lagos finally has a functioning metro system. This governor deserves credit for infrastructure development.",
        "likes": 45, "shares": 12,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "The Lagos governorship election is heating up. Sanwo-Olu campaign team is everywhere. APC is confident their candidate will win again.",
        "likes": 23, "shares": 8,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Traffic in Lagos under Sanwo-Olu is terrible. The governor promised BRT expansion but Eko bridge is still a nightmare every morning.",
        "likes": 67, "shares": 31,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Sanwo-Olu's education reforms are actually working. LASU ranking has improved and the free education policy helps many families. Credit to this governor.",
        "likes": 38, "shares": 15,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Babajide Sanwo-Olu is just another puppet of the godfathers. Nothing will change in Lagos until we break the APC stronghold. This candidate is not independent.",
        "likes": 89, "shares": 44,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "Lagos governor Babajide Sanwo-Olu inaugurated the new maternal health center in Epe. Good move for healthcare in the state. #LagosCares #Election2027",
        "likes": 156, "shares": 67,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "Flooding in Lekki AGAIN and Sanwo-Olu government has done nothing about drainage. Billions allocated but where are the results? #LagosFlooding",
        "likes": 234, "shares": 112,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "The governor Babajide Sanwo-Olu should be commended for the Lekki Deep Sea Port. It will transform trade and create jobs in Lagos. Great work on this project.",
        "likes": 89, "shares": 34,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "Sanwo-Olu administration demolished homes without adequate compensation. This is not what we voted for as governor. Where is the humanity? #LagosElection",
        "likes": 178, "shares": 89,
    },
    {
        "platform": "reddit", "state": "Lagos",
        "text": "I think Babajide Sanwo-Olu has been a decent governor for Lagos overall. The infrastructure push is real - blue line, red line construction ongoing, road repairs in Ikeja. Not perfect but better than most. What do you think about this candidate?",
        "likes": 34, "shares": 11,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "Sanwo-Olu's T.H.E.M.E.S agenda is showing results. Lagos GDP grew 4.2% this year. The governor is delivering on economic promises. APC candidate making moves.",
        "likes": 67, "shares": 23,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Security in Lagos has improved under Babajide Sanwo-Olu. The neighborhood safety corps and CCTV installations are helping. This governor takes safety seriously.",
        "likes": 29, "shares": 9,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Waste management is still a disaster under Sanwo-Olu. Heaps of refuse everywhere in Surulere and Mushin. The governorship candidate promised clean Lagos but failed to deliver.",
        "likes": 55, "shares": 22,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "People keep bashing Babajide Sanwo-Olu but the man has completed more projects than the last 3 governors combined. Lagos election 2027 - APC will win.",
        "likes": 112, "shares": 45,
    },
    {
        "platform": "reddit", "state": "Lagos",
        "text": "Honest question about the Lagos governorship election - has Sanwo-Olu actually reduced poverty in Lagos or is it just infrastructure projects for the rich? The candidate needs to address inequality.",
        "likes": 28, "shares": 7,
    },
    # --- Abdul-Azeez Adediran (Jandor, opposition) ---
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Abdul-Azeez Adediran better known as Jandor is preparing for 2027 governor race. His Lagos4Lagos movement brought fresh ideas. PDP candidate with grassroots support.",
        "likes": 34, "shares": 18,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Jandor lacks the experience and political machinery to win Lagos governorship. Abdul-Azeez Adediran should focus on building his base before contesting as candidate.",
        "likes": 41, "shares": 14,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Abdul-Azeez Adediran represents the voice of young Lagosians. His governorship campaign focuses on youth empowerment and digital economy. Fresh candidate for governor.",
        "likes": 56, "shares": 25,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "Jandor - Abdul-Azeez Adediran needs to present a clear economic plan for Lagos. Just criticizing APC won't win the governor election. PDP candidate must do better. #Lagos2027",
        "likes": 78, "shares": 32,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "If Abdul-Azeez Adediran can unite the opposition in Lagos, he has a real chance at the governorship. The candidate showed courage in 2023, needs to keep momentum for governor race.",
        "likes": 44, "shares": 20,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "The problem with Abdul-Azeez Adediran as a candidate is that PDP has no structure in Lagos. You need more than social media to win governor election. #LagosDecides",
        "likes": 95, "shares": 41,
    },
    {
        "platform": "reddit", "state": "Lagos",
        "text": "Abdul-Azeez Adediran (Jandor) is interesting as a governorship candidate. Young, articulate, good social media presence. But can he actually beat the Lagos APC machine for governor?",
        "likes": 19, "shares": 6,
    },
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Jandor Abdul-Azeez Adediran healthcare policy is actually comprehensive. Free primary healthcare for all Lagosians if elected governor. Good plan from this candidate.",
        "likes": 37, "shares": 16,
    },
    # --- General Lagos election posts ---
    {
        "platform": "nairaland", "state": "Lagos",
        "text": "Lagos governorship election 2027 will be the most competitive in history. Multiple strong candidates from APC, PDP, and LP. Who will be the next governor?",
        "likes": 78, "shares": 35,
    },
    {
        "platform": "twitter", "state": "Lagos",
        "text": "Lagos needs a governor who understands technology and can make the state a true smart city. The election candidates should present digital transformation plans. #Lagos2027",
        "likes": 134, "shares": 56,
    },
    {
        "platform": "reddit", "state": "Lagos",
        "text": "As a Lagos resident, I want the next governor to prioritize affordable housing. Rent is killing us. Which election candidate has the best housing policy?",
        "likes": 45, "shares": 12,
    },
]

# Realistic sample posts for Kano State
KANO_POSTS = [
    # --- Abba Kabir Yusuf (incumbent, NNPP) ---
    {
        "platform": "nairaland", "state": "Kano",
        "text": "Abba Kabir Yusuf is transforming Kano education sector. Free school feeding program and renovated classrooms across the state. This governor is working for the people.",
        "likes": 33, "shares": 14,
    },
    {
        "platform": "nairaland", "state": "Kano",
        "text": "Governor Abba Kabir Yusuf has improved water supply in rural Kano. Boreholes and water treatment plants serving millions. NNPP candidate delivered on promises.",
        "likes": 28, "shares": 11,
    },
    {
        "platform": "nairaland", "state": "Kano",
        "text": "Abba Kabir Yusuf governorship has been disappointing. No major infrastructure projects completed. Kano roads are still terrible. The governor needs to do more.",
        "likes": 52, "shares": 24,
    },
    {
        "platform": "twitter", "state": "Kano",
        "text": "Kano governor Abba Kabir Yusuf inaugurated the new technology hub in Nassarawa. This will attract tech investments and create jobs. Great move for election 2027. #KanoRising",
        "likes": 89, "shares": 37,
    },
    {
        "platform": "twitter", "state": "Kano",
        "text": "The security situation in Kano under Abba Kabir Yusuf is concerning. Rising banditry in outskirts. The governor must address this before the next election. NNPP candidate needs action.",
        "likes": 112, "shares": 55,
    },
    {
        "platform": "nairaland", "state": "Kano",
        "text": "Abba Kabir Yusuf government spent billions on road construction in Kano. Zaria Road and Maiduguri Road now in good shape. This governor is a builder and strong candidate.",
        "likes": 44, "shares": 19,
    },
    {
        "platform": "twitter", "state": "Kano",
        "text": "Healthcare in Kano has improved under governor Abba Kabir Yusuf. New primary health centers opened. Maternal mortality rate dropping. Real progress from this candidate.",
        "likes": 67, "shares": 28,
    },
    {
        "platform": "reddit", "state": "Kano",
        "text": "What do Kano residents think of Abba Kabir Yusuf as governor? Is NNPP delivering or just riding on Kwankwaso's popularity? Genuine question about this candidate for the election.",
        "likes": 15, "shares": 4,
    },
    {
        "platform": "nairaland", "state": "Kano",
        "text": "Corruption allegations against Abba Kabir Yusuf administration are troubling. N2 billion contract scandal needs investigation. This governor must be transparent for the election.",
        "likes": 76, "shares": 38,
    },
    {
        "platform": "twitter", "state": "Kano",
        "text": "Abba Kabir Yusuf has restored Kano's dignity as a commercial center. Trade volume with Niger Republic increased 30%. Smart governor, strong election candidate. #Kano2027",
        "likes": 45, "shares": 18,
    },
    # --- Nasiru Gawuna (APC opposition) ---
    {
        "platform": "nairaland", "state": "Kano",
        "text": "Nasiru Gawuna is preparing a strong comeback for the 2027 Kano governorship. APC candidate has been building grassroots support. Will he contest as governor again?",
        "likes": 38, "shares": 16,
    },
    {
        "platform": "nairaland", "state": "Kano",
        "text": "Gawuna's agriculture policy when he was deputy governor was excellent. Nasiru Gawuna understands farming communities. APC needs this candidate for the Kano governor election.",
        "likes": 29, "shares": 10,
    },
    {
        "platform": "twitter", "state": "Kano",
        "text": "Nasiru Gawuna needs to differentiate himself from Ganduje's legacy. APC candidate for Kano governor must show he is his own man. #KanoElection2027",
        "likes": 56, "shares": 23,
    },
    {
        "platform": "nairaland", "state": "Kano",
        "text": "If Nasiru Gawuna wins the APC primary for Kano governorship, it will be a tough contest. This candidate has the party structure but not the popular support for governor.",
        "likes": 42, "shares": 17,
    },
    {
        "platform": "reddit", "state": "Kano",
        "text": "Nasiru Gawuna vs Abba Kabir Yusuf for Kano governor in 2027 would be a rematch. Both candidates have strengths. Who do you think wins the election?",
        "likes": 22, "shares": 8,
    },
    {
        "platform": "twitter", "state": "Kano",
        "text": "Nasiru Gawuna's campaign team launched a comprehensive manifesto for Kano. Focus on industrialization and education. Serious APC candidate for governor election.",
        "likes": 34, "shares": 14,
    },
    # --- General Kano election posts ---
    {
        "platform": "nairaland", "state": "Kano",
        "text": "Kano governorship election 2027 will be a three-way race between NNPP, APC, and PDP. The emirate crisis adds another dimension. Who will be the next governor candidate?",
        "likes": 65, "shares": 29,
    },
    {
        "platform": "twitter", "state": "Kano",
        "text": "Kano state needs a governor who can manage both traditional institutions and modern development. Election candidates must address the emirate issue carefully.",
        "likes": 88, "shares": 42,
    },
    {
        "platform": "reddit", "state": "Kano",
        "text": "Kano is the most politically complex state in Nigeria. The governor race will depend on which candidate can balance the Kwankwasiyya movement with APC structure. Thoughts on the election?",
        "likes": 31, "shares": 9,
    },
]


def _anonymize_author():
    """Generate a realistic anonymized author hash."""
    fake_name = f"user_{random.randint(1000, 9999)}_{random.randint(1, 100)}"
    return hashlib.sha256(fake_name.encode()).hexdigest()[:16]


def _random_date(months_back=12):
    """Generate a random date within the past N months."""
    days_back = random.randint(1, months_back * 30)
    date = datetime.now() - timedelta(days=days_back)
    return date.strftime("%Y-%m-%d")


def seed_database():
    """Insert sample data into the database."""
    # Remove old database to start fresh
    db_path = "output/data/election_data.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"Removed old database: {db_path}")

    db = Database()

    all_posts = LAGOS_POSTS + KANO_POSTS
    for post in all_posts:
        post["author"] = _anonymize_author()
        post["date"] = _random_date()
        post["url"] = f"https://{post['platform']}.com/post/{random.randint(100000, 999999)}"
        post["keyword_used"] = f"{post['state']} governorship election"

    db.save_posts(all_posts)
    logger.info(f"Seeded {len(all_posts)} sample posts ({len(LAGOS_POSTS)} Lagos, {len(KANO_POSTS)} Kano)")

    db.close()
    return len(all_posts)


if __name__ == "__main__":
    seed_database()

    if "--only" not in sys.argv:
        print("\nRunning analysis pipeline on seeded data...\n")
        from main import run_analysis, generate_reports
        profiles = run_analysis()
        generate_reports(profiles)
        print("\nDone! Check output/ directory for results.")
    else:
        print("Data seeded. Run 'python main.py --skip-scraping' to analyze.")
