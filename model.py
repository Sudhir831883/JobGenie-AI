import re
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


REQUIRED_COLUMNS = ["job_title", "job_description", "skills", "category", "location"]

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off",
    "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "you", "your", "yours", "yourself",
    "yourselves", "will", "work", "working", "team", "teams", "role", "roles",
}

SKILL_KEYWORDS = {
    "python": ["python"],
    "sql": ["sql", "mysql", "postgresql", "postgres", "sqlite"],
    "excel": ["excel", "spreadsheets", "spreadsheet"],
    "tableau": ["tableau"],
    "power bi": ["power bi", "powerbi"],
    "statistics": ["statistics", "statistical analysis", "hypothesis testing"],
    "data visualization": ["data visualization", "visualization", "dashboards", "dashboard"],
    "data cleaning": ["data cleaning", "data wrangling", "etl"],
    "machine learning": ["machine learning", "ml", "predictive modeling"],
    "deep learning": ["deep learning", "neural networks", "cnn", "rnn", "transformers"],
    "nlp": ["nlp", "natural language processing", "language models"],
    "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch", "torch"],
    "scikit learn": ["scikit learn", "scikit-learn", "sklearn"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "flask": ["flask"],
    "django": ["django"],
    "fastapi": ["fastapi"],
    "react": ["react", "reactjs"],
    "angular": ["angular"],
    "vue": ["vue", "vuejs"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "html": ["html"],
    "css": ["css", "scss", "sass"],
    "node.js": ["node.js", "nodejs", "node"],
    "express": ["express"],
    "java": ["java"],
    "spring boot": ["spring boot", "spring"],
    "c#": ["c#", "c sharp", ".net", "dotnet"],
    "go": ["golang", "go"],
    "rust": ["rust"],
    "php": ["php", "laravel"],
    "api design": ["api design", "rest", "restful", "graphql", "apis"],
    "microservices": ["microservices", "service mesh"],
    "docker": ["docker", "containers", "containerization"],
    "kubernetes": ["kubernetes", "k8s"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure"],
    "gcp": ["gcp", "google cloud"],
    "terraform": ["terraform"],
    "linux": ["linux", "bash", "shell scripting"],
    "ci cd": ["ci cd", "ci/cd", "github actions", "jenkins", "gitlab ci"],
    "devops": ["devops"],
    "site reliability": ["site reliability", "sre", "observability"],
    "prometheus": ["prometheus"],
    "grafana": ["grafana"],
    "security": ["security", "cybersecurity"],
    "network security": ["network security", "firewalls", "ids", "ips"],
    "penetration testing": ["penetration testing", "ethical hacking", "burp suite"],
    "siem": ["siem", "splunk", "sentinel"],
    "risk assessment": ["risk assessment", "threat modeling"],
    "incident response": ["incident response"],
    "product management": ["product management", "product strategy"],
    "roadmapping": ["roadmapping", "roadmap"],
    "user research": ["user research", "customer discovery", "interviews"],
    "agile": ["agile", "scrum", "kanban"],
    "jira": ["jira"],
    "figma": ["figma"],
    "ux design": ["ux design", "user experience", "wireframing", "prototyping"],
    "ui design": ["ui design", "visual design", "design systems"],
    "accessibility": ["accessibility", "wcag", "a11y"],
    "seo": ["seo", "search engine optimization"],
    "content marketing": ["content marketing", "copywriting", "editorial"],
    "google analytics": ["google analytics", "ga4"],
    "crm": ["crm", "salesforce", "hubspot"],
    "lead generation": ["lead generation", "prospecting"],
    "customer success": ["customer success", "account management"],
    "project management": ["project management", "program management"],
    "stakeholder management": ["stakeholder management", "communication"],
    "financial modeling": ["financial modeling", "valuation"],
    "accounting": ["accounting", "gaap"],
    "forecasting": ["forecasting", "budgeting"],
    "quality assurance": ["quality assurance", "qa", "test plans"],
    "selenium": ["selenium"],
    "playwright": ["playwright"],
    "mobile development": ["mobile development", "android", "ios"],
    "swift": ["swift"],
    "kotlin": ["kotlin"],
    "react native": ["react native"],
    "flutter": ["flutter", "dart"],
    "blockchain": ["blockchain", "web3"],
    "solidity": ["solidity", "smart contracts"],
    "healthcare analytics": ["healthcare analytics", "clinical data", "ehr"],
    "bioinformatics": ["bioinformatics", "genomics"],
    "supply chain": ["supply chain", "logistics"],
    "robotics": ["robotics", "ros"],
    "computer vision": ["computer vision", "opencv", "image processing"],
    "unity": ["unity"],
    "unreal engine": ["unreal engine", "unreal"],
}

SUGGESTIONS = {
    "python": "Build two portfolio projects in Python and show clean notebooks or APIs on GitHub.",
    "sql": "Practice joins, window functions, and query optimization on realistic business datasets.",
    "machine learning": "Create an end-to-end ML project with feature engineering, validation, and deployment notes.",
    "react": "Ship a responsive React interface with routing, state management, and API integration.",
    "aws": "Deploy one app on AWS using IAM, storage, compute, logging, and cost controls.",
    "docker": "Containerize an app and document local development plus production build commands.",
    "kubernetes": "Practice deployments, services, config maps, health checks, and autoscaling basics.",
    "figma": "Create a polished case study showing wireframes, component states, and design rationale.",
    "product management": "Write a product brief with problem framing, metrics, roadmap, and tradeoffs.",
    "security": "Document threat models, secure coding decisions, and incident response exercises.",
    "tableau": "Publish a dashboard with filters, calculated fields, and a short insight narrative.",
    "power bi": "Build a Power BI report that includes data modeling, DAX measures, and drilldowns.",
    "ci cd": "Set up automated linting, testing, and deployment for one public project.",
}


def clean_text(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9+#.\s/-]", " ", text)
    text = re.sub(r"[/_-]+", " ", text)
    tokens = re.findall(r"[a-z0-9+#.]+", text)
    tokens = [token for token in tokens if token not in STOPWORDS and len(token) > 1]
    return " ".join(tokens)


def extract_skills(text):
    normalized = f" {clean_text(text)} "
    compact = normalized.replace(".", " ")
    skills = set()

    for canonical, variants in SKILL_KEYWORDS.items():
        for variant in variants:
            cleaned_variant = clean_text(variant)
            if not cleaned_variant:
                continue
            if f" {cleaned_variant} " in compact:
                skills.add(canonical)
                break

    return sorted(skills)


def parse_skill_column(skills_text):
    parts = re.split(r"[;,|]", str(skills_text or ""))
    extracted = set()
    for part in parts:
        skill = clean_text(part).strip()
        if skill:
            canonical = extract_skills(skill)
            extracted.update(canonical or {skill})
    extracted.update(extract_skills(skills_text))
    return sorted(extracted)


class JobRecommendationEngine:
    def __init__(self, dataset_path):
        self.dataset_path = Path(dataset_path)
        self.df = self._load_and_preprocess_dataset()
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        self.job_matrix = self.vectorizer.fit_transform(self.df["model_text"])

    def _load_and_preprocess_dataset(self):
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found at {self.dataset_path}")

        df = pd.read_csv(self.dataset_path)
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing_columns:
            raise ValueError(f"dataset.csv is missing required columns: {missing_columns}")

        df = df[REQUIRED_COLUMNS].dropna()
        df = df.drop_duplicates()

        for column in REQUIRED_COLUMNS:
            df[column] = df[column].astype(str).str.lower().str.strip()
            df[column] = df[column].str.replace(r"[^a-z0-9+#.,;:/\s-]", " ", regex=True)
            df[column] = df[column].str.replace(r"\s+", " ", regex=True).str.strip()

        df = df[df["job_description"].str.len() > 30].copy()
        df["clean_description"] = df["job_description"].apply(clean_text)
        df["clean_title"] = df["job_title"].apply(clean_text)
        df["clean_category"] = df["category"].apply(clean_text)
        df["skill_list"] = df.apply(
            lambda row: sorted(
                set(parse_skill_column(row["skills"]))
                | set(extract_skills(row["job_description"]))
                | set(extract_skills(row["job_title"]))
            ),
            axis=1,
        )
        df["clean_skills"] = df["skill_list"].apply(lambda skills: " ".join(skills))
        df["model_text"] = (
            df["clean_title"]
            + " "
            + df["clean_description"]
            + " "
            + df["clean_skills"]
            + " "
            + df["clean_category"]
        )

        if df.empty:
            raise ValueError("dataset.csv did not contain usable job rows after cleaning.")

        print("DEBUG dataset rows loaded:", len(df))
        return df.reset_index(drop=True)

    def recommend(self, resume_text, top_n=5):
        cleaned_resume = clean_text(resume_text)
        resume_skills = set(extract_skills(resume_text))
        resume_vector = self.vectorizer.transform([cleaned_resume + " " + " ".join(resume_skills)])
        similarities = cosine_similarity(resume_vector, self.job_matrix).flatten()

        scored_jobs = []
        for index, row in self.df.iterrows():
            job_skills = set(row["skill_list"])
            overlap = resume_skills & job_skills
            skill_score = len(overlap) / len(job_skills) if job_skills else 0
            semantic_score = float(similarities[index])
            combined_score = (0.68 * semantic_score) + (0.32 * skill_score)

            scored_jobs.append(
                {
                    "index": index,
                    "combined_score": combined_score,
                    "semantic_score": semantic_score,
                    "skill_score": skill_score,
                    "overlap": sorted(overlap),
                    "missing": sorted(job_skills - resume_skills),
                }
            )

        top_jobs = sorted(scored_jobs, key=lambda item: item["combined_score"], reverse=True)[:top_n]

        recommendations = []
        all_missing = set()
        all_matched = set()

        for item in top_jobs:
            row = self.df.iloc[item["index"]]
            missing_skills = item["missing"][:8]
            all_missing.update(missing_skills)
            all_matched.update(item["overlap"])
            match_percent = round(min(98.0, max(1.0, item["combined_score"] * 100)), 1)
            recommendations.append(
                {
                    "job_title": row["job_title"].title(),
                    "category": row["category"].title(),
                    "location": row["location"].title(),
                    "job_description": row["job_description"],
                    "skills": row["skill_list"],
                    "matched_skills": item["overlap"],
                    "missing_skills": missing_skills,
                    "match_percent": match_percent,
                    "semantic_score": round(item["semantic_score"] * 100, 1),
                    "skill_score": round(item["skill_score"] * 100, 1),
                    "suggestions": [
                        SUGGESTIONS.get(skill, f"Add a practical project or certification that demonstrates {skill}.")
                        for skill in missing_skills[:4]
                    ],
                }
            )

        top_labels = [job["job_title"] for job in recommendations]
        top_scores = [job["match_percent"] for job in recommendations]
        resume_skill_count = len(resume_skills)
        missing_count = len(all_missing)
        matched_count = len(all_matched)

        return {
            "resume_skills": sorted(resume_skills),
            "recommendations": recommendations,
            "chart_data": {
                "bar": {
                    "labels": top_labels,
                    "scores": top_scores,
                },
                "pie": {
                    "labels": ["Matched skills", "Missing skills", "Resume-only skills"],
                    "values": [
                        matched_count,
                        missing_count,
                        max(0, resume_skill_count - matched_count),
                    ],
                },
            },
            "summary": {
                "dataset_rows": len(self.df),
                "resume_skill_count": resume_skill_count,
                "top_match": top_scores[0] if top_scores else 0,
                "most_relevant_category": recommendations[0]["category"] if recommendations else "Unknown",
            },
        }

    def search_jobs(self, query, limit=8):
        cleaned_query = clean_text(query)
        query_skills = set(extract_skills(query))
        if not cleaned_query and not query_skills:
            return []

        query_tokens = set(cleaned_query.split())
        results = []

        for index, row in self.df.iterrows():
            searchable_text = row["model_text"]
            job_skills = set(row["skill_list"])
            token_hits = sum(1 for token in query_tokens if token in searchable_text)
            skill_hits = len(query_skills & job_skills)
            title_hit = 2 if cleaned_query and cleaned_query in row["clean_title"] else 0
            category_hit = 1 if cleaned_query and cleaned_query in row["clean_category"] else 0
            score = token_hits + (skill_hits * 3) + title_hit + category_hit

            if score <= 0:
                continue

            results.append(
                {
                    "score": int(score),
                    "job_title": row["job_title"].title(),
                    "category": row["category"].title(),
                    "location": row["location"].title(),
                    "job_description": row["job_description"],
                    "skills": row["skill_list"][:10],
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def search_suggestions(self, query, limit=8):
        cleaned_query = clean_text(query)
        if not cleaned_query:
            return []

        suggestions = {}
        query_tokens = set(cleaned_query.split())

        def add_suggestion(label, suggestion_type, score):
            key = (label.lower(), suggestion_type)
            if key not in suggestions or score > suggestions[key]["score"]:
                suggestions[key] = {
                    "label": label,
                    "type": suggestion_type,
                    "score": int(score),
                }

        for _, row in self.df.iterrows():
            title = row["job_title"].title()
            category = row["category"].title()
            title_clean = row["clean_title"]
            category_clean = row["clean_category"]

            if cleaned_query in title_clean or query_tokens & set(title_clean.split()):
                add_suggestion(title, "job title", 10 if cleaned_query in title_clean else 6)

            if cleaned_query in category_clean or query_tokens & set(category_clean.split()):
                add_suggestion(category, "category", 8 if cleaned_query in category_clean else 5)

            for skill in row["skill_list"]:
                skill_clean = clean_text(skill)
                if cleaned_query in skill_clean or query_tokens & set(skill_clean.split()):
                    add_suggestion(skill.title(), "skill", 9 if cleaned_query in skill_clean else 5)

        ordered = sorted(
            suggestions.values(),
            key=lambda item: (-item["score"], item["type"], item["label"]),
        )
        return ordered[:limit]
