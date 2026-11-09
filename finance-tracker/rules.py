"""Categorisation rules: raw statement narration -> merchant, category, review flag.

Order matters: the first matching rule wins. Categories and whether they count
toward income / spending live in CATEGORIES.
"""
import re

# name -> group. Groups: "income", "spend", "excluded" (never counted by default).
CATEGORIES = {
    "Salary": "income",
    "Reimbursements": "income",
    "Interest & cashback": "income",
    "From Dad": "income",
    "Other income": "income",
    "Rent": "spend",
    "Household (with Lakshana)": "spend",
    "Food delivery": "spend",
    "Groceries & quick commerce": "spend",
    "Dining out": "spend",
    "Office meals": "spend",
    "Alcohol": "spend",
    "Shopping": "spend",
    "Personal care": "spend",
    "Health & medical": "spend",
    "Entertainment": "spend",
    "Travel & stays": "spend",
    "Transport & fuel": "spend",
    "Subscriptions & apps": "spend",
    "Phone & internet": "spend",
    "Insurance": "spend",
    "Education & classes": "spend",
    "Cash spending": "spend",
    "Small UPI payments": "spend",
    "Splits with friends": "spend",
    "Payments to people": "spend",
    "Fees & charges": "spend",
    "Other spending": "spend",
    "Own-account transfers": "excluded",
    "Card bill payments": "excluded",
    "Family transfers": "excluded",
    "Lending & money returned": "excluded",
    "Bought for family (paid back)": "excluded",
    "Cash moved between accounts": "excluded",
    "Cash withdrawn to wallet": "excluded",
}

# (regex on upper-cased narration, merchant label, category, review, note)
R = []


def rule(pattern, merchant, category, review=False, note=""):
    R.append((re.compile(pattern), merchant, category, review, note))


# ---- transfers between own accounts, card bills, family, friends ----
rule(r"MOB/SELFFT|PRAVEEN ?RAAMANAATHAN|UPI/P2A/.*/PRAVEEN R/|IMPS/MRT/.*918525094643",
     "Own account", "Own-account transfers")
rule(r"HDFC BANK DIGITAL CR", "HDFC credit card bill", "Card bill payments")
rule(r"CREDITCARD PAYMENT|^MB PAYMENT", "Axis credit card bill", "Card bill payments")
rule(r"^PAYMENT RECEIVED", "Card bill payment", "Card bill payments")
rule(r"FUEL SURCHARGE REVERSAL", "Fuel surcharge refund", "Transport & fuel")
rule(r"TRULIV", "Truliv (rent)", "Rent")
rule(r"ARULALAN", "Dad", "DAD", False, "")
rule(r"LAKSHANA", "Lakshana B", "Household (with Lakshana)", False,
     "Your share of household costs. Money she sends back reduces it.")
rule(r"JANANI SANKAR", "Dr Janani Sankar", "Health & medical")
rule(r"KARTHIKEYAN|BHAVANI B|BHAVANA B", None, "Splits with friends", False,
     "Shared spending: money sent adds to spending, money received back reduces it.")
rule(r"CASH DEPOSIT", "Cash deposit", "Family transfers", False,
     "Cash from Dad (plus the 11 Oct Axis withdrawal), part of the October family transfer.")

# ---- income ----
rule(r"ZOOMRX.*(MEALS|TRAVEL)", "ZoomRx reimbursement", "Reimbursements")
rule(r"ZOOMRX", "ZoomRx", "Salary")
rule(r"INT\.PD|INTEREST PAID", "Bank interest", "Interest & cashback")
rule(r"FUEL CASHBACK", "Card cashback", "Interest & cashback")
rule(r"UPIRET", "UPI cashback", "Interest & cashback")

# ---- fees ----
rule(r"CASH TXN CHGS|ISSUANCE FEE|ANNUAL FEE|^IMPS P2P|DCC MARKUP|^GST$", "Bank fees", "Fees & charges")

# ---- cash ----
rule(r"ATM|^ATW-|^NWD-", "ATM withdrawal", "Cash withdrawn to wallet", False,
     "Cash into your wallet. What you spend from it is recorded as Cash spending.")

