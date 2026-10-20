"""Create a workbook of 1,200 FICTIONAL employees for development and demos.

Run:  python generate_data.py
Output: sample_employees.xlsx
"""
import random
import pandas as pd

FIRST = ["Aisha", "Bilal", "Carmen", "Daniel", "Elena", "Farhan", "Grace", "Hamza",
         "Iris", "Jamal", "Kiran", "Liam", "Maya", "Noor", "Omar", "Priya",
         "Qasim", "Rania", "Sana", "Tariq", "Uma", "Victor", "Wendy", "Xavier",
         "Yusra", "Zane", "Anya", "Bruno", "Chloe", "Dev", "Esha", "Felix",
         "Hina", "Ivan", "Julia", "Karan", "Layla", "Mateo", "Nadia", "Owen"]
LAST = ["Abbas", "Baker", "Chaudhry", "Dawson", "Evans", "Farooq", "Garcia", "Hussain",
        "Iqbal", "Jensen", "Khan", "Lopez", "Malik", "Nguyen", "Olsen", "Patel",
        "Qureshi", "Rossi", "Siddiqui", "Taylor", "Usman", "Varga", "Wright", "Xu",
        "Yilmaz", "Zafar", "Ahmed", "Brown", "Cruz", "Das", "Ellis", "Fisher",
        "Gill", "Hayes", "Ibrahim", "Jones", "Kumar", "Lee", "Mirza", "Novak"]

DEPARTMENTS = {
    "Engineering": ["Software Engineer", "Senior Software Engineer", "QA Engineer", "DevOps Engineer"],
    "Human Resources": ["HR Executive", "Recruiter", "HR Manager"],
    "Finance": ["Accountant", "Financial Analyst", "Finance Manager"],
    "Marketing": ["Marketing Executive", "Content Strategist", "Brand Manager"],
    "Sales": ["Sales Executive", "Account Manager", "Sales Lead"],
    "Operations": ["Operations Analyst", "Logistics Coordinator", "Operations Manager"],
    "Customer Support": ["Support Agent", "Support Team Lead"],
    "IT": ["System Administrator", "Network Engineer", "IT Support Specialist"],
}


def generate(n: int = 1200, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        dept = rng.choice(list(DEPARTMENTS))
        rows.append({
            "Employee_ID": f"EMP{i:04d}",
            "Name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "Designation": rng.choice(DEPARTMENTS[dept]),
            "Department": dept,
            "Photo": "",                       # empty -> app shows initials avatar
            "Record_Type": "SYNTHETIC",        # clearly marked as fake data
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate()
    df.to_excel("sample_employees.xlsx", index=False)
    print(f"Created sample_employees.xlsx with {len(df)} fictional employees.")
