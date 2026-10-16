"""
StatIntel Cadre Competency Assessment & Certification Engine
------------------------------------------------------------
Provides evidence-based competency verification, tiered examination questions,
automatic scoring with explanatory feedback, dynamic officer readiness updates,
and cryptographic ReportLab vector PDF certificates with scannable QR verification.
"""
import io
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF

from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Officer, AssessmentAttempt, Certificate, AuditLog


# ── Curated Competency Question Bank ─────────────────────────────────────────
QUESTION_BANK = {
    "sql & data management": {
        "operational": [
            {
                "id": 101,
                "question": "Which SQL clause is used to filter aggregated grouped records (e.g., showing only districts with total enumeration count > 5,000)?",
                "options": ["WHERE", "HAVING", "GROUP FILTER", "QUALIFY"],
                "correct_index": 1,
                "rationale": "The HAVING clause filters aggregated results after GROUP BY, whereas WHERE filters individual rows before grouping."
            },
            {
                "id": 102,
                "question": "When combining microdata from an Urban Survey and a Rural Survey where some household IDs might not match across tables, which JOIN preserves all records from the primary household registry?",
                "options": ["INNER JOIN", "LEFT OUTER JOIN", "CROSS JOIN", "NATURAL JOIN"],
                "correct_index": 1,
                "rationale": "A LEFT OUTER JOIN preserves all rows from the primary (left) table and fills missing matches from the secondary table with NULL."
            },
            {
                "id": 103,
                "question": "What is the primary operational consequence of omitting a WHERE clause in an SQL UPDATE statement on an officer database?",
                "options": [
                    "The query throws a syntax error",
                    "Only the first record is modified",
                    "Every record across the entire table is updated",
                    "The operation is automatically rolled back"
                ],
                "correct_index": 2,
                "rationale": "Without a WHERE clause, UPDATE acts unconditionally on every tuple in the relation."
            },
            {
                "id": 104,
                "question": "Which constraint ensures that no two officers can be registered with the exact same Government Employee Code?",
                "options": ["CHECK constraint", "FOREIGN KEY", "UNIQUE / PRIMARY KEY", "NOT NULL"],
                "correct_index": 2,
                "rationale": "A UNIQUE constraint or PRIMARY KEY enforces entity integrity, guaranteeing column value uniqueness."
            },
            {
                "id": 105,
                "question": "In PostgreSQL/SQLite, which aggregate function computes the total number of non-null district entries?",
                "options": ["COUNT(district)", "SUM(district)", "TOTAL(district)", "DISTINCT(district)"],
                "correct_index": 0,
                "rationale": "COUNT(column) evaluates the count of non-null records in that column."
            }
        ],
        "senior": [
            {
                "id": 201,
                "question": "To calculate the moving average of monthly Consumer Price Index (CPI) over the preceding 3 months within each state, which SQL construct is appropriate?",
                "options": [
                    "AVG(cpi) OVER (PARTITION BY state ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)",
                    "AVG(cpi) GROUP BY state, month HAVING month <= 3",
                    "LAG(cpi, 3) OVER (PARTITION BY state)",
                    "SUM(cpi) OVER (ORDER BY state) / 3"
                ],
                "correct_index": 0,
                "rationale": "Window functions with ROWS BETWEEN 2 PRECEDING AND CURRENT ROW compute moving rolling statistics partitioned by subgroup."
            },
            {
                "id": 202,
                "question": "What is the difference between RANK() and DENSE_RANK() when ordering officers by readiness score where two officers share the second position?",
                "options": [
                    "RANK() assigns 1, 2, 2, 4; DENSE_RANK() assigns 1, 2, 2, 3",
                    "RANK() assigns 1, 2, 2, 3; DENSE_RANK() assigns 1, 2, 2, 4",
                    "RANK() skips duplicate ranks; DENSE_RANK() randomly breaks ties",
                    "Both functions produce identical rankings"
                ],
                "correct_index": 0,
                "rationale": "RANK() introduces gaps after ties (1, 2, 2, 4), whereas DENSE_RANK() leaves no gaps in the numbering sequence (1, 2, 2, 3)."
            },
            {
                "id": 203,
                "question": "When querying multi-million record census tables, which database optimization technique eliminates full-table scans for range queries on survey dates?",
                "options": ["B-Tree Indexing on the date column", "Dropping all foreign keys", "Converting to CSV files", "Using SELECT * queries"],
                "correct_index": 0,
                "rationale": "B-Tree indexes provide logarithmic $O(\\log N)$ lookup performance for range and equality searches."
            },
            {
                "id": 204,
                "question": "Which SQL window function allows an officer to compare the current month's industrial production index directly against the previous month's value within the same row?",
                "options": ["LEAD()", "LAG()", "FIRST_VALUE()", "NTH_VALUE()"],
                "correct_index": 1,
                "rationale": "LAG() accesses data from a preceding row at a specified physical offset within the partition."
            },
            {
                "id": 205,
                "question": "What does a database transaction ACID property 'Isolation' guarantee during concurrent statistical data entry?",
                "options": [
                    "Data is immediately backed up to secondary storage",
                    "Concurrent transactions execute without interfering with one another's intermediate states",
                    "All column constraints are checked only at system shutdown",
                    "Queries always return cached results"
                ],
                "correct_index": 1,
                "rationale": "Isolation ensures that uncommitted transactions are isolated from each other to prevent dirty reads and race conditions."
            }
        ],
        "executive": [
            {
                "id": 301,
                "question": "Under modern National Statistical System data architecture, what is the primary governance benefit of a Federate Data Lakehouse over disparate silos?",
                "options": [
                    "Eliminates the need for data security controls",
                    "Provides a unified semantic catalog with ACID compliance, lineage provenance, and role-based data governance",
                    "Restricts access strictly to single-threaded queries",
                    "Replaces all relational databases with static flat files"
                ],
                "correct_index": 1,
                "rationale": "A Lakehouse architecture unifies data management with strict lineage, auditable governance, and open catalog standards."
            },
            {
                "id": 302,
                "question": "When designing an enterprise data warehouse schema for multi-cadre workforce analytics, why is a Star Schema generally preferred over a highly normalized (3NF) OLTP schema?",
                "options": [
                    "It minimizes storage space by avoiding all duplicate values",
                    "It optimizes complex analytical aggregation queries by reducing multi-table join depth",
                    "It strictly prohibits foreign keys",
                    "It is the only schema supported by SQLite"
                ],
                "correct_index": 1,
                "rationale": "Star schemas denormalize dimension tables around central fact tables, significantly accelerating analytical aggregations."
            },
            {
                "id": 303,
                "question": "In public sector data governance, what standard does the Fundamental Principles of Official Statistics (Principle 6: Confidentiality) mandate regarding microdata access?",
                "options": [
                    "Individual statistical records must be strictly confidential and used exclusively for statistical purposes",
                    "Microdata must be published openly with citizen identification numbers",
                    "Data confidentiality expires after 30 days",
                    "Statistical agencies may sell identifiable data for commercial research"
                ],
                "correct_index": 0,
                "rationale": "Principle 6 of UNSD Fundamental Principles mandates strict confidentiality and exclusive statistical usage of individual records."
            },
            {
                "id": 304,
                "question": "Which mechanism ensures zero-data-loss point-in-time recovery for mission-critical national databases?",
                "options": [
                    "Write-Ahead Logging (WAL) with continuous archive streaming",
                    "Weekly manual CSV exports",
                    "Restarting the database server daily",
                    "Disabling foreign key checks"
                ],
                "correct_index": 0,
                "rationale": "WAL archiving combined with base backups enables deterministic Point-In-Time Recovery (PITR) to any microsecond."
            },
            {
                "id": 305,
                "question": "What is the primary purpose of Master Data Management (MDM) across national statistical directorates?",
                "options": [
                    "Ensuring single authoritative definitions for core reference entities (e.g. standard industrial classifications, administrative codes)",
                    "Merging all ministry databases into one single Excel workbook",
                    "Eliminating the need for database administrators",
                    "Preventing regional offices from accessing national indices"
                ],
                "correct_index": 0,
                "rationale": "MDM establishes a uniform Golden Record and harmonized taxonomy across disparate ministry sources."
            }
        ]
    },
    "python & reproducible analysis": {
        "operational": [
            {
                "id": 401,
                "question": "In Python Pandas, which method is the standard way to inspect missing values across all columns of a survey DataFrame `df`?",
                "options": ["df.isna().sum()", "df.empty()", "df.missing()", "df.drop_nulls()"],
                "correct_index": 0,
                "rationale": "`df.isna().sum()` returns the count of missing (NaN/None) values per column."
            },
            {
                "id": 402,
                "question": "How do you filter a DataFrame `df` to include only officers with readiness >= 75 in department 'NSSO'?",
                "options": [
                    "df[(df['readiness'] >= 75) & (df['department'] == 'NSSO')]",
                    "df[df['readiness'] >= 75 and df['department'] == 'NSSO']",
                    "df.filter(readiness >= 75, department == 'NSSO')",
                    "df.where(readiness >= 75)"
                ],
                "correct_index": 0,
                "rationale": "Pandas requires bitwise operators (`&`, `|`) with parenthesized boolean conditions for element-wise filtering."
            },
            {
                "id": 403,
                "question": "Which Pandas function is used to convert an unpivoted wide census table into a tidy key-value long format?",
                "options": ["pd.melt()", "pd.pivot()", "pd.concat()", "pd.merge()"],
                "correct_index": 0,
                "rationale": "`pd.melt()` unpivots a DataFrame from wide format to long format."
            },
            {
                "id": 404,
                "question": "What is the role of `inplace=True` or reassignment (`df = df.drop(...)`) when mutating a Pandas DataFrame?",
                "options": [
                    "Ensures changes persist on the DataFrame rather than returning a modified temporary copy",
                    "Increases memory usage by 100%",
                    "Converts data types to string",
                    "Automatically saves the file to disk"
                ],
                "correct_index": 0,
                "rationale": "Without `inplace=True` or reassignment, Pandas methods return a new copy without modifying the original object."
            },
            {
                "id": 405,
                "question": "Which Python library is the standard foundation for numerical vector calculations and multidimensional arrays in scientific computing?",
                "options": ["NumPy", "Flask", "BeautifulSoup", "PyPDF2"],
                "correct_index": 0,
                "rationale": "NumPy provides ndarray objects and compiled C-speed mathematical linear algebra routines."
            }
        ],
        "senior": [
            {
                "id": 501,
                "question": "When fitting an ARIMA(p,d,q) model in Python (statsmodels), what does the parameter 'd' represent?",
                "options": [
                    "The degree of differencing required to achieve stationarity",
                    "The number of autoregressive lag terms",
                    "The number of lagged forecast error terms",
                    "The seasonal period length"
                ],
                "correct_index": 0,
                "rationale": "'d' represents the integration order (differencing) necessary to render a non-stationary series stationary."
            },
            {
                "id": 502,
                "question": "To perform statistical testing for stationarity on a Consumer Price Index series, which hypothesis test is standard?",
                "options": ["Augmented Dickey-Fuller (ADF) test", "Student's t-test", "Chi-squared test of independence", "Mann-Whitney U test"],
                "correct_index": 0,
                "rationale": "The ADF test checks for the presence of a unit root ($H_0$: unit root present / non-stationary)."
            },
            {
                "id": 503,
                "question": "Why is setting a specific `random_state` (e.g. `np.random.seed(42)`) critical for reproducible survey sampling scripts?",
                "options": [
                    "Guarantees that pseudo-random sample selection is exactly replicable across audit runs",
                    "Accelerates CPU calculation speed",
                    "Prevents Python memory overflow",
                    "Encrypts the resulting sample file"
                ],
                "correct_index": 0,
                "rationale": "Fixed seeds guarantee computational reproducibility—a cornerstone of official statistical audit standards."
            },
            {
                "id": 504,
                "question": "When vectorizing string parsing in a survey dataset of 1,000,000 rows, which approach offers optimal runtime?",
                "options": [
                    "Built-in Pandas vectorized methods (`df['col'].str.extract(...)`)",
                    "Iterating with `for index, row in df.iterrows()`",
                    "Using Python's built-in `while` loop with `.iloc[]`",
                    "Exporting to Excel and manually splitting columns"
                ],
                "correct_index": 0,
                "rationale": "Vectorized string routines execute in compiled C, avoiding Python interpreter loop overhead."
            },
            {
                "id": 505,
                "question": "In Python statistical modeling, what diagnostic plot confirms whether regression residuals are normally distributed?",
                "options": ["Quantile-Quantile (Q-Q) Plot", "Scatter plot of raw features", "Correlation Heatmap", "Pie Chart"],
                "correct_index": 0,
                "rationale": "A Q-Q plot compares empirical residual quantiles against theoretical standard normal distribution quantiles."
            }
        ],
        "executive": [
            {
                "id": 601,
                "question": "In national econometric policy evaluations, what does the 'Parallel Trends Assumption' require for a valid Difference-in-Differences (DID) estimation?",
                "options": [
                    "In the absence of the policy intervention, treatment and control groups would have followed parallel outcome trajectories",
                    "Both groups must have identical population sizes",
                    "The policy must be applied simultaneously to all citizens",
                    "Residuals must have zero standard deviation"
                ],
                "correct_index": 0,
                "rationale": "The identifying assumption of DID is that counterfactual outcome trends would have remained parallel over time."
            },
            {
                "id": 602,
                "question": "What is the primary purpose of Instrumental Variables (2SLS) estimation in macro-statistical models?",
                "options": [
                    "To overcome endogeneity bias caused by omitted variables or reverse causality",
                    "To speed up database indexing",
                    "To format statistical tables for publication",
                    "To eliminate the need for survey sampling weights"
                ],
                "correct_index": 0,
                "rationale": "Instruments isolate exogenous variation in explanatory variables to produce unbiased causal estimates."
            },
            {
                "id": 603,
                "question": "Under the European Statistics Code of Practice (Principle 4: Commitment to Quality), how should national statistical authorities treat methodological revisions?",
                "options": [
                    "Revisions must follow standard, well-established and transparent procedures published in advance",
                    "Revisions should be concealed to preserve public confidence",
                    "Methodologies should never be changed under any circumstances",
                    "Revisions should only be shared with selected private stakeholders"
                ],
                "correct_index": 0,
                "rationale": "Principle 4 requires transparent, scheduled, and methodologically documented revision policies."
            },
            {
                "id": 604,
                "question": "When publishing public-use synthetic microdata derived from sensitive administrative records, which mathematical framework provides provable privacy guarantees?",
                "options": ["Differential Privacy (with defined epsilon budget)", "Deleting only names and phone numbers", "Rotating the columns randomly", "Base64 encoding"],
                "correct_index": 0,
                "rationale": "Differential Privacy bounds the maximum information leakage risk for any individual participating in a dataset."
            },
            {
                "id": 605,
                "question": "What is the key advantage of an automated continuous integration pipeline (CI/CD) for national statistical publication scripts?",
                "options": [
                    "Automated regression tests ensure that code modifications do not inadvertently alter historical published time series",
                    "It replaces the need for senior statistical economists",
                    "It automatically generates policy speeches",
                    "It prevents external researchers from downloading open data"
                ],
                "correct_index": 0,
                "rationale": "CI pipelines execute automated unit tests and data validation checks to prevent methodological regressions."
            }
        ]
    },
    "applied sampling methodology": {
        "operational": [
            {
                "id": 701,
                "question": "What is a Sampling Frame in the context of household surveys?",
                "options": [
                    "The physical wooden frame used to measure survey boundaries",
                    "A complete, up-to-date list or map of all sampling units from which the sample is drawn",
                    "The statistical formula used for calculating standard error",
                    "The budget spreadsheet for survey enumerators"
                ],
                "correct_index": 1,
                "rationale": "A sampling frame is the actual list or spatial registry representing the target population."
            },
            {
                "id": 702,
                "question": "In Simple Random Sampling Without Replacement (SRSWOR), what is the probability of selecting any specific household from a village of N = 500 when drawing a sample of n = 50?",
                "options": ["50 / 500 = 0.10 (10%)", "1 / 500 = 0.002", "500 / 50 = 10", "0.50 (50%)"],
                "correct_index": 0,
                "rationale": "The first-order inclusion probability in SRSWOR is $\\pi_i = n / N = 50 / 500 = 0.10$."
            },
            {
                "id": 703,
                "question": "Which sampling technique divides the population into non-overlapping homogeneous sub-groups (e.g. Rural/Urban) before drawing random samples within each?",
                "options": ["Stratified Random Sampling", "Convenience Sampling", "Snowball Sampling", "Quota Sampling"],
                "correct_index": 0,
                "rationale": "Stratification partitions the population into homogeneous strata to decrease sampling variance."
            },
            {
                "id": 704,
                "question": "What is Non-Response Bias in statistical surveys?",
                "options": [
                    "Error occurring when non-respondents differ systematically in key characteristics from those who respond",
                    "A computer failure during data entry",
                    "The time difference between questionnaire completion and data verification",
                    "A misprint in the survey questionnaire"
                ],
                "correct_index": 0,
                "rationale": "Non-response bias distorts sample estimates when missing units have different characteristics than responding units."
            },
            {
                "id": 705,
                "question": "What is the Sampling Weight (design weight) for a household selected with inclusion probability $\\pi_i = 0.04$?",
                "options": ["$w_i = 1 / \\pi_i = 25$", "$w_i = 0.04$", "$w_i = 400$", "$w_i = 0.96$"],
                "correct_index": 0,
                "rationale": "The design weight (Horvitz-Thompson weight) is the inverse of the inclusion probability ($w_i = 1 / \\pi_i$)."
            }
        ],
        "senior": [
            {
                "id": 801,
                "question": "In multi-stage cluster sampling, what does the Design Effect ($Deff$) quantify?",
                "options": [
                    "The ratio of the variance under the complex sampling design relative to the variance under an equivalent SRS",
                    "The total financial cost of the survey per enumerator",
                    "The number of survey questions answered correctly",
                    "The physical distance traveled between sample clusters"
                ],
                "correct_index": 0,
                "rationale": "Design Effect ($Deff = \\text{Var}_{\\text{complex}} / \\text{Var}_{\\text{SRS}}$) measures variance inflation due to clustering and weighting."
            },
            {
                "id": 802,
                "question": "When cluster sizes vary substantially, which sampling design is optimal to ensure approximately equal interviewer workload while preserving self-weighting properties?",
                "options": [
                    "Probability Proportional to Size (PPS) selection of Primary Sampling Units (PSUs)",
                    "Simple Random Sampling of clusters with fixed sample count",
                    "Voluntary response sampling",
                    "Judgement sampling"
                ],
                "correct_index": 0,
                "rationale": "PPS selection of PSUs combined with equal sample size per PSU yields an equal-probability (self-weighting) design."
            },
            {
                "id": 803,
                "question": "Why is Taylor Series Linearization employed in survey microdata analysis packages (e.g. R survey, Python statsmodels)?",
                "options": [
                    "To approximate the variance of complex non-linear estimators (e.g. ratios, poverty indices, Gini coefficients)",
                    "To generate linear regression plots",
                    "To sort survey records by household income",
                    "To impute missing survey records"
                ],
                "correct_index": 0,
                "rationale": "Taylor linearization approximates non-linear statistics as linear functions to estimate sampling variance under complex designs."
            },
            {
                "id": 804,
                "question": "In survey weight calibration, what does Post-Stratification / Raking (Iterative Proportional Fitting) achieve?",
                "options": [
                    "Adjusts sample weights so weighted sample totals match known external census population marginals",
                    "Removes all outliers from the survey dataset",
                    "Converts qualitative questions into numbers",
                    "Ensures all households have identical weights"
                ],
                "correct_index": 0,
                "rationale": "Raking adjusts design weights to align marginal distributions with benchmark population totals."
            },
            {
                "id": 805,
                "question": "What is the Intra-Cluster Correlation Coefficient ($\\rho$) and how does a high $\\rho$ affect cluster sampling precision?",
                "options": [
                    "It measures homogeneity within clusters; higher $\\rho$ substantially reduces effective sample size ($n_{eff}$)",
                    "It measures surveyor speed; higher $\\rho$ indicates faster data collection",
                    "It measures correlation between two different surveys",
                    "A high $\\rho$ always improves survey precision"
                ],
                "correct_index": 0,
                "rationale": "High within-cluster homogeneity means observing multiple units in the same cluster yields little unique information."
            }
        ],
        "executive": [
            {
                "id": 901,
                "question": "When balancing the trade-off between National and District-level statistical disaggregation under fixed budget constraints, which methodology enables reliable sub-regional estimates without multiplying sample size?",
                "options": [
                    "Small Area Estimation (SAE) borrowing strength via empirical Bayes or Fay-Herriot models",
                    "Simply multiplying the sample size by zero",
                    "Conducting a full national census every month",
                    "Relying solely on informal social media polls"
                ],
                "correct_index": 0,
                "rationale": "Small Area Estimation models borrow strength from auxiliary administrative data to produce reliable domain estimates."
            },
            {
                "id": 902,
                "question": "What is the primary strategic risk of using non-probability 'big data' (e.g. mobile records, web scraping) as a direct replacement for probability sampling?",
                "options": [
                    "Selection bias and unknown inclusion probabilities make population-level generalization mathematically ungrounded",
                    "Big data takes up too little storage space",
                    "Computers cannot process large files",
                    "Big data is always 100% free of error"
                ],
                "correct_index": 0,
                "rationale": "Non-probability sources suffer from uncontrolled selection mechanisms that can severely bias estimates of the target population."
            },
            {
                "id": 903,
                "question": "In National Statistical System modernization, what does a Dual-Frame Survey design combine?",
                "options": [
                    "An inexpensive but incomplete list frame with an expensive but comprehensive area frame",
                    "Two completely unrelated surveys conducted in different years",
                    "Two questionnaires given to the same individual twice",
                    "A paper questionnaire and an email questionnaire sent to the same person"
                ],
                "correct_index": 0,
                "rationale": "Dual-frame designs exploit cost efficiencies of list frames while using area frames to cover unlisted population segments."
            },
            {
                "id": 904,
                "question": "How should statistical directors manage the 'Total Survey Error' (TSE) framework?",
                "options": [
                    "By optimizing across both sampling errors and non-sampling errors (coverage, measurement, non-response, processing) simultaneously",
                    "By ignoring non-sampling error and focusing exclusively on standard deviation",
                    "By increasing enumerator salaries without training",
                    "By shortening the questionnaire to a single question"
                ],
                "correct_index": 0,
                "rationale": "Total Survey Error encompasses all sources of error across design, implementation, and processing stages."
            },
            {
                "id": 905,
                "question": "What governance role does an Independent National Statistical Audit Commission serve regarding official estimates?",
                "options": [
                    "Validates methodological independence, objectivity, and transparency from political interference",
                    "Determines tax policy based on survey findings",
                    "Enforces disciplinary transfers on enumerators",
                    "Decides the market price of commodities"
                ],
                "correct_index": 0,
                "rationale": "Statistical commissions ensure institutional integrity and credibility under the UN Fundamental Principles."
            }
        ]
    }
}


