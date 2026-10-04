"""
Generate synthetic contracts with seeded problems, plus ground truth for eval.

All names, numbers and lenders are fictional. Aadhaar numbers are random 12-digit
numbers with a valid Verhoeff check digit (so the redactor is tested properly);
they are not real people's numbers.

Outputs (in samples/):
  <id>.txt            contract text
  <id>.truth.json     seeded risks, money truth, PII strings
  <id>.html           printable page
  photos/<id>_clean.png, photos/<id>_<degradation>.png   (needs Microsoft Edge for rendering)

Run:  python samples/make_samples.py
"""
from __future__ import annotations

import html
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from apr import compute_loan_cost  # noqa: E402
from redact import verhoeff_check_digit  # noqa: E402

OUT = Path(__file__).resolve().parent
PHOTOS = OUT / "photos"
rng = random.Random(42)
BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def aadhaar() -> str:
    body = str(rng.randint(2, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(10))
    a = body + verhoeff_check_digit(body)
    return f"{a[:4]} {a[4:8]} {a[8:]}"


def phone() -> str:
    return str(rng.choice([6, 7, 8, 9])) + "".join(str(rng.randint(0, 9)) for _ in range(9))


def pan() -> str:
    L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(rng.choice(L) for _ in range(3)) + "P" + rng.choice(L) + f"{rng.randint(0, 9999):04d}" + rng.choice(L)


def C(label: str, text: str, risky: bool = False, rules: list[str] | None = None) -> dict:
    return {"label": label, "text": text, "risky": risky, "rules": rules or []}


def build() -> list[dict]:
    docs = []

    a, p = aadhaar(), phone()
    docs.append({
        "id": "01_mfi_weekly_en", "lang": "en", "doc_type": "loan",
        "title": "GROUP LOAN AGREEMENT - Sahaj Micro Credit Pvt Ltd (fictional)",
        "header": [f"Borrower: Rina Das, Village Kalna, Purba Bardhaman", f"Aadhaar No: {a}   Mobile: {p}"],
        "pii": [a, p],
        "clauses": [
            C("1", "Loan amount: Rs 20,000 (Rupees twenty thousand only). A processing fee of Rs 1,000 and insurance of Rs 400 will be deducted from the loan amount at disbursal.", True, ["hidden_upfront_fees"]),
            C("2", "Interest is 24% per annum on a flat basis. The loan is repayable in 50 weekly installments of Rs 496 each.", True, ["flat_rate_presented", "effective_cost_mismatch"]),
            C("3", "If any installment is not paid on the due date, penal interest at 2% per week will be charged on the overdue amount and compounded weekly.", True, ["penal_compounding"]),
            C("4", "The Company may revise the rate of interest, fees and charges at its sole discretion at any time without prior notice to the Borrower.", True, ["unilateral_change"]),
            C("5", "All members of the group are jointly responsible for repayment of each member's loan."),
            C("6", "The Borrower may repay the loan early without any charge."),
            C("7", "Disputes shall be subject to the jurisdiction of courts at Bardhaman."),
        ],
        "money": dict(principal=20000, upfront_fees=1400, installment=496, num_installments=50, frequency="weekly",
                      stated_rate_pct=24, stated_rate_period="year", rate_type="flat"),
    })

    a, p = aadhaar(), phone()
    docs.append({
        "id": "02_moneylender_gold_en", "lang": "en", "doc_type": "loan",
        "title": "LOAN AGREEMENT ON PLEDGE OF GOLD (fictional)",
        "header": [f"Borrower: Sukanta Mondal, Ranaghat, Nadia", f"Phone: {p}  Aadhaar: {a}"],
        "pii": [a, p],
        "clauses": [
            C("1", "The Lender advances Rs 50,000 to the Borrower against the pledge of gold ornaments weighing 25 grams."),
            C("2", "Interest at 3% per month shall be charged. The Borrower shall repay the principal with interest in one lump sum of Rs 59,000 after 6 months.", True, ["missing_apr_disclosure"]),
            C("3", "Two signed blank cheques shall be given to the Lender as security.", True, ["blank_documents"]),
            C("4", "If the Borrower fails to pay on the due date, the Lender may sell or auction the pledged gold at any time without any notice to the Borrower.", True, ["repossession_without_notice"]),
            C("5", "The decision of the Lender regarding the amount due shall be final and binding, and the Borrower shall not approach any court, police or consumer forum.", True, ["rights_waiver"]),
            C("6", "The Borrower shall not repay before 6 months. If repaid early, the full 6 months' interest shall still be payable.", True, ["heavy_prepayment_charge"]),
        ],
        "money": dict(principal=50000, upfront_fees=0, installment=0, num_installments=6, frequency="monthly",
                      balloon=59000, stated_rate_pct=3, stated_rate_period="month", rate_type="flat"),
    })

    a, p, pn = aadhaar(), phone(), pan()
    m3 = compute_loan_cost(100000, 12, stated_rate_pct=16, rate_type="reducing", upfront_fees=1180)
    docs.append({
        "id": "03_nbfc_fair_en", "lang": "en", "doc_type": "loan",
        "title": "PERSONAL LOAN AGREEMENT - Udaya Finance Ltd (fictional)",
        "header": [f"Borrower: Amit Kumar Saha, Howrah. PAN: {pn}", f"Aadhaar: {a}, Mobile: +91 {p[:5]} {p[5:]}"],
        "pii": [a, p, pn],
        "clauses": [
            C("1", "Loan amount Rs 1,00,000. A processing fee of Rs 1,180 (including GST) is deducted at disbursal and is shown in the Key Facts Statement."),
            C("2", f"Interest is 16% per annum on the reducing balance. The loan is repayable in 12 monthly EMIs of Rs {m3.installment:,.0f}. The Annual Percentage Rate (APR) is {m3.apr_pct:.1f}% as stated in the Key Facts Statement."),
            C("3", "Penal charges: a fixed charge of Rs 500 per missed EMI. No interest is charged on penal charges."),
            C("4", "Any change in the interest rate or charges will be communicated in writing 30 days in advance."),
            C("5", "The Borrower may foreclose the loan at any time without any foreclosure charge."),
            C("6", "Complaints may be made to our Grievance Redressal Officer and, if unresolved in 30 days, to the RBI Ombudsman."),
        ],
        "money": dict(principal=100000, upfront_fees=1180, installment=round(m3.installment), num_installments=12,
                      frequency="monthly", stated_rate_pct=16, stated_rate_period="year", rate_type="reducing"),
    })

    a, p = aadhaar(), phone()
    docs.append({
        "id": "04_vehicle_loan_en", "lang": "en", "doc_type": "loan",
        "title": "TWO-WHEELER LOAN AGREEMENT - Gati Motor Finance (fictional)",
        "header": [f"Borrower: Rahim Sheikh, Basirhat. Mobile {p}", f"Aadhaar {a}"],
        "pii": [a, p],
        "clauses": [
            C("1", "Loan amount Rs 60,000 for purchase of a two-wheeler. A processing fee of Rs 1,800 will be deducted at disbursal.", True, ["hidden_upfront_fees"]),
            C("2", "Interest is 10% per annum flat. The loan is repayable in 24 monthly installments of Rs 3,000.", True, ["flat_rate_presented", "effective_cost_mismatch"]),
            C("3", "In case of default of even one installment, the Company may repossess the vehicle without notice and sell it.", True, ["repossession_without_notice"]),
            C("4", "The Borrower waives all rights to file a complaint before any consumer commission.", True, ["rights_waiver"]),
            C("5", "Late payment charges of Rs 750 per day will apply on any delayed installment.", True, ["excessive_late_fee"]),
            C("6", "This agreement is governed by the laws of India."),
        ],
        "money": dict(principal=60000, upfront_fees=1800, installment=3000, num_installments=24, frequency="monthly",
                      stated_rate_pct=10, stated_rate_period="year", rate_type="flat"),
    })

    a, p = aadhaar(), phone()
    docs.append({
        "id": "05_rental_en", "lang": "en", "doc_type": "rental",
        "title": "RENT AGREEMENT (fictional)",
        "header": ["Landlord: Gopal Chandra Roy. Tenant: Mithu Khatun", f"Tenant Aadhaar: {a}. Tenant phone: {p}"],
        "pii": [a, p],
        "clauses": [
            C("1", "The monthly rent is Rs 6,000, payable before the 5th of every month."),
            C("2", "The Tenant shall pay a security deposit of Rs 60,000, which is non-refundable.", True, ["excessive_security_deposit"]),
            C("3", "The Landlord may increase the rent at any time at his sole discretion.", True, ["unilateral_change"]),
            C("4", "If the rent is delayed, the Landlord may lock the premises and cut off electricity and water without notice.", True, ["eviction_without_notice"]),
            C("5", "The Tenant shall keep the flat clean and shall not sublet it."),
            C("6", "The term is 11 months, renewable by mutual consent."),
        ],
        "money": None, "rental": {"monthly_rent": 6000, "security_deposit": 60000},
    })

    a, p = aadhaar(), phone()
    docs.append({
        "id": "06_loan_bn", "lang": "bn", "doc_type": "loan",
        "title": "ঋণ চুক্তিপত্র (কাল্পনিক)",
        "header": ["ঋণগ্রহীতা: শ্যামলী বিশ্বাস, গ্রাম চাকদহ", f"আধার নম্বর: {a}   ফোন: {p}"],
        "pii": [a, p],
        "bn_digits": True,
        "clauses": [
            C("1", "ঋণের পরিমাণ 15,000 টাকা। প্রসেসিং ফি বাবদ 750 টাকা ঋণের টাকা থেকে কেটে নেওয়া হবে।", True, ["hidden_upfront_fees"]),
            C("2", "সুদের হার মাসিক 2% ফ্ল্যাট। ঋণ 12টি মাসিক কিস্তিতে শোধ করতে হবে, প্রতি কিস্তি 1,550 টাকা।", True, ["flat_rate_presented", "effective_cost_mismatch"]),
            C("3", "কিস্তি দিতে দেরি হলে বকেয়া টাকার উপর মাসিক 5% জরিমানা সুদ ধরা হবে এবং তা চক্রবৃদ্ধি হারে বাড়বে।", True, ["penal_compounding"]),
            C("4", "ঋণদাতা যে কোনো সময় নোটিশ ছাড়াই সুদের হার পরিবর্তন করতে পারবে।", True, ["unilateral_change"]),
            C("5", "ঋণগ্রহীতা দুটি সই করা ফাঁকা চেক জমা দেবেন।", True, ["blank_documents"]),
            C("6", "এই চুক্তি ভারতের আইন অনুযায়ী পরিচালিত হবে।"),
        ],
        "money": dict(principal=15000, upfront_fees=750, installment=1550, num_installments=12, frequency="monthly",
                      stated_rate_pct=2, stated_rate_period="month", rate_type="flat"),
    })

    a, p = aadhaar(), phone()
    docs.append({
        "id": "07_loan_hi", "lang": "hi", "doc_type": "loan",
        "title": "ऋण अनुबंध (काल्पनिक)",
        "header": ["उधारकर्ता: सुनीता देवी, गांव मधुपुर", f"आधार: {a}   मोबाइल: {p}"],
        "pii": [a, p],
        "clauses": [
            C("1", "ऋण राशि 25,000 रुपये है। दस्तावेज़ शुल्क 1,250 रुपये ऋण राशि से काट लिया जाएगा।", True, ["hidden_upfront_fees"]),
            C("2", "ब्याज दर 20% प्रति वर्ष फ्लैट है। ऋण 40 साप्ताहिक किस्तों में चुकाना होगा, हर किस्त 750 रुपये।", True, ["flat_rate_presented", "effective_cost_mismatch"]),
            C("3", "उधारकर्ता को कोरे स्टांप पेपर पर हस्ताक्षर करने होंगे।", True, ["blank_documents"]),
            C("4", "उधारकर्ता किसी भी अदालत या उपभोक्ता फोरम में शिकायत करने का अधिकार छोड़ता है।", True, ["rights_waiver"]),
            C("5", "ऋणदाता किसी भी समय बिना सूचना के किस्त की राशि बदल सकता है।", True, ["unilateral_change"]),
            C("6", "समय से पहले भुगतान करने पर बकाया राशि का 10% शुल्क लगेगा।", True, ["heavy_prepayment_charge"]),
        ],
        "money": dict(principal=25000, upfront_fees=1250, installment=750, num_installments=40, frequency="weekly",
                      stated_rate_pct=20, stated_rate_period="year", rate_type="flat"),
    })

    a, p = aadhaar(), phone()
    docs.append({
        "id": "08_gold_loan_en", "lang": "en", "doc_type": "loan",
        "title": "GOLD LOAN AGREEMENT - Swarna Credit Ltd (fictional)",
        "header": [f"Borrower: Pradip Ghosh, Krishnanagar", f"KYC: Aadhaar {a}; registered mobile {p}"],
        "pii": [a, p],
        "clauses": [
            C("1", "Loan amount Rs 40,000 against gold ornaments. Advance interest of Rs 600 for the first month is deducted at disbursal.", True, ["hidden_upfront_fees"]),
            C("2", "Interest is 18% per annum. The loan is repayable in 12 monthly installments of Rs 3,667. The APR is shown in the attached Key Facts Statement."),
            C("3", "Penal interest of 2% per month over and above the applicable rate will be charged on all overdue amounts.", True, ["penal_compounding"]),
            C("4", "On default, the Company may auction the gold after giving 7 days' notice by SMS and registered post."),
            C("5", "Foreclosure is allowed after 3 months with a charge of 2% of the outstanding amount."),
            C("6", "Grievances may be raised with the Grievance Officer or the RBI Ombudsman."),
        ],
        "money": dict(principal=40000, upfront_fees=600, installment=3667, num_installments=12, frequency="monthly",
                      stated_rate_pct=18, stated_rate_period="year", rate_type="unknown"),
    })

    a, p = aadhaar(), phone()
    docs.append({
        "id": "09_rental_bn", "lang": "bn", "doc_type": "rental",
        "title": "বাড়ি ভাড়ার চুক্তি (কাল্পনিক)",
        "header": ["বাড়িওয়ালা: নির্মল দত্ত। ভাড়াটে: রুমা পাল", f"ভাড়াটের ফোন: {p}, আধার: {a}"],
        "pii": [a, p],
        "bn_digits": True,
        "clauses": [
            C("1", "মাসিক ভাড়া 5,000 টাকা, প্রতি মাসের 7 তারিখের মধ্যে দিতে হবে।"),
            C("2", "ভাড়াটে 50,000 টাকা জামানত দেবেন, যা ফেরতযোগ্য নয়।", True, ["excessive_security_deposit"]),
            C("3", "ভাড়া দিতে দেরি হলে বাড়িওয়ালা নোটিশ ছাড়াই ঘরে তালা দিতে এবং বিদ্যুৎ বন্ধ করতে পারবেন।", True, ["eviction_without_notice"]),
            C("4", "বাড়িওয়ালা যে কোনো সময় নিজের ইচ্ছামতো ভাড়া বাড়াতে পারবেন।", True, ["unilateral_change"]),
            C("5", "চুক্তির মেয়াদ 11 মাস।"),
        ],
        "money": None, "rental": {"monthly_rent": 5000, "security_deposit": 50000},
    })
    return docs


def to_text(d: dict) -> str:
    lines = [d["title"], *d["header"], *(f"{c['label']}. {c['text']}" for c in d["clauses"])]
    text = "\n".join(lines)
    return text.translate(BN_DIGITS) if d.get("bn_digits") else text


def truth(d: dict) -> dict:
    money = None
    if d["money"]:
        m = dict(d["money"])
        res = compute_loan_cost(m.pop("principal"), m.pop("num_installments"), **m)
        money = {"input": d["money"], "total_repayment": res.total_repayment, "extra_cost": res.extra_cost,
                 "apr_pct": res.apr_pct}
    pii = [x.translate(BN_DIGITS) if d.get("bn_digits") else x for x in d["pii"]]
    return {"id": d["id"], "lang": d["lang"], "doc_type": d["doc_type"],
            "clauses": [{k: c[k] for k in ("label", "risky", "rules")} for c in d["clauses"]],
            "money": money, "rental": d.get("rental"), "pii": pii}


PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#fffdf7;font-family:"Times New Roman","Nirmala UI",serif;font-size:{fs}px;line-height:1.55;color:#222}}
.page{{padding:70px 80px}} h1{{text-align:center;font-size:{h1}px;margin:0 0 24px}}
p{{margin:0 0 14px}} .sig{{margin-top:60px;display:flex;justify-content:space-between}}
</style></head><body><div class="page"><h1>{title}</h1>{body}
<div class="sig"><span>Signature of Lender / Landlord</span><span>Signature of Borrower / Tenant</span></div></div></body></html>"""


def to_html(text: str, fs: int = 26) -> str:
    title, *rest = text.split("\n")
    body = "".join(f"<p>{html.escape(l)}</p>" for l in rest)
    return PAGE.format(title=html.escape(title), body=body, fs=fs, h1=fs + 6)


EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def render(html_path: Path, png: Path) -> bool:
    exe = EDGE if Path(EDGE).exists() else shutil.which("msedge") or shutil.which("chromium") or shutil.which("google-chrome")
    if not exe:
        return False
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    f"--screenshot={png}", "--window-size=1240,1754", html_path.resolve().as_uri()],
                   check=True, capture_output=True, timeout=60)
    return png.exists()


def degrade(src: Path, kind: str, dst: Path) -> None:
    import cv2
    import numpy as np

    img = cv2.imread(str(src))
    h, w = img.shape[:2]
    r = np.random.default_rng(7)
    if kind == "angled":
        pts1 = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
        pts2 = np.float32([[40, 30], [w - 10, 0], [0, h - 10], [w - 50, h - 40]])
        img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(pts1, pts2), (w, h), borderValue=(90, 90, 90))
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 3.5, 1.0)
        img = cv2.warpAffine(img, m, (w, h), borderValue=(90, 90, 90))
    elif kind == "dim":
        img = cv2.convertScaleAbs(img, alpha=0.5, beta=10)
        shade = np.tile(np.linspace(0.65, 1.0, w, dtype=np.float32), (h, 1))[..., None]
        img = np.clip(img * shade + r.normal(0, 8, img.shape), 0, 255).astype(np.uint8)
    elif kind == "blurry":
        img = cv2.GaussianBlur(img, (0, 0), 2.2)
    cv2.imwrite(str(dst), img, [cv2.IMWRITE_PNG_COMPRESSION, 6])


def main() -> None:
    PHOTOS.mkdir(exist_ok=True)
    docs = build()
    kinds = ["angled", "dim", "blurry"]
    rendered = 0
    for i, d in enumerate(docs):
        text = to_text(d)
        (OUT / f"{d['id']}.txt").write_text(text, encoding="utf-8")
        (OUT / f"{d['id']}.truth.json").write_text(json.dumps(truth(d), ensure_ascii=False, indent=2), encoding="utf-8")
        page = OUT / f"{d['id']}.html"
        page.write_text(to_html(text), encoding="utf-8")
        small = OUT / f"{d['id']}.small.html"
        small.write_text(to_html(text, fs=17), encoding="utf-8")
        clean = PHOTOS / f"{d['id']}_clean.png"
        try:
            if render(page, clean):
                rendered += 1
                kind = kinds[i % len(kinds)]
                degrade(clean, kind, PHOTOS / f"{d['id']}_{kind}.png")
                if i % 3 == 0 and render(small, PHOTOS / f"{d['id']}_smallfont.png"):
                    pass
        except (subprocess.SubprocessError, OSError) as e:
            print(f"render failed for {d['id']}: {e}")
        small.unlink(missing_ok=True)
    print(f"{len(docs)} contracts written; {rendered} rendered to photos/")


if __name__ == "__main__":
    main()