# ---- food ----
rule(r"SWIGGY INSTAMART|SWIGGY E COM", "Swiggy Instamart", "Groceries & quick commerce")
rule(r"SWIGGY|BUNDL TECHNOLOGIES", "Swiggy", "Food delivery")
rule(r"EAT GOOD TECH|EATCLUB", "EatClub", "Food delivery")
rule(r"ETERNAL LIMITED|ZOMATO", "Zomato", "Food delivery")
rule(r"JUBILANT|DOMINOS", "Domino's", "Food delivery")
rule(r"HUNGERBOX", "Hungerbox", "Office meals")
rule(r"ZEPTO", "Zepto", "Groceries & quick commerce")
rule(r"BLINKIT|BLINK COMMERCE", "Blinkit", "Groceries & quick commerce")
rule(r"AKSHAYAKALPA|VIJAYA MILK|AKSHAYA VEG|PARRY MULTI|NISH STORE|CHAITANYA GOURMET",
     None, "Groceries & quick commerce")
rule(r"DISTRICT DINING", "District (dining)", "Dining out")
rule(r"TASMAC", "TASMAC", "Alcohol")
rule(r"RAYARS|RAMESHWARAM|CHAAYOS|ANDHRA MEALS|PRASANAM|HOT N SPICY|MOMO|CAKES|GEETHAM|VOHUMAN|"
     r"KATI ROLL|JUICE|BLACK PEKOE|MANOJ BHAVAN|BALAAJEE|CHARMINAR|GREMS|RAJ PALACE|WELCOME HOTEL|"
     r"COZZY|GHAR KA KHANA|MAISON|SUBZERO|SWEETS|BUTTER MILK|COOL BAR|TEA |TEA$|TEA-|COFFEE|"
     r"CIACCO|MOUTAN|NANDHANA|HOTEL HALEZ|SRM HOTELS|BOARD ROOM|SHILTON|SHEESHA|HARI  CATERS|"
     r"SNACKS|MAYURA|WHITE TOWN|REFRESHING|STARBUCKS|MITHAI|IBACO|CULINARY BRANDS|BIRYANI|PON VASANTHAM|YAMANAGA", None, "Dining out")

# ---- shopping / personal ----
rule(r"FLIPKART", "Flipkart", "Shopping")
rule(r"MYNTRA", "Myntra", "Shopping")
rule(r"^ASSPL|AMAZON", "Amazon", "Shopping")
rule(r"LIFE STYLE|LEVIS|JOCKEY|VICTORIA|KHADI|VARAMAHALAKSHMI|VUMMIDI|ZIMSON|HIDESIDE|TUCKED IN|"
     r"LYNK CRAFTS|BLUETYGA|DOCTORTOWELS|MARCH TEE|DAILYOBJECTS|CROSSWORD|BESTBUY|HINDUSTAN TRADING|"
     r"EVERYDAY INTENTION|ONESTO|WATERSCIENCE|TEA NURSERY|FLOWER|JON ENTERPRISE|HEMA ENTERPRISES|"
     r"SHANSCO|UGAOO|AURIGLO|PATTABHIRAMA", None, "Shopping")
rule(r"SEPHORA|HAIRWAYS|INNOVIST|DOT & KEY|RELEAF|DECONSTRUCT", None, "Personal care")

# ---- health ----
rule(r"DENTAL|APOLLO|ANDERSON|MEDPLUS|PHARMAC|SPECIALITY|CAPZ N TABZ|MEDICALS|NUTRITION", None,
     "Health & medical")

# ---- entertainment / travel / transport ----
rule(r"BOOKMYSHOW", "BookMyShow", "Entertainment")
rule(r"PVR|KICKASS", None, "Entertainment")
rule(r"AGODA|MAKEMYTRIP|REDBUS|CONFIRM TICKET|ALLBEST TRAVELS|MANGALORE CONSOLIDATED", None,
     "Travel & stays")
rule(r"EKAYARS", "Ekayars (fuel)", "Transport & fuel")
rule(r"A ?J SERVICE STATION", "AJ Service Station (fuel)", "Transport & fuel")
rule(r"ABT LTD", "ABT Ltd (car service)", "Transport & fuel", False, "Car servicing.")
rule(r"ROPPEN|RAPIDO|PARKI|ADANI|SERVICE STATION|PETROL|FUEL|EKAYARS", None, "Transport & fuel")