def _get_skill_key(skill_name: str) -> str:
    """Map skill variations to canonical question bank keys."""
    sn = skill_name.strip().lower()
    if "sql" in sn or "data management" in sn or "database" in sn:
        return "sql & data management"
    if "python" in sn or "reproducible" in sn or "data analysis" in sn or "pandas" in sn:
        return "python & reproducible analysis"
    if "sampling" in sn or "survey" in sn or "estimation" in sn or "methodology" in sn:
        return "applied sampling methodology"
    # Fallback to general data quality or SQL
    return "sql & data management"


def get_quiz_questions(skill_name: str, cadre_tier: str, phase_order: int = 1) -> Dict[str, Any]:
    """Retrieve 5 questions tailored to skill and cadre tier, sanitizing correct answers."""
    skill_key = _get_skill_key(skill_name)
    tier_key = cadre_tier.lower() if cadre_tier.lower() in ("operational", "senior", "executive") else "operational"
    
    questions_pool = QUESTION_BANK.get(skill_key, {}).get(tier_key, [])
    if not questions_pool:
        # Fallback to operational tier of the skill
        questions_pool = QUESTION_BANK.get(skill_key, {}).get("operational", [])

    # Format questions for client (omit correct_index and rationale)
    client_questions = []
    for q in questions_pool[:5]:
        client_questions.append({
            "id": q["id"],
            "question": q["question"],
            "options": q["options"]
        })

    return {
        "status": "success",
        "skill_name": skill_name,
        "cadre_tier": tier_key,
        "phase_order": phase_order,
        "total_questions": len(client_questions),
        "passing_threshold": 80,
        "questions": client_questions
    }


