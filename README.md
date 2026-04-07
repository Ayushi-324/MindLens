# 🧠 MindLens — Cognitive Bias Detector

An advanced AI-powered critical thinking tool that identifies psychological shortcuts and logical fallacies in text. **MindLens** helps users deconstruct their decision-making process by quantifying the quality of their reasoning.

🚀 **[Live Demo](https://mindlens-app.onrender.com)**

---

### 💡 Features

* **Multidimensional Bias Detection:** Identifies 20+ types of cognitive biases (Sunk Cost, FOMO, Confirmation Bias, etc.) using Gemini 1.5 Flash.
* **Reasoning Quality Score:** Provides a quantitative 1-10 score based on objectivity and logical consistency.
* **Cognitive DNA Profile:** Aggregates your history to show your "most frequent" biases and provides tailored improvement tips.
* **Global Benchmarking:** Real-time comparison showing how your objectivity compares to the average MindLens user.
* **Interactive Reframing:** Don't just find the bias—learn how to fix it with AI-generated "How to Reframe" logic.

### 🛠️ Tech Stack

* **Backend:** FastAPI (Python)
* **AI:** Google Gemini Pro API
* **Database:** PostgreSQL (Production) / SQLAlchemy ORM
* **Security:** Rate limiting with SlowAPI & Environment Variable Protection
* **Frontend:** Modern Dark UI (HTML5, CSS3, JavaScript)

### 📸 How It Works

![MindLens Analysis Dashboard](https://raw.githubusercontent.com/Ayushi-324/MindLens/main/screenshot.png)

1. **Input:** Paste any argument, investment pitch, or decision-making text.
2. **Analyze:** The AI engine scans for emotional triggers and logical gaps.
3. **Result:** View your reasoning score and a breakdown of detected biases.
4. **Growth:** Visit the **Profile** tab to see your long-term cognitive patterns.

### 📦 Installation

```bash
# 1. Clone the repository
git clone [https://github.com/Ayushi-324/MindLens.git](https://github.com/Ayushi-324/MindLens.git)
cd MindLens

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up Environment Variables (.env)
# Create a .env file and add:
GEMINI_API_KEY="your_api_key_here"
DATABASE_URL="sqlite:///./mindlens.db" 

# 4. Run the application
uvicorn main:app --reload
📁 Project StructurePlaintextMindLens/
├── main.py           # FastAPI server & AI logic
├── database.py       # SQLAlchemy models & Database connection
├── index.html        # Single-page Application UI
├── requirements.txt  # Python dependencies
└── .gitignore        # Keeps API keys and DB files private
🌐 API EndpointsMethodEndpointDescriptionPOST/analyzeSubmits text for bias detection and scoringGET/history/{user}Retrieves past analysis for a specific userGET/profile/{user}Returns the "Cognitive DNA" stats for a userGET/global-insightsAggregates anonymized data for all usersGET/compare/{user}Calculates the "You vs Global" comparisonDeveloped by Ayushi Tyagi 🚀