# ---- bills / subscriptions ----
rule(r"APPLE", "Apple", "Subscriptions & apps")
rule(r"YOUTUBE|GOOGLE|WISPR", None, "Subscriptions & apps")
rule(r"AIRTEL", "Airtel", "Phone & internet")
rule(r"LIC", "LIC premium", "Insurance")
rule(r"INDIAN INSTITUTE OF MA|SRM INSTITUTES|SRM EDUCATION|SRUTHILAYA|RODA NOTES", None,
     "Education & classes")
rule(r"UPI-LITE", "UPI Lite top-up", "Small UPI payments", False,
     "Money loaded into UPI Lite; the individual payments aren't itemised.")
rule(r"^POS .*PAYTM", "Paytm", "Other spending", True)
rule(r"BIGBASKET|INNOVATIVE RETAIL", "BigBasket", "Groceries & quick commerce")


PREFIX = re.compile(r"^(RSP|RAZ|CAS|PHP|PAY|PYU|PTM)\*")


def clean_merchant(desc):
    d = desc.strip()
    m = re.match(r"UPI-(.*?)-([^-]*@[^-]*)-", d)
    if m:
        return re.sub(r"-.*$", "", m.group(1)).strip().title()
    m = re.match(r"UPI/P2A/\d+/(.*?)/", d)
    if m:
        return m.group(1).strip().title()
    m = re.match(r"POS \S+ \S+ \S+ \S+ (.*)", d)
    if m:
        return re.sub(r"^(NOIDA|GURUGRAM|GURGAON|MUMBAI|BANGALORE|BENGALURU|MANGALORE|CHENNAI) ", "",
                      m.group(1)).strip().title()
    d = PREFIX.sub("", d)
    d = d.split(",")[0]
    d = re.sub(r"\s+\d{5,}$", "", d)
    return d.strip().title()[:40]


def categorise(desc, amount, direction, account, date):
    u = desc.upper()
    merchant = None
    for pat, m, cat, review, note in R:
        if pat.search(u):
            # The 50k Axis ATM withdrawal on 11 Oct was re-deposited into HDFC on 13 Oct.
            if cat == "Cash withdrawn to wallet" and account.startswith("Axis Savings") and date == "2026-10-11":
                return {"merchant": "ATM withdrawal", "category": "Cash moved between accounts",
                        "review": False, "note": "Withdrawn from Axis and deposited into HDFC on 13 Oct."}
            if cat == "DAD":
                # Oct 2026 family transfers and the 31 May / 1 Jun round trip net out; skip them.
                if date >= "2026-10-01" or date in ("2026-05-31", "2026-06-01"):
                    return {"merchant": "Dad", "category": "Family transfers", "review": False,
                            "note": "Family transfer with Dad; not counted."}
                if direction == "in":
                    return {"merchant": "Dad", "category": "From Dad", "review": False, "note": ""}
                return {"merchant": "Dad", "category": "Family transfers", "review": True, "note": ""}
            if cat == "Salary" and amount > 150000:
                note = "Much larger than the usual salary; probably a bonus or settlement."
            # Refunds into a spend category stay in that category and reduce its total.
            return {"merchant": m or clean_merchant(desc), "category": cat, "review": review,
                    "note": note}
    merchant = clean_merchant(desc)
    is_upi_person = bool(re.match(r"UPI-", u)) and "@HDFCBANK" not in u
    if direction == "in":
        return {"merchant": merchant, "category": "Other income", "review": True,
                "note": "Unrecognised incoming payment."}
    if is_upi_person and amount <= 500:
        return {"merchant": merchant, "category": "Small UPI payments", "review": False, "note": ""}
    if is_upi_person:
        return {"merchant": merchant, "category": "Payments to people", "review": True,
                "note": "UPI payment to a person. Mark it as lending if you'll get it back."}
    return {"merchant": merchant, "category": "Other spending", "review": True, "note": ""}