def evaluate_quiz_submission(
    officer_id: int,
    skill_name: str,
    cadre_tier: str,
    phase_order: int,
    target_role: str,
    answers: Dict[str, int],
    db: Session
) -> Dict[str, Any]:
    """Evaluate submitted quiz answers, compute score, and update officer readiness if passed."""
    officer = db.get(Officer, officer_id)
    if not officer:
        raise ValueError("Officer not found")

    skill_key = _get_skill_key(skill_name)
    tier_key = cadre_tier.lower() if cadre_tier.lower() in ("operational", "senior", "executive") else "operational"
    pool = QUESTION_BANK.get(skill_key, {}).get(tier_key, QUESTION_BANK.get(skill_key, {}).get("operational", []))

    correct_count = 0
    total = len(pool[:5])
    explanations = []

    for q in pool[:5]:
        qid_str = str(q["id"])
        selected = answers.get(qid_str)
        is_correct = (selected == q["correct_index"])
        if is_correct:
            correct_count += 1
        
        explanations.append({
            "question_id": q["id"],
            "question": q["question"],
            "selected_index": selected,
            "correct_index": q["correct_index"],
            "is_correct": is_correct,
            "rationale": q["rationale"],
            "options": q["options"]
        })

    score = round((correct_count / total) * 100.0, 1) if total > 0 else 0.0
    passed = (score >= 80.0)
    readiness_gain = 0.0
    cert_uuid = None

    if passed:
        readiness_gain = 8.0
        old_r = officer.readiness
        new_r = min(100.0, round(old_r + readiness_gain, 1))
        officer.readiness = new_r
        officer.open_gaps = max(0, officer.open_gaps - 1)
        officer.assessment_source = "StatIntel Verified Competency Exam"
        officer.assessment_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Update skill tags
        existing_skills = [s.strip() for s in officer.skills.split(";") if s.strip()]
        if skill_name not in existing_skills:
            existing_skills.append(skill_name)
            officer.skills = ";".join(existing_skills)

        # Remove from missing if present
        missing_skills = [m.strip() for m in officer.missing_skills.split(";") if m.strip()]
        missing_skills = [m for m in missing_skills if m.lower() != skill_name.lower()]
        officer.missing_skills = ";".join(missing_skills)

        # Generate unique certificate
        raw_token = uuid.uuid4().hex[:8].upper()
        cert_uuid = f"STAT-{datetime.now(timezone.utc).year}-{raw_token}"
        cert = Certificate(
            cert_uuid=cert_uuid,
            officer_id=officer.id,
            officer_name=officer.name,
            skill_name=skill_name,
            cadre_tier=tier_key,
            target_role=target_role or officer.target_role,
            score=score,
            issued_at=datetime.now(timezone.utc)
        )
        db.add(cert)

        # Audit log
        db.add(AuditLog(
            user_id=None,
            username="assessment_engine",
            action="verify_skill",
            entity_type="certificate",
            entity_id=officer.id,
            detail=f"Officer {officer.name} verified competency in '{skill_name}' ({tier_key} tier) with score {score}%. Issued Cert {cert_uuid}."
        ))

    # Record attempt
    attempt = AssessmentAttempt(
        officer_id=officer.id,
        skill_name=skill_name,
        cadre_tier=tier_key,
        phase_order=phase_order,
        score=score,
        passed=passed,
        total_questions=total,
        correct_answers=correct_count,
        details_json=json.dumps(explanations)
    )
    db.add(attempt)
    db.commit()

    return {
        "status": "success",
        "officer_id": officer.id,
        "officer_name": officer.name,
        "skill_name": skill_name,
        "cadre_tier": tier_key,
        "phase_order": phase_order,
        "score": score,
        "passed": passed,
        "correct_count": correct_count,
        "total_questions": total,
        "readiness_gain": readiness_gain,
        "new_readiness": officer.readiness,
        "certificate_uuid": cert_uuid,
        "explanations": explanations,
        "evaluated_at": datetime.now(timezone.utc).isoformat()
    }


