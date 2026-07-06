from pipeline import run_pipeline

TEST_CASES = {
    "clearly_ai": (
        "Artificial intelligence represents a transformative paradigm shift in modern society. "
        "It is important to note that while the benefits of AI are numerous, it is equally "
        "essential to consider the ethical implications. Furthermore, stakeholders across "
        "various sectors must collaborate to ensure responsible deployment."
    ),
    "clearly_human": (
        "ok so i finally tried that new ramen place downtown and honestly? "
        "underwhelming. the broth was fine but they put WAY too much sodium in it and "
        "i was thirsty for like three hours after. my friend got the spicy version and "
        "said it was better. probably won't go back unless someone drags me there"
    ),
    "borderline_formal_human": (
        "The relationship between monetary policy and asset price inflation has been "
        "extensively studied in the literature. Central banks face a fundamental tension "
        "between their mandate for price stability and the unintended consequences of "
        "prolonged low interest rates on equity and real estate valuations."
    ),
    "borderline_edited_ai": (
        "I've been thinking a lot about remote work lately. There are genuine tradeoffs — "
        "flexibility and no commute on one side, isolation and blurred work-life boundaries "
        "on the other. Studies show productivity varies widely by individual and role type."
    ),
}

EXPECTATIONS = {
    "clearly_ai": "should score high (net_score > 0, band = lean_ai or strong_ai)",
    "clearly_human": "should score low (net_score < 0, band = lean_human or strong_human)",
    "borderline_formal_human": "may score mid-high on stylometrics -- formal but human",
    "borderline_edited_ai": "should ideally score mid-range (indeterminate) -- lightly edited AI",
}

if __name__ == "__main__":
    print(f"{'case':<26}{'words':<8}{'sentences':<11}{'score':<8}{'band':<16}{'label'}")
    print("-" * 100)
    for name, text in TEST_CASES.items():
        r = run_pipeline(text, domain="general")
        wc = len(text.split())
        sentence_count = [s for s in r.signals if s.name == "sentence_rhythm"][0].detail
        print(f"{name:<26}{wc:<8}{'':<11}{r.net_score:<8}{r.confidence_band.value:<16}{r.label}")

    print()
    print("Signal-level detail:")
    print("-" * 100)
    for name, text in TEST_CASES.items():
        print(f"\n{name} (expected: {EXPECTATIONS[name]})")
        r = run_pipeline(text, domain="general")
        for s in r.signals:
            print(f"  {s.name}: {s.direction.value} ({s.weight.name}) — {s.detail}")