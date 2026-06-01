import re


def _normalize(message):
    return re.sub(r"[^a-z0-9\s+#.]", " ", message.lower())


def _format_skills(skills):
    if not skills:
        return "I do not have skill context yet. Upload and analyze your resume first for tailored guidance."
    return ", ".join(skills[:8])


def _top_job_titles(recommendations, limit=3):
    jobs = []
    for job in recommendations[:limit]:
        title = job.get("job_title")
        percent = job.get("match_percent")
        if title and percent:
            jobs.append(f"{title} ({percent}% match)")
        elif title:
            jobs.append(title)
    return jobs


def _collect_missing_skills(recommendations, limit=8):
    missing = []
    for job in recommendations[:5]:
        for skill in job.get("missing_skills") or []:
            if skill not in missing:
                missing.append(skill)
            if len(missing) >= limit:
                return missing
    return missing


def get_chatbot_response(message, context=None):
    context = context or {}
    text = _normalize(message)
    tokens = set(text.split())
    resume_skills = context.get("resume_skills") or []
    recommendations = context.get("recommendations") or []
    top_job = recommendations[0] if recommendations else {}
    top_missing = top_job.get("missing_skills") or context.get("missing_skills") or []
    all_missing = _collect_missing_skills(recommendations)
    top_categories = []
    for job in recommendations[:5]:
        category = job.get("category")
        if category and category not in top_categories:
            top_categories.append(category)

    if tokens & {"hello", "hi", "hey"}:
        return "Hi, I am JobGenie. Upload a resume and I can explain your strongest job matches, missing skills, and next learning steps."

    if any(word in text for word in ["top job", "best job", "best jobs", "recommend", "match", "jobs for me"]):
        if top_job:
            job_list = _top_job_titles(recommendations)
            alternatives = ", ".join(job_list[1:])
            return (
                f"Your strongest current match is {job_list[0]}. Focus your applications around "
                f"{top_job.get('category')} roles and emphasize: {_format_skills(top_job.get('matched_skills') or [])}. "
                f"Good adjacent targets: {alternatives or 'similar roles in the same category'}."
            )
        return "Analyze a resume first, then I can identify your best-fit job titles and why they matched."

    if any(word in text for word in ["career path", "career paths", "path", "transition", "direction", "switch"]):
        if top_categories:
            return (
                f"Based on your resume, your strongest career paths are {', '.join(top_categories[:3])}. "
                "Apply first to the top-matching path, then use the missing-skill list as your learning roadmap. "
                "For a career switch, position your current skills as transferable proof and add one portfolio project in the target domain."
            )
        if resume_skills:
            return f"Your skills suggest a path around {_format_skills(resume_skills[:4])}. Run the resume analysis to rank exact job tracks."
        return "Upload your resume and I will map your strongest career paths from your detected skills."

    if any(word in text for word in ["missing", "gap", "improve", "learn", "skill"]):
        missing_skills = top_missing or all_missing
        if missing_skills:
            return (
                f"For your top matches, the biggest skill gaps are: {_format_skills(missing_skills)}. "
                "Pick the top two, build one small project for each, and add measurable outcomes to your resume."
            )
        if resume_skills:
            return (
                f"I found these resume skills: {_format_skills(resume_skills)}. "
                "To level up, add projects that combine your strongest skill with a measurable business outcome."
            )
        return "Upload your resume first so I can compare your skills against real job requirements."

    if any(word in text for word in ["resume mistakes", "mistakes"]):
        missing_hint = f" Also add evidence for {_format_skills(all_missing[:4])}." if all_missing else ""
        return (
            "The biggest resume mistakes are vague bullets, missing role keywords, no metrics, weak project links, and too much generic wording."
            f"{missing_hint} Rewrite bullets as action + tool + result, such as built X with Y to improve Z."
        )

    if any(word in text for word in ["resume review", "improve resume", "resume", "cv", "bullet", "ats"]):
        skill_line = f" Your detected strengths are {_format_skills(resume_skills)}." if resume_skills else ""
        return (
            "For a stronger ATS resume, use job-title keywords, quantify outcomes, keep bullets action-led, "
            "and mirror the most relevant skills from the target posting without exaggerating."
            f"{skill_line}"
        )

    if any(word in text for word in ["interview", "prepare", "questions"]):
        if top_job:
            return (
                f"Prepare for {top_job.get('job_title')} interviews by practicing one project walkthrough, "
                "one conflict story, one metrics story, and technical questions around the missing skills shown in your analysis. "
                "For HR rounds, prepare crisp answers for why this role, your strengths, a challenge, and salary expectations."
            )
        return (
            "For interviews, prepare STAR stories, a crisp project walkthrough, role-specific technical basics, "
            "and two questions to ask the interviewer about team goals and success metrics."
        )

    if any(word in text for word in ["salary", "pay", "compensation"]):
        title_hint = top_job.get("job_title") or "your target role"
        return (
            f"For {title_hint}, salary depends on location, seniority, and company stage. "
            "Use 3-5 market sources, define a target range before calls, and negotiate with proof: projects, metrics, certifications, and competing demand."
        )

    if any(word in text for word in ["data science", "data scientist", "analyst"]):
        return (
            "A practical Data Science roadmap: Python and SQL fundamentals, statistics, pandas/numpy, visualization, machine learning basics, "
            "one end-to-end project, deployment notes, then interview practice with case studies and SQL questions."
        )

    if any(word in text for word in ["roadmap", "learning roadmap", "plan", "30", "60", "90"]):
        missing_skills = top_missing or all_missing
        if missing_skills:
            return (
                f"30 days: refresh fundamentals for {_format_skills(missing_skills[:2])}. "
                "60 days: build a portfolio project using those skills. 90 days: tailor applications and practice interviews."
            )
        return "A strong 30-60-90 plan is: sharpen core skills, publish one relevant project, then apply with tailored resumes."

    if any(word in text for word in ["project", "projects", "ai ml", "machine learning project"]):
        skills = resume_skills[:4] or ["python", "sql", "machine learning"]
        return (
            f"Strong AI/ML portfolio projects for you: a resume-job matcher using {skills[0]}, a dashboard that explains model results, "
            "a chatbot over career documents, and a deployed prediction API with clean README, screenshots, and metrics."
        )

    if any(word in text for word in ["freelance", "freelancing", "client"]):
        return (
            "For freelancing, choose one clear niche, create 2 short case studies, publish a simple services page, "
            "send targeted proposals with a concrete outcome, and start with small fixed-scope projects before retainers."
        )

    return (
        "I can help with job matches, missing skills, resume improvement, interview prep, salary strategy, and learning roadmaps. "
        "Try asking: what skills should I improve?"
    )