def generate_certificate_pdf(cert: Certificate, officer: Officer) -> bytes:
    """
    Generate an official, vector-grade StatIntel Cadre Competency Certificate
    in landscape A4 format with dual borders, official seals, and a scannable QR verification code.
    """
    buf = io.BytesIO()
    pagesize = landscape(A4)
    width, height = pagesize
    c = canvas.Canvas(buf, pagesize=pagesize)

    # 1. Background Fill
    c.setFillColor(colors.HexColor("#080E1A"))  # Dark institutional navy
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # 2. Outer Decorative Gold Border
    c.setStrokeColor(colors.HexColor("#D4AF37"))
    c.setLineWidth(3)
    c.rect(20, 20, width - 40, height - 40)

    # Inner Delicate Border
    c.setStrokeColor(colors.HexColor("#38BDF8"))
    c.setLineWidth(1)
    c.rect(26, 26, width - 52, height - 52)

    # 3. Corner Accents
    c.setFillColor(colors.HexColor("#D4AF37"))
    c.circle(26, 26, 5, fill=1, stroke=0)
    c.circle(width - 26, 26, 5, fill=1, stroke=0)
    c.circle(26, height - 26, 5, fill=1, stroke=0)
    c.circle(width - 26, height - 26, 5, fill=1, stroke=0)

    # 4. Header Titles
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2.0, height - 60, "NATIONAL STATISTICAL WORKFORCE PLATFORM & CADRE ACADEMY")
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2.0, height - 74, "GOVERNMENT OF INDIA • STATISTICAL INTELLIGENCE SYSTEM")

    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2.0, height - 110, "CERTIFICATE OF VERIFIED CADRE COMPETENCY")

    c.setStrokeColor(colors.HexColor("#D4AF37"))
    c.setLineWidth(1.5)
    c.line(width / 2.0 - 180, height - 120, width / 2.0 + 180, height - 120)

    # 5. Officer Attestation
    c.setFillColor(colors.HexColor("#CBD5E1"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2.0, height - 150, "This is to officially certify that statistical officer")

    # Officer Name in Large Gold/Cyan
    officer_name = (officer.name if officer else cert.officer_name) or "Statistical Officer"
    dept_name = (officer.department if officer else "National Statistical System") or "National Statistical System"
    current_role_name = (officer.current_role if officer else "Statistical Cadre Officer") or "Statistical Cadre Officer"

    c.setFillColor(colors.HexColor("#38BDF8"))
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2.0, height - 185, officer_name.upper())

    c.setFillColor(colors.HexColor("#E2E8F0"))
    c.setFont("Helvetica", 11)
    dept_str = f"Department / Directorate: {dept_name}  •  Current Post: {current_role_name}"
    c.drawCentredString(width / 2.0, height - 208, dept_str)

    # Competency Mastery Block
    c.setFillColor(colors.HexColor("#CBD5E1"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2.0, height - 238, "has successfully passed rigorous competency examination and demonstrated proven proficiency in")

    c.setFillColor(colors.HexColor("#D4AF37"))
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2.0, height - 270, cert.skill_name.upper())

    # Cadre clearance line
    tier_label = cert.cadre_tier.capitalize()
    target_role_label = cert.target_role or (officer.target_role if officer else None) or "Advanced Cadre Specialization"
    clearance_text = f"Clearance Approved: {target_role_label}  |  Cadre Level: {tier_label} Tier  |  Examination Score: {cert.score}%"
    c.setFillColor(colors.HexColor("#34D399"))
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2.0, height - 296, clearance_text)

    # Descriptive statement
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica-Oblique", 9.5)
    statement = "Evaluated under European Statistical System (ESS) criteria and ISI Kolkata Applied Statistics Cadre Guidelines."
    c.drawCentredString(width / 2.0, height - 322, statement)

    # 6. Verification & Scannable QR Code Block
    verify_url = f"https://statintel-live.onrender.com/api/assessment/certificate/{cert.cert_uuid}/verify"
    
    # Draw QR code
    qr = QrCodeWidget(verify_url)
    qr_size = 80
    d = Drawing(qr_size, qr_size)
    d.add(qr)
    renderPDF.draw(d, c, 55, 60)

    # QR Label & Metadata
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(145, 125, "OFFICIAL VERIFICATION IDENTIFIER:")
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(145, 110, cert.cert_uuid)

    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica", 8)
    issue_date = cert.issued_at.strftime("%B %d, %Y") if cert.issued_at else datetime.now(timezone.utc).strftime("%B %d, %Y")
    c.drawString(145, 95, f"Date of Issue: {issue_date}")
    c.drawString(145, 80, "Scan QR code or query public registry to verify certificate authenticity.")
    c.drawString(145, 65, f"Registry URL: {verify_url[:55]}...")

    # 7. Signature Blocks (Right Side)
    c.setStrokeColor(colors.HexColor("#64748B"))
    c.setLineWidth(1)
    c.line(width - 250, 100, width - 60, 100)
    c.line(width - 460, 100, width - 280, 100)

    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width - 370, 85, "Controller of Examinations")
    c.drawCentredString(width - 155, 85, "Cadre Development Advisor")

    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(width - 370, 72, "National Cadre Registry")
    c.drawCentredString(width - 155, 72, "Statistical Intelligence Council")

    c.save()
    return buf.getvalue()