# ---------------------------------------------------------------------------
# Subcategories: (category, regex on merchant + narration, subcategory). First match wins.
# Swiggy descriptors: FOOD / FOOD1 / "PVT LTD FO" are food delivery; INSTAMART / E COM are
# Instamart. Plain "Swiggy", "Swiggy Limited", CAS*/RAZ* Swiggy can be food, Instamart or
# Dineout, and the statement doesn't say which.
SUB_RULES = [
    ("Food delivery", r"SWIGGY.*(FOOD|PVT LTD FO)|BUNDL", "Swiggy food delivery"),
    ("Food delivery", r"SWIGGY", "Swiggy (food, Instamart or Dineout: unclear)"),
    ("Food delivery", r"ZOMATO|ETERNAL", "Zomato"),
    ("Food delivery", r"EATCLUB|EAT GOOD", "EatClub"),
    ("Food delivery", r"DOMINO|JUBILANT", "Domino's"),
    ("Groceries & quick commerce", r"ZEPTO", "Zepto"),
    ("Groceries & quick commerce", r"BLINK", "Blinkit"),
    ("Groceries & quick commerce", r"INSTAMART|SWIGGY E COM", "Swiggy Instamart"),
    ("Groceries & quick commerce", r"BIGBASKET|INNOVATIVE RETAIL", "BigBasket"),
    ("Groceries & quick commerce", r".", "Milk, vegetables & local stores"),
    ("Dining out", r"DISTRICT", "Restaurants paid via District"),
    ("Dining out", r"COFFEE|CAFE|STARBUCKS|CHAAYOS|TEA|PEKOE|JUICE|COOL BAR|BUTTER MILK|COZZY|"
                   r"REFRESHING|CAKES|SWEETS|MITHAI|IBACO|SUBZERO|MAISON", "Cafés, tea, sweets & desserts"),
    ("Dining out", r"BOARD ROOM|SHEESHA|SHILTON|YAMANAGA", "Bars, pubs & lounges"),
    ("Dining out", r".", "Restaurants"),
    ("Shopping", r"FLIPKART|AMAZON|ASSPL|MYNTRA", "Online marketplaces"),
    ("Shopping", r"LEVIS|JOCKEY|LIFE STYLE|VICTORIA|MARCH TEE|TUCKED IN|BLUETYGA|HIDESIDE|ZIMSON|"
                 r"SILKS|KHADI|PATTABHIRAMA", "Clothing, shoes & accessories"),
    ("Shopping", r"VUMMIDI|JEWEL", "Jewellery"),
    ("Shopping", r"CROSSWORD|RODA", "Books & stationery"),
    ("Shopping", r"BESTBUY|MOBILE", "Electronics"),
    ("Shopping", r".", "Home & other"),
    ("Health & medical", r"DENTAL", "Dental"),
    ("Health & medical", r"DIAGNOSTIC", "Diagnostics & tests"),
    ("Health & medical", r"JANANI|SPECIALITY|HOSPITAL", "Doctors & hospitals"),
    ("Health & medical", r".", "Pharmacy & supplements"),
    ("Transport & fuel", r"ABT", "Car service"),
    ("Transport & fuel", r"EKAYARS|SERVICE STATION|FUEL|PETROL", "Fuel"),
    ("Transport & fuel", r"PARKI", "Parking"),
    ("Transport & fuel", r".", "Rides & tolls"),
    ("Travel & stays", r"AGODA|MAKEMYTRIP|HOTEL", "Hotels & bookings"),
    ("Travel & stays", r"REDBUS|CONFIRM TICKET|TRAVELS", "Bus & train"),
    ("Subscriptions & apps", r"APPLE", "Apple (iCloud, App Store)"),
    ("Subscriptions & apps", r"YOUTUBE|GOOGLE", "Google & YouTube"),
    ("Entertainment", r"BOOKMYSHOW|KARTHIKEYAN|BHAVANI", "Event tickets (BookMyShow)"),
    ("Splits with friends", r"CASH", "Paid in cash"),
    ("Entertainment", r"PVR", "Movies"),
]
SUB_RULES = [(c, re.compile(p), sub) for c, p, sub in SUB_RULES]


def subcategory(category, merchant, desc):
    text = f"{merchant} {desc}".upper()
    for c, pat, sub in SUB_RULES:
        if c == category and pat.search(text):
            return sub
    return merchant if category in ("Subscriptions & apps", "Entertainment", "Travel & stays",
                                    "Personal care", "Education & classes", "Insurance") else ""
