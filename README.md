## Directory Structure
```txt
root/
│
├── data/
│   ├── onet/
│   │   ├── raw/
│   │   │   ├── abilities.csv
│   │   │   ├── interests.csv
│   │   │   ├── work_styles.csv
│   │   │   ├── work_activities.csv
│   │   │   └── occupation_data.csv
│   │   │
│   │   ├── processed/
│   │   │   ├── career_profiles.json
│   │   │   └── normalization_stats.json
│   │   │
│   │   └── mappings.py
│   │
│   └── README.md
│
├── core/
│   ├── profile.py
│   ├── career_components.py
│   ├── career_profiles.py
│   └── normalization.py
│
├── inference/
│   ├── similarity.py
│   ├── ai_interpreter.py
│   └── answer_converter.py
│
├── ingestion/
│   ├── build_career_profiles.py
│   └── utils.py
│
├── questionnaires/
│   ├── questions.py
│   └── prompt.txt
│
├── scripts/
│   ├── sample.py
│   └── sanity_checks.py
│
├── README.md
├── .gitignore
└── requirements.txt
```

## Pipeline

```
1. Questions
2. Answer Converter
3. PsychometricProfile
4. Feature Vector
5. Career Cluster Model (ML)
6. Career Filtering (by Cluster)
7. Career Ranking (Similarity Matching)
8. AI Interpreter (LLM)
9. Human-Readable Insight + Career Recommendations
```

## Model Schema
```json
{
  "Input": "PsychometricProfile",
  "Output": ["ranked_careers", "strengths", "challenges", "summary"],
  "Data": "O*NET"
}
```

## Data Shape
```json
{
  "traits": 6,
  "interests": 6,
  "aptitudes": 5,
  "values": 6,
  "work_styles": 4
}
```